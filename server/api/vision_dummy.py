from __future__ import annotations

from fastapi import APIRouter, Depends

from gate.models import FaceMatch
from server.api.common import fail
from server.deps import get_vision_service, require_admin
from server.schemas import VisionDummyState
from vision.service import VisionServiceDummyControl

router = APIRouter()


def _get_dummy() -> VisionServiceDummyControl:
    vision = get_vision_service()
    if not isinstance(vision, VisionServiceDummyControl):
        fail(
            400,
            "VISION_DUMMY_DISABLED",
            "Vision dummy not enabled",
            {"provider": vision.__class__.__name__ if vision else None},
        )
    return vision


@router.get("/", response_model=VisionDummyState)
async def get_state(_: dict = Depends(require_admin)) -> VisionDummyState:
    v = _get_dummy()
    return VisionDummyState(
        people_count=v._cfg.default_people_count,
        face_match=(
            v._cfg.default_face_match.name if v._cfg.default_face_match else None
        ),
        delay_ms=int(v._cfg.dummy_delay_sec * 1000),
    )


@router.post("/", response_model=VisionDummyState)
async def set_state(
    payload: VisionDummyState, _: dict = Depends(require_admin)
) -> VisionDummyState:
    v = _get_dummy()
    match = FaceMatch[payload.face_match] if payload.face_match else FaceMatch.NO_FACE
    v.set_values(
        people_count=payload.people_count, face_match=match, delay_ms=payload.delay_ms
    )
    return VisionDummyState(
        people_count=payload.people_count,
        face_match=match.name,
        delay_ms=payload.delay_ms,
    )
