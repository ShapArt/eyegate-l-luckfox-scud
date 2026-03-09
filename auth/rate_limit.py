from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class _Entry:
    fails: int = 0
    locked_until: float = 0.0


@dataclass
class LoginRateLimiter:
    """Простейший лимитер попыток логина по логину (в памяти процесса)."""

    max_failures: int = 5
    lock_seconds: float = 30.0
    _store: Dict[str, _Entry] = field(default_factory=dict)

    def is_locked(self, login: str) -> bool:
        entry = self._store.get(login)
        if entry is None:
            return False
        now = time.monotonic()
        if entry.locked_until > now:
            return True
        # Срок блокировки истёк — сбрасываем счётчик
        if entry.locked_until > 0:
            self._store.pop(login, None)
        return False

    def record_failure(self, login: str) -> bool:
        entry = self._store.setdefault(login, _Entry())
        entry.fails += 1
        if entry.fails >= self.max_failures:
            entry.locked_until = time.monotonic() + self.lock_seconds
            return True
        return False

    def reset(self, login: str) -> None:
        self._store.pop(login, None)

    def clear(self) -> None:
        self._store.clear()
