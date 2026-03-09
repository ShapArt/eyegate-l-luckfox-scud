from __future__ import annotations

from typing import Any

from fastapi import HTTPException


def fail(status_code: int, code: str, message: str, details: Any | None = None) -> None:
    """
    Raise a normalized HTTPException that will be rendered as
    {"error": {code, message, details?}} by the global handlers.
    """
    raise HTTPException(
        status_code=status_code,
        detail={
            "code": code,
            "message": message,
            "details": details,
        },
    )
