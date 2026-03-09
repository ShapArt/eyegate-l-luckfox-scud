from __future__ import annotations

import asyncio
import base64
import binascii
import datetime as dt
import os

from fastapi import APIRouter, Depends, HTTPException

from auth.passwords import hash_password, verify_password
from auth.rate_limit import LoginRateLimiter
from auth.tokens import create_token
from auth.validation import password_strength_error
from db import models as db_models
from gate.controller import GateController
from server.deps import get_gate_controller
from server.schemas import (
    AdminLoginRequest,
    LoginRequest,
    LoginResponse,
    PinLoginRequest,
    RegisterRequest,
    UserOut,
)
from vision.embeddings import compute_dummy_embedding

router = APIRouter()

_rate_limiter = LoginRateLimiter(
    max_failures=int(os.getenv("LOGIN_MAX_FAILURES", "5")),
    lock_seconds=float(os.getenv("LOGIN_LOCK_SECONDS", "30")),
)

_pin_rate_limiter = LoginRateLimiter(
    max_failures=int(os.getenv("PIN_MAX_FAILURES", "5")),
    lock_seconds=float(os.getenv("PIN_LOCK_SECONDS", "20")),
)


@router.post("/register", response_model=UserOut)
async def register(payload: RegisterRequest) -> UserOut:
    if payload.password != payload.password_confirm:
        _raise(400, "PASSWORD_MISMATCH", "Passwords do not match")
    pwd_err = password_strength_error(payload.password)
    if pwd_err:
        _raise(400, "PASSWORD_WEAK", pwd_err)

    if db_models.get_user_by_login(payload.login) is not None:
        _raise(400, "LOGIN_EXISTS", "Login already exists")
    if db_models.get_user_by_card(payload.card_id) is not None:
        _raise(400, "CARD_EXISTS", "Card already exists")

    face_embedding = None
    if payload.face_image_b64:
        try:
            image_bytes = _decode_base64(payload.face_image_b64)
            face_embedding = compute_dummy_embedding(image_bytes)
        except (binascii.Error, ValueError) as exc:  # noqa: F841
            _raise(400, "FACE_IMAGE_INVALID", f"Invalid face image: {exc}")
    elif payload.face_embedding_b64:
        try:
            face_embedding = _decode_base64(payload.face_embedding_b64)
        except binascii.Error as exc:  # noqa: F841
            _raise(400, "FACE_EMBEDDING_INVALID", "Invalid face_embedding_b64")

    auto_approve = _env_bool(
        "AUTO_APPROVE_REGISTRATION",
        "AUTH_AUTO_APPROVE_REGISTRATION",
        "EYEGATE_DEMO_MODE",
    )
    status = "active" if auto_approve else "pending"
    approved_at = dt.datetime.utcnow() if auto_approve else None

    user_id = db_models.create_user(
        name=payload.name,
        login=payload.login,
        password_hash=hash_password(payload.password),
        pin_hash=hash_password(payload.password),
        card_id=payload.card_id,
        access_level=payload.access_level,
        is_blocked=payload.is_blocked,
        face_embedding=face_embedding,
        role="user",
        status=status,
        approved_at=approved_at,
    )
    created = db_models.get_user_by_login(payload.login)
    if created is None:
        _raise(500, "USER_CREATE_FAILED", "Failed to create user")

    if status == "active":
        db_models.insert_event(
            level="INFO",
            message=f"User registered (active): {created.login}",
            reason="USER_REGISTERED_ACTIVE",
            state="SYSTEM",
            card_id=None,
            user_id=created.id,
        )
    else:
        db_models.insert_event(
            level="INFO",
            message=f"User registered (pending): {created.login}",
            reason="USER_REGISTERED_PENDING",
            state="SYSTEM",
            card_id=None,
            user_id=created.id,
        )
    return UserOut(
        id=created.id,
        name=created.name,
        login=created.login,
        card_id=created.card_id,
        access_level=created.access_level,
        is_blocked=created.is_blocked,
        status=created.status,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    controller: GateController = Depends(get_gate_controller),
) -> LoginResponse:
    if _rate_limiter.is_locked(payload.login):
        db_models.insert_event(
            level="WARN",
            message=f"Login locked for {payload.login}",
            reason="LOGIN_RATE_LIMIT",
            state="AUTH",
            card_id=None,
            user_id=None,
        )
        _raise(429, "LOGIN_LOCKED", "Too many attempts, try later")

    user = db_models.get_user_by_login(payload.login)
    if user is None:
        db_models.insert_event(
            level="WARN",
            message=f"Login failed for {payload.login}",
            reason="INVALID_CREDENTIALS",
            state="AUTH",
            card_id=None,
            user_id=None,
        )
        _raise(401, "INVALID_CREDENTIALS", "Invalid credentials")
    if user.status == "pending":
        db_models.insert_event(
            level="WARN",
            message=f"Login blocked (pending) for {payload.login}",
            reason="USER_PENDING",
            state="AUTH",
            card_id=None,
            user_id=user.id,
        )
        _raise(403, "USER_PENDING", "User pending approval")
    if user.status == "rejected":
        db_models.insert_event(
            level="WARN",
            message=f"Login blocked (rejected) for {payload.login}",
            reason="USER_REJECTED",
            state="AUTH",
            card_id=None,
            user_id=user.id,
        )
        _raise(403, "USER_REJECTED", "User rejected")
    if user.is_blocked:
        db_models.insert_event(
            level="WARN",
            message=f"Login blocked for {payload.login}",
            reason="USER_BLOCKED",
            state="AUTH",
            card_id=None,
            user_id=user.id,
        )
        _raise(403, "USER_BLOCKED", "User is blocked")
    if not verify_password(payload.password, user.password_hash):
        locked = _rate_limiter.record_failure(payload.login)
        db_models.insert_event(
            level="WARN",
            message=f"Login failed for {payload.login}",
            reason="INVALID_CREDENTIALS",
            state="AUTH",
            card_id=None,
            user_id=user.id,
        )
        if locked:
            _raise(429, "LOGIN_LOCKED", "Too many attempts, try later")
        _raise(401, "INVALID_CREDENTIALS", "Invalid credentials")

    await controller.login_success(user.id)
    _rate_limiter.reset(payload.login)

    token = create_token({"user_id": user.id, "role": user.role})

    db_models.insert_event(
        level="INFO",
        message=f"Login success for {payload.login}",
        reason="LOGIN_OK",
        state="AUTH",
        card_id=None,
        user_id=user.id,
    )

    return LoginResponse(
        status="ok",
        user_id=user.id,
        state=controller.state.name,
        token=token,
        role=user.role,
    )


@router.post("/pin")
async def kiosk_pin(
    payload: PinLoginRequest,
    controller: GateController = Depends(get_gate_controller),
) -> dict:
    user = db_models.find_user_by_pin(payload.pin)
    if user is None:
        _raise(401, "PIN_INVALID", "PIN rejected")
    await controller.login_success(user.id)
    # For demos, immediately unlock/open door 1 to reflect access.
    try:
        controller._doors.unlock_door1()  # type: ignore[attr-defined]
        if hasattr(controller._doors, "open_door"):
            controller._doors.open_door(1)  # type: ignore[attr-defined]
    except Exception:
        pass
    await asyncio.sleep(0.05)
    return {
        "status": "ok",
        "state": controller.state.name,
        "userId": user.id,
        "login": user.login,
    }


@router.post("/admin/login", response_model=LoginResponse)
async def admin_login(
    payload: AdminLoginRequest,
    controller: GateController = Depends(get_gate_controller),
) -> LoginResponse:
    expected_login = os.getenv("ADMIN_LOGIN", "admin")
    expected_pass = os.getenv("ADMIN_PASS", "admin123")
    admin_card = os.getenv("ADMIN_CARD_ID", "ADMINCARD")

    if not expected_pass:
        _raise(
            503, "ADMIN_NOT_CONFIGURED", "ADMIN_PASS is not configured on the server"
        )
    if payload.login != expected_login or payload.password != expected_pass:
        _raise(401, "ADMIN_INVALID_CREDENTIALS", "Invalid admin credentials")

    admin = db_models.get_user_by_login(expected_login)
    if admin is None:
        db_models.create_user(
            name="Administrator",
            login=expected_login,
            password_hash=hash_password(expected_pass),
            pin_hash=hash_password(expected_pass),
            card_id=admin_card,
            access_level=10,
            is_blocked=False,
            face_embedding=None,
            role="admin",
            status="active",
        )
        admin = db_models.get_user_by_login(expected_login)
        if admin is None:
            _raise(500, "ADMIN_CREATE_FAILED", "Failed to create admin user")
    else:
        needs_update = False
        new_role = admin.role
        new_status = admin.status
        new_pwd = admin.password_hash
        if admin.role != "admin":
            new_role = "admin"
            needs_update = True
        if admin.status != "active":
            new_status = "active"
            needs_update = True
        if not admin.password_hash:
            new_pwd = hash_password(expected_pass)
            needs_update = True
        if needs_update:
            db_models.update_user(
                admin.id,
                role=new_role,
                status=new_status,
                password_hash=new_pwd,
                pin_hash=new_pwd,
            )
            admin = db_models.get_user_by_login(expected_login)

    token = create_token({"user_id": admin.id, "role": "admin"})  # type: ignore[arg-type]
    return LoginResponse(
        status="ok",
        user_id=admin.id,  # type: ignore[arg-type]
        state=controller.state.name,
        token=token,
        role="admin",
    )


def _raise(status: int, code: str, message: str, details: object | None = None) -> None:
    raise HTTPException(
        status_code=status,
        detail={
            "code": code,
            "message": message,
            "details": details,
        },
    )


def _decode_base64(data: str) -> bytes:
    """Принимает data URL или чистый base64, возвращает байты."""
    if "," in data:
        data = data.split(",", 1)[1]
    return base64.b64decode(data)


def _env_bool(*names: str) -> bool:
    for name in names:
        raw = os.getenv(name, "").strip()
        if raw:
            return raw.lower() in ("1", "true", "yes", "on")
    return False
