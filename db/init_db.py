from __future__ import annotations

import logging
import os
import sqlite3
import sys
import time
from pathlib import Path

from auth.passwords import hash_password

from .models import (
    create_tables_if_not_exists,
    create_user,
    get_user_by_card,
    get_user_by_login,
)

logger = logging.getLogger(__name__)


def _reset_connection(new_path: str | Path) -> None:
    """Switch DB path and drop cached connection safely."""
    os.environ["EYEGATE_DB_PATH"] = str(new_path)
    from db import base  # local import to avoid cycle

    try:
        base.close_all_connections()  # type: ignore[attr-defined]
    except Exception:
        if getattr(base, "_DB_CONN", None) is not None:
            try:
                base._DB_CONN.close()  # type: ignore[attr-defined]
            except Exception:
                pass
            base._DB_CONN = None  # type: ignore[attr-defined]


def init_db() -> None:
    # Use a stable on-disk DB unless caller overrides EYEGATE_DB_PATH explicitly.
    if not os.getenv("EYEGATE_DB_PATH"):
        project_root = Path(__file__).resolve().parents[1]
        default_path = project_root / "data" / "eyegate_scud.db"
        default_path.parent.mkdir(parents=True, exist_ok=True)
        _reset_connection(default_path.resolve())

    attempts = 12
    for attempt in range(attempts):
        try:
            create_tables_if_not_exists()
            break
        except sqlite3.OperationalError as exc:
            msg = str(exc).lower()
            if "locked" in msg or "busy" in msg:
                if attempt < attempts - 1:
                    time.sleep(min(0.25 * (attempt + 1), 2.0))
                    continue
            raise
    demo_card = "CARD123"
    if get_user_by_card(demo_card) is None:
        create_user(
            name="Demo User",
            login="demo",
            password_hash=hash_password("demo"),
            pin_hash=hash_password("0000"),
            card_id=demo_card,
            access_level=1,
            is_blocked=False,
            face_embedding=None,
            status="active",
        )
    _ensure_admin_seed()
    _ensure_demo_person_seed()


def _ensure_admin_seed() -> None:
    demo_mode = os.getenv("EYEGATE_DEMO_MODE", "0") == "1"
    admin_login = os.getenv("ADMIN_LOGIN", "admin")
    admin_pass = os.getenv("ADMIN_PASS")
    if not admin_pass and demo_mode:
        admin_pass = "admin123"
    admin_card = os.getenv("ADMIN_CARD_ID", "ADMINCARD")

    if not admin_pass:
        return

    existing = get_user_by_login(admin_login) or get_user_by_card(admin_card)
    if existing is None:
        create_user(
            name="Administrator",
            login=admin_login,
            password_hash=hash_password(admin_pass),
            pin_hash=hash_password(admin_pass),
            card_id=admin_card,
            access_level=10,
            is_blocked=False,
            face_embedding=None,
            role="admin",
            status="active",
        )
        return

    # If already present, make sure role/status are elevated for demo usability.
    needs_update = False
    update_kwargs = {}
    if existing.login != admin_login:
        update_kwargs["login"] = admin_login
        needs_update = True
    if existing.role != "admin":
        update_kwargs["role"] = "admin"
        needs_update = True
    if existing.status != "active":
        update_kwargs["status"] = "active"
        needs_update = True
    if existing.password_hash in ("", None):
        update_kwargs["password_hash"] = hash_password(admin_pass)
        needs_update = True
    if needs_update:
        from db import models as db_models  # local import to avoid cycle

        db_models.update_user(existing.id, **update_kwargs)


def _ensure_demo_person_seed() -> None:
    """Seed a single known user for demo-only recognition/labels."""
    demo_mode = os.getenv("EYEGATE_DEMO_MODE", "0") == "1"
    if not demo_mode:
        return
    login = os.getenv("DEMO_PERSON_LOGIN", "shapovalov")
    name = os.getenv("DEMO_PERSON_NAME", "Shapovalov Artem")
    pin = os.getenv("DEMO_PERSON_PIN", "1234")
    card_id = os.getenv("DEMO_PERSON_CARD_ID", "SHAPCARD")

    existing = get_user_by_login(login) or get_user_by_card(card_id)
    if existing is not None:
        return

    create_user(
        name=name,
        login=login,
        password_hash=hash_password(pin),
        pin_hash=hash_password(pin),
        card_id=card_id,
        access_level=1,
        is_blocked=False,
        face_embedding=None,
        status="active",
    )


if __name__ == "__main__":
    try:
        init_db()
    except Exception as exc:
        print(f"Database init failed: {exc}")
        sys.exit(1)
    print("Database initialized.")
