from __future__ import annotations

from fastapi import APIRouter

from . import auth, camera_control, config, events, sim, status, users, video

api_router = APIRouter()
api_router.include_router(status.router, prefix="/status", tags=["status"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(sim.router, prefix="/sim", tags=["sim"])
api_router.include_router(video.router, prefix="/video", tags=["video"])
api_router.include_router(camera_control.router, prefix="/camera", tags=["camera"])
api_router.include_router(config.router, prefix="/config", tags=["config"])
