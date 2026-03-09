from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response, StreamingResponse

from server.deps import get_vision_service

router = APIRouter()


async def _mjpeg_stream(vision, max_frames: int | None = None):
    boundary = b"frame"
    sent = 0
    while True:
        frame = vision.get_jpeg_frame()
        yield b"--" + boundary + b"\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
        sent += 1
        if max_frames is not None and sent >= max_frames:
            return
        await asyncio.sleep(0.08)


@router.get("/mjpeg")
async def video_mjpeg(
    max_frames: Annotated[int | None, Query(ge=1, le=1000)] = None,
    vision=Depends(get_vision_service),
) -> StreamingResponse:  # type: ignore[valid-type]
    return StreamingResponse(
        _mjpeg_stream(vision, max_frames=max_frames),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/snapshot")
async def video_snapshot(vision=Depends(get_vision_service)) -> Response:  # type: ignore[valid-type]
    frame = vision.get_jpeg_frame()
    headers = {}
    try:
        snap = vision.last_snapshot()
        ts = snap.get("last_frame_ts") if isinstance(snap, dict) else None
        if ts:
            headers["X-Frame-Timestamp"] = str(ts)
    except Exception:
        pass
    return Response(content=frame, media_type="image/jpeg", headers=headers)
