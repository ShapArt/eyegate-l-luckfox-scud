from __future__ import annotations

import asyncio
import datetime as dt

from fastapi import APIRouter, Depends

from gate.controller import GateController
from server.deps import get_gate_controller, require_admin
from server.schemas import GateStatus, VisionSnapshot

router = APIRouter()


@router.get("/", response_model=GateStatus)
async def get_status(
    controller: GateController = Depends(get_gate_controller),
) -> GateStatus:
    snap = _normalize_snapshot(controller.snapshot())
    vision_info = snap.get("vision")
    if isinstance(vision_info, dict):
        snap["vision"] = VisionSnapshot(**vision_info)
    return GateStatus(**snap)


@router.post("/reset", response_model=GateStatus)
async def reset_system(
    controller: GateController = Depends(get_gate_controller),
    _: dict = Depends(require_admin),
) -> GateStatus:
    await controller.reset()
    await asyncio.sleep(0.01)
    snap = _normalize_snapshot(controller.snapshot())
    vision_info = snap.get("vision")
    if isinstance(vision_info, dict):
        snap["vision"] = VisionSnapshot(**vision_info)
    return GateStatus(**snap)


def _normalize_snapshot(raw: dict) -> dict:
    snap = dict(raw)
    ts = snap.get("timestamp")
    if isinstance(ts, str):
        try:
            snap["timestamp"] = dt.datetime.fromisoformat(ts)
        except ValueError:
            snap["timestamp"] = None
    vision = snap.get("vision")
    if isinstance(vision, dict):
        snap["vision"] = vision
    return snap
