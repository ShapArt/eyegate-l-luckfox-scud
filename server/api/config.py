from __future__ import annotations

from fastapi import APIRouter

from server.deps import get_config

router = APIRouter()


@router.get("/")
async def get_app_config() -> dict:
    cfg = get_config()
    return {
        "camera_rtsp_url": cfg.camera_rtsp_url,
        "camera_hls_url": "/streams/live0/index.m3u8",
        "health_camera_url": "/health/camera",
    }
