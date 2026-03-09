from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from db import models as db_models

from .models import User


@dataclass
class AuthConfig:
    master_card_id: Optional[str] = None


class AuthServiceDummy:
    """Простейшая in-memory реализация AuthServiceInterface."""

    def __init__(self, cfg: Optional[AuthConfig] = None) -> None:
        self._cfg = cfg or AuthConfig()
        self._users_by_card: Dict[str, User] = {}
        demo_user = User(
            id=1,
            name="Demo User",
            login="demo",
            card_id="CARD123",
            is_blocked=False,
            access_level=1,
        )
        self._users_by_card[demo_user.card_id] = demo_user

    async def check_card(self, card_id: str) -> Tuple[bool, Optional[int], str]:
        if self._cfg.master_card_id and card_id == self._cfg.master_card_id:
            return True, 0, "MASTER_CARD"

        user = self._users_by_card.get(card_id)
        if user is None:
            return False, None, "CARD_NOT_FOUND"
        if user.is_blocked:
            return False, user.id, "USER_BLOCKED"
        return True, user.id, "OK"

    def add_user(self, user: User) -> None:
        self._users_by_card[user.card_id] = user

    def remove_user(self, card_id: str) -> None:
        self._users_by_card.pop(card_id, None)

    def get_user_by_card(self, card_id: str) -> Optional[User]:
        return self._users_by_card.get(card_id)


class AuthServiceDB:
    """Auth service backed by the SQLite users table."""

    def __init__(self, cfg: Optional[AuthConfig] = None) -> None:
        self._cfg = cfg or AuthConfig()

    async def check_card(self, card_id: str) -> Tuple[bool, Optional[int], str]:
        if self._cfg.master_card_id and card_id == self._cfg.master_card_id:
            return True, 0, "MASTER_CARD"

        user = db_models.get_user_by_card(card_id) or db_models.find_user_by_pin(
            card_id
        )
        if user is None:
            return False, None, "CARD_NOT_FOUND"
        if getattr(user, "status", "active") != "active":
            return False, user.id, f"USER_{user.status.upper()}"
        if user.is_blocked:
            return False, user.id, "USER_BLOCKED"
        return True, user.id, "OK"
