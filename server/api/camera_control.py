from __future__ import annotations

from fastapi import APIRouter, Depends

from server.deps import get_vision_service

router = APIRouter()


@router.post("/warmup")
async def warmup_camera(vision=Depends(get_vision_service)) -> dict:  # type: ignore[valid-type]
    """
    No-op endpoint to hint the backend camera loop to start (compatible with dummy).
    """
    try:
        vision.get_jpeg_frame()
    except Exception:
        pass
    return {"status": "ok"}
