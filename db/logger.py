from __future__ import annotations

import datetime as dt
from typing import Optional

from gate.models import GateState

from .models import insert_event


class SQLiteEventLogger:
    """Запись событий в SQLite и, опционально, в stdout."""

    def __init__(self, mirror_to_stdout: bool = True) -> None:
        self._mirror = mirror_to_stdout

    async def log(
        self,
        level: str,
        message: str,
        reason: Optional[str],
        state: GateState,
        card_id: Optional[str],
        user_id: Optional[int],
    ) -> None:
        insert_event(
            level=level,
            message=message,
            reason=reason,
            state=state.name,
            card_id=card_id,
            user_id=user_id,
        )
        if self._mirror:
            ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            parts = [
                f"[{ts}]",
                f"[{level}]",
                f"[state={state.name}]",
            ]
            if card_id is not None:
                parts.append(f"[card={card_id}]")
            if user_id is not None:
                parts.append(f"[user={user_id}]")
            if reason:
                parts.append(f"[reason={reason}]")
            parts.append(f"- {message}")
            print(" ".join(parts))
