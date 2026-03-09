from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter

from server.deps import get_camera_ingest, get_config, get_vision_service

router = APIRouter()


@router.get("/health/camera")
async def camera_health() -> dict:
    cfg = get_config()
    url = cfg.camera_rtsp_url or cfg.vision_camera_source
    ingest = get_camera_ingest()
    timeout_sec = 2.5

    if ingest is not None:
        probe_id = ingest.frame_id
        frame = await asyncio.to_thread(ingest.get_frame, timeout_sec, probe_id)
        now = time.time()
        last_ts = ingest.last_frame_ts
        ok = frame is not None or (
            last_ts is not None and (now - last_ts) <= timeout_sec
        )
        error = None if ok else (ingest.last_error or "NO_FRAME")
        return {
            "ok": ok,
            "url": url,
            "error": error,
            "last_frame_ts": last_ts,
        }

    vision = get_vision_service()
    last_ts = None
    ok = False
    error = None
    try:
        snap = vision.last_snapshot()
    except Exception:
        snap = None
    if isinstance(snap, dict):
        last_ts = snap.get("last_frame_ts")
        ok = bool(snap.get("camera_ok", False))
        if not ok:
            error = snap.get("vision_error") or "NO_FRAME"
    return {
        "ok": ok,
        "url": url,
        "error": error,
        "last_frame_ts": last_ts,
    }
