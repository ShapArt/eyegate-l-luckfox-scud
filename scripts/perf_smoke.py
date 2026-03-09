"""
Простой нагрузочный скрипт (smoke) для API:
- Создаёт пользователя (если нужно) через /api/auth/register.
- Гоняет параллельные логины + статус-запросы.

Запуск:
    python scripts/perf_smoke.py --base http://localhost:8000 --login user --password passw0rd --register

Параметры:
- --base: URL сервера.
- --login/--password: учётка для логина.
- --register: предварительно создать пользователя (без face_image_b64).
- --concurrency: число параллельных логинов.
- --iterations: сколько логинов на поток.
"""

from __future__ import annotations

import argparse
import asyncio
import json

import httpx


async def ensure_user(
    client: httpx.AsyncClient, base: str, login: str, password: str
) -> None:
    payload = {
        "name": login,
        "login": login,
        "card_id": f"CARD_{login}",
        "password": password,
        "password_confirm": password,
        "access_level": 1,
    }
    resp = await client.post(f"{base}/api/auth/register", json=payload)
    if resp.status_code not in (200, 400):  # 400 если login уже есть
        raise RuntimeError(f"register failed: {resp.status_code} {resp.text}")


async def login_once(
    client: httpx.AsyncClient, base: str, login: str, password: str
) -> bool:
    resp = await client.post(
        f"{base}/api/auth/login", json={"login": login, "password": password}
    )
    return resp.status_code == 200


async def poll_status(client: httpx.AsyncClient, base: str) -> None:
    await client.get(f"{base}/api/status/")


async def worker(base: str, login: str, password: str, iterations: int) -> int:
    ok = 0
    status_lat_ms = []
    login_lat_ms = []
    async with httpx.AsyncClient(timeout=5.0) as client:
        for _ in range(iterations):
            start = asyncio.get_event_loop().time()
            if await login_once(client, base, login, password):
                ok += 1
            login_lat_ms.append((asyncio.get_event_loop().time() - start) * 1000)
            s_start = asyncio.get_event_loop().time()
            await poll_status(client, base)
            status_lat_ms.append((asyncio.get_event_loop().time() - s_start) * 1000)
    return ok, max(login_lat_ms or [0]), max(status_lat_ms or [0])


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--login", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--iterations", type=int, default=20)
    args = parser.parse_args()

    async with httpx.AsyncClient(timeout=5.0) as client:
        if args.register:
            await ensure_user(client, args.base, args.login, args.password)

    tasks = [
        worker(args.base, args.login, args.password, args.iterations)
        for _ in range(args.concurrency)
    ]
    results = await asyncio.gather(*tasks)
    total_ok = sum(r[0] for r in results)
    max_login = max(r[1] for r in results)
    max_status = max(r[2] for r in results)
    total_attempts = args.concurrency * args.iterations
    summary = {
        "base": args.base,
        "concurrency": args.concurrency,
        "iterations": args.iterations,
        "ok_logins": total_ok,
        "attempts": total_attempts,
        "success_rate": total_ok / total_attempts if total_attempts else 0,
        "max_login_ms": max_login,
        "max_status_ms": max_status,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
