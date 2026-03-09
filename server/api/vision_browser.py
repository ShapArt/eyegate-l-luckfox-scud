from __future__ import annotations

from fastapi import APIRouter, Depends

from db import models as db_models
from gate.controller import GateController
from gate.models import GateState, RoomAnalyzed
from server.api.common import fail
from server.deps import get_gate_controller, get_vision_service
from server.schemas import BrowserVisionPayload, VisionLastResponse, VisionSnapshot
from server.status_bus import status_bus
from vision.service import VisionServiceBrowserPush

router = APIRouter()


def _get_browser_service() -> VisionServiceBrowserPush:
    vision = get_vision_service()
    if not isinstance(vision, VisionServiceBrowserPush):
        fail(400, "VISION_BROWSER_DISABLED", "Browser vision is not enabled")
    return vision


@router.post("/", response_model=VisionSnapshot)
async def push_vision(
    payload: BrowserVisionPayload,
    controller: GateController = Depends(get_gate_controller),
) -> VisionSnapshot:
    vision = _get_browser_service()
    descriptor = payload.faces[0].descriptor if payload.faces else None
    best_user_id = payload.best_match.user_id if payload.best_match else None
    if best_user_id is None and payload.best_match and payload.best_match.login:
        best_user = db_models.get_user_by_login(payload.best_match.login)
        if best_user:
            best_user_id = best_user.id
    distance = payload.best_match.distance if payload.best_match else None

    analysis = await vision.record_browser_reading(
        people_count=payload.people_count,
        match=payload.match,
        descriptor=descriptor,
        best_user_id=best_user_id,
        distance=distance,
        expected_user_id=controller.current_user_id,
        payload_ts=payload.ts,
    )

    if controller.state == GateState.CHECK_ROOM:
        await controller.push_event(
            RoomAnalyzed(
                people_count=analysis.people_count,
                face_match=analysis.face_match,
                stale=analysis.stale,
                matched_user_id=analysis.matched_user_id,
                match_distance=analysis.match_distance,
            )
        )

    # Log snapshot for observability (no-op if DB unavailable)
    try:
        db_models.insert_event(
            level="INFO",
            message=f"Vision push: people={analysis.people_count}, match={analysis.face_match.name}, stale={analysis.stale}",
            reason="VISION_PUSH",
            state=controller.state.name,
            card_id=None,
            user_id=best_user_id,
        )
    except Exception:
        pass

    snapshot_full = controller.snapshot()
    snapshot = vision.last_snapshot()
    snapshot_full["vision"] = snapshot
    # broadcast updated status so WS consumers see fresh vision without waiting for FSM events
    await status_bus.broadcast(snapshot_full)
    return VisionSnapshot(**snapshot)


@router.get("/last", response_model=VisionLastResponse)
async def get_last() -> VisionLastResponse:
    vision = _get_browser_service()
    snapshot = vision.last_snapshot()
    return VisionLastResponse(last=VisionSnapshot(**snapshot))
