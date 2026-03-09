from __future__ import annotations

import base64
import hmac
import json
import os
import time
from hashlib import sha256
from typing import Any, Dict, Optional


def _get_secret() -> str:
    return os.getenv("AUTH_SECRET", "dev-secret-change-me")


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_token(payload: Dict[str, Any], expires_in: int = 3600) -> str:
    body = payload.copy()
    body["exp"] = int(time.time()) + expires_in
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    secret = _get_secret().encode("utf-8")
    sig = hmac.new(secret, raw, sha256).digest()
    return _b64url(raw) + "." + _b64url(sig)


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    if "." not in token:
        return None
    raw_b64, sig_b64 = token.split(".", 1)
    try:
        raw = _b64url_decode(raw_b64)
        sig = _b64url_decode(sig_b64)
    except (ValueError, base64.binascii.Error):
        return None
    secret = _get_secret().encode("utf-8")
    expected = hmac.new(secret, raw, sha256).digest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        body = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return None
    if "exp" in body and int(time.time()) > int(body["exp"]):
        return None
    return body
