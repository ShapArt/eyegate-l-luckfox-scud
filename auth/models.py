from __future__ import annotations

from dataclasses import dataclass


@dataclass
class User:
    id: int
    name: str
    login: str
    card_id: str
    is_blocked: bool = False
    access_level: int = 1
