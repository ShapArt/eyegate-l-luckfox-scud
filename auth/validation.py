from __future__ import annotations

from typing import Optional


def password_strength_error(password: str) -> Optional[str]:
    """
    Simplified demo-friendly password policy:
    - minimum length 4
    Returns None if OK, otherwise an error string.
    """
    if len(password) < 4:
        return "Password must be at least 4 characters long"
    return None
