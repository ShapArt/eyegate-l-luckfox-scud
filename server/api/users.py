from __future__ import annotations

from fastapi import APIRouter, Depends

from auth.passwords import hash_password
from db import models as db_models
from server.api.common import fail
from server.deps import get_current_user, get_vision_service, require_admin
from server.schemas import UserOut, UserQuickCreate

router = APIRouter()


@router.get("/", response_model=list[UserOut])
async def list_users() -> list[UserOut]:
    users = db_models.list_users()
    return [_to_user_out(u) for u in users]


@router.get("/quick", response_model=list[UserOut])
async def list_users_quick() -> list[UserOut]:
    """Compatibility GET for legacy frontend."""
    return await list_users()


@router.post("/", response_model=UserOut)
async def create_user_quick(payload: UserQuickCreate) -> UserOut:
    if not payload.pin.isdigit() or len(payload.pin) != 4:
        fail(400, "BAD_PIN", "PIN must be exactly 4 digits")

    if db_models.get_user_by_login(payload.login) is not None:
        fail(400, "LOGIN_EXISTS", "Login already exists")

    pin_hash = hash_password(payload.pin)
    user_id = db_models.create_user(
        name=payload.name or payload.login,
        login=payload.login,
        password_hash=pin_hash,
        pin_hash=pin_hash,
        card_id=f"PIN:{payload.login}",
        access_level=payload.access_level,
        is_blocked=payload.is_blocked,
        face_embedding=None,
        role="user",
        status="active",
    )
    created = _get_user_or_404(user_id)
    return _to_user_out(created)


@router.post("/quick", response_model=UserOut)
async def create_user_quick_alias(payload: UserQuickCreate) -> UserOut:
    """Compatibility alias for previous frontend path."""
    return await create_user_quick(payload)


@router.post("/me/enroll", response_model=UserOut)
async def enroll_face_self(
    current_user=Depends(get_current_user),
    vision=Depends(get_vision_service),  # type: ignore[valid-type]
) -> UserOut:
    user_id = current_user.get("user_id") if isinstance(current_user, dict) else None
    if user_id is None:
        fail(401, "UNAUTHORIZED", "Unauthorized")
    _ = _get_user_or_404(user_id)
    try:
        descriptor_blob = vision.capture_descriptor()
    except Exception as exc:  # noqa: BLE001
        fail(400, "ENROLL_FAILED", f"{exc}")
    db_models.update_user(user_id=user_id, face_embedding=descriptor_blob)
    updated = _get_user_or_404(user_id)
    return _to_user_out(updated)


@router.post("/{user_id}/enroll", response_model=UserOut)
async def enroll_face(user_id: int, vision=Depends(get_vision_service)) -> UserOut:  # type: ignore[valid-type]
    _ = _get_user_or_404(user_id)
    try:
        descriptor_blob = vision.capture_descriptor()
    except Exception as exc:  # noqa: BLE001
        fail(400, "ENROLL_FAILED", f"{exc}")
    db_models.update_user(user_id=user_id, face_embedding=descriptor_blob)
    updated = _get_user_or_404(user_id)
    return _to_user_out(updated)


@router.post("/{user_id}/clear-face", response_model=UserOut)
async def clear_face(
    user_id: int,
    _: dict = Depends(require_admin),
) -> UserOut:
    user = _get_user_or_404(user_id)
    if user.role == "admin":
        fail(403, "ADMIN_PROTECTED", "Admin user cannot be modified")
    db_models.clear_face_embedding(user_id)
    updated = _get_user_or_404(user_id)
    return _to_user_out(updated)


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    _: dict = Depends(require_admin),
) -> dict:
    user = _get_user_or_404(user_id)
    if user.role == "admin":
        fail(403, "ADMIN_PROTECTED", "Admin user cannot be deleted")
    db_models.delete_user(user_id)
    return {"status": "deleted", "user_id": user_id}


def _get_user_or_404(user_id: int) -> db_models.UserRecord:
    from db.base import get_connection

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?;", (user_id,))
    row = cur.fetchone()
    if row is None:
        fail(404, "USER_NOT_FOUND", "User not found")
    return db_models._row_to_user(row)


def _to_user_out(user: db_models.UserRecord) -> UserOut:
    return UserOut(
        id=user.id,
        name=user.name,
        login=user.login,
        card_id=user.card_id,
        access_level=user.access_level,
        is_blocked=user.is_blocked,
        status=user.status,
        role=user.role,
        approved_by=user.approved_by,
        approved_at=user.approved_at,
        has_face=bool(user.face_embedding),
    )
