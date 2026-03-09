from __future__ import annotations

import asyncio
import os
from functools import lru_cache
from pathlib import Path

from fastapi import Header, HTTPException

from auth.service import AuthConfig, AuthServiceDB
from auth.tokens import verify_token
from camera_ingest import CameraIngest, CameraIngestConfig
from db import models as db_models
from db.init_db import init_db
from db.logger import SQLiteEventLogger
from gate.controller import GateConfig, GateController
from gate.fsm import GateFSM
from hw.alarm import AlarmConfig, AlarmGPIO
from hw.doors import DoorsConfig, DoorsController
from hw.dummy import DummyAlarm
from hw.serial_bridge import SerialBridge
from hw.simulated import SimulatedDoors
from server.config import load_config
from server.restream import RestreamConfig, RestreamService
from server.status_bus import status_bus
from vision.service import VisionConfig, VisionServiceDummyControl, VisionServiceOpenCV


@lru_cache
def get_config():
    return load_config()


_status_task: asyncio.Task | None = None
_serial_bridge: SerialBridge | None = None


@lru_cache
def get_camera_ingest() -> CameraIngest | None:
    cfg = get_config()
    url = (cfg.camera_rtsp_url or "").strip()
    if not url or not url.lower().startswith("rtsp://"):
        return None
    ingest_cfg = CameraIngestConfig(
        url=url,
        transport=cfg.rtsp_transport,
        width=cfg.vision_frame_width,
        height=cfg.vision_frame_height,
        read_timeout_sec=max(0.2, cfg.vision_read_timeout_ms / 1000.0),
        backoff_initial_sec=0.5,
        backoff_max_sec=5.0,
        ffmpeg_path=cfg.ffmpeg_path,
    )
    ingest = CameraIngest(ingest_cfg)
    ingest.start()
    return ingest


@lru_cache
def get_restream_service() -> RestreamService | None:
    cfg = get_config()
    url = (cfg.camera_rtsp_url or "").strip()
    if not url or not url.lower().startswith("rtsp://"):
        return None
    repo_root = Path(__file__).resolve().parents[1]
    streams_dir = repo_root / "data" / "streams" / "live0"
    restream_cfg = RestreamConfig(
        input_url=url,
        output_dir=streams_dir,
        transport=cfg.rtsp_transport,
        ffmpeg_path=cfg.ffmpeg_path,
    )
    return RestreamService(restream_cfg)


def start_restream_service() -> None:
    service = get_restream_service()
    if service is not None:
        service.start()


async def _status_poller(controller: GateController) -> None:
    while True:
        try:
            await status_bus.broadcast(controller.snapshot())
        except Exception:
            pass
        await asyncio.sleep(0.1)


def _ensure_models(cfg) -> None:
    """Download YuNet/SFace models when requested (for real vision mode)."""
    if not getattr(cfg, "vision_auto_download", False):
        return
    try:
        from scripts import download_models
    except Exception:
        return
    targets = [
        ("yunet", Path(cfg.vision_detection_model_path)),
        ("sface", Path(cfg.vision_recognition_model_path)),
    ]
    for name, dest in targets:
        if dest.exists():
            continue
        try:
            download_models.download_model(name, dest.parent)
        except Exception:
            # If download fails, we leave vision to degrade gracefully to dummy.
            continue


@lru_cache
def get_gate_controller() -> GateController:
    cfg = get_config()
    init_db()

    fsm = GateFSM()

    if cfg.use_dummy_hw:
        doors = SimulatedDoors(
            auto_close_ms=cfg.sim_auto_close_ms if cfg.sim_auto_close_ms > 0 else None,
            door1_auto_close_ms=(
                cfg.door1_auto_close_ms if cfg.door1_auto_close_ms > 0 else None
            ),
            door2_auto_close_ms=(
                cfg.door2_auto_close_ms if cfg.door2_auto_close_ms > 0 else None
            ),
        )
        alarm = DummyAlarm()
    else:
        doors = DoorsController(
            DoorsConfig(
                door1_lock_gpio=41,
                door2_lock_gpio=42,
                door1_closed_gpio=40,
                door2_closed_gpio=39,
            )
        )
        alarm = AlarmGPIO(
            AlarmConfig(
                alarm_gpio=36,
                active_high=True,
            )
        )

    vision_cfg = VisionConfig(
        mode=cfg.vision_mode,
        # NEW (P0):
        camera_source=cfg.vision_camera_source,
        camera_backend=cfg.vision_camera_backend,
        frame_width=cfg.vision_frame_width,
        frame_height=cfg.vision_frame_height,
        rotate=cfg.vision_rotate,
        flip=cfg.vision_flip,
        open_timeout_ms=cfg.vision_open_timeout_ms,
        read_timeout_ms=cfg.vision_read_timeout_ms,
        reconnect_backoff_ms=cfg.vision_reconnect_backoff_ms,
        reconnect_backoff_max_ms=cfg.vision_reconnect_backoff_max_ms,
        match_threshold=cfg.vision_match_threshold,
        match_metric=cfg.vision_match_metric,
        detection_score_threshold=cfg.vision_detection_score_threshold,
        detection_model_path=cfg.vision_detection_model_path,
        recognition_model_path=cfg.vision_recognition_model_path,
        stale_after_sec=cfg.vision_stale_after_sec,
        smooth_window=cfg.vision_smooth_window,
        smooth_hits=cfg.vision_smooth_hits,
        smooth_ttl_frames=cfg.vision_smooth_ttl_frames,
        smooth_score_jitter=cfg.vision_smooth_score_jitter,
        smooth_iou_threshold=cfg.vision_smooth_iou_threshold,
        # back-compat:
        camera_index=cfg.vision_camera_index,
        # остальное как у тебя уже было:
        bg_history=cfg.bg_history,
        bg_var_threshold=cfg.bg_var_threshold,
        people_min_area=cfg.people_min_area,
        people_min_area_ratio=cfg.people_min_area_ratio,
        people_min_width_ratio=cfg.people_min_width_ratio,
        people_min_height_ratio=cfg.people_min_height_ratio,
        people_min_extent=cfg.people_min_extent,
        people_min_aspect_ratio=cfg.people_min_aspect_ratio,
        people_max_aspect_ratio=cfg.people_max_aspect_ratio,
        people_border_margin_ratio=cfg.people_border_margin_ratio,
        people_merge_margin_ratio=cfg.people_merge_margin_ratio,
        people_dominant_second_area_ratio=cfg.people_dominant_second_area_ratio,
        people_present_frames=cfg.people_present_frames,
        people_absent_frames=cfg.people_absent_frames,
        demo_fixed_login=cfg.vision_demo_fixed_login,
    )

    _ensure_models(cfg)
    ingest = get_camera_ingest()
    if cfg.vision_mode == "dummy":
        vision = VisionServiceDummyControl(vision_cfg)
    else:
        try:
            vision = VisionServiceOpenCV(
                vision_cfg,
                db_models.get_user_by_id,
                db_models.list_users,
                camera_ingest=ingest,
            )
        except Exception as exc:  # noqa: BLE001
            print(
                f"[WARN] Failed to init VisionServiceOpenCV: {exc}. Falling back to dummy."
            )
            vision = VisionServiceDummyControl(vision_cfg)

    auth = AuthServiceDB(AuthConfig())
    logger = SQLiteEventLogger(mirror_to_stdout=True)

    gate_cfg = GateConfig(
        enter_timeout_sec=cfg.enter_timeout_sec,
        check_timeout_sec=cfg.check_timeout_sec,
        exit_timeout_sec=cfg.exit_timeout_sec,
        alarm_timeout_sec=cfg.alarm_timeout_sec,
        auto_open_door1=cfg.demo_mode or isinstance(doors, SimulatedDoors),
        auto_open_door2=cfg.demo_mode or isinstance(doors, SimulatedDoors),
        demo_mode=cfg.demo_mode,
        allow_multi_known=cfg.allow_multi_known,
        require_face_match_for_door2=cfg.require_face_match_for_door2,
        max_people_allowed=cfg.max_people_allowed,
        door1_close_stabilize_ms=cfg.door1_close_stabilize_ms,
        room_check_samples=cfg.room_check_samples,
    )

    controller = GateController(
        fsm=fsm,
        doors=doors,
        vision=vision,
        auth=auth,
        logger=logger,
        alarm=alarm,
        config=gate_cfg,
        on_status=status_bus.broadcast,
    )

    if isinstance(doors, SimulatedDoors):
        doors.set_event_handler(controller.door_closed_changed)

    return controller


async def start_gate_controller() -> None:
    global _status_task, _serial_bridge
    controller = get_gate_controller()
    if _status_task is None or _status_task.done():
        _status_task = asyncio.create_task(_status_poller(controller))
    if not getattr(controller, "_running", False):
        asyncio.create_task(controller.run())
    start_restream_service()

    cfg = get_config()
    if cfg.sensor_mode == "serial" and _serial_bridge is None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()
        doors = getattr(controller, "_doors", None)

        def on_sensor(door: int, is_closed: bool) -> None:
            if hasattr(doors, "set_sensor"):
                try:
                    doors.set_sensor(door, is_closed)  # type: ignore[attr-defined]
                    return
                except Exception:
                    pass
            try:
                asyncio.run_coroutine_threadsafe(
                    controller.door_closed_changed(door, is_closed), loop
                )
            except Exception:
                pass

        if cfg.sensor_serial_port:
            bridge = SerialBridge(
                port=cfg.sensor_serial_port,
                baudrate=cfg.sensor_serial_baud,
                on_sensor=on_sensor,
                loop=loop,
            )
            bridge.start()
            _serial_bridge = bridge


def get_vision_service():
    return get_gate_controller()._vision  # type: ignore[attr-defined]


async def verify_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    """
    Простейший механизм "админ-токена" (X-Admin-Token) ИЛИ bearer-токена с role=admin.
    Если ADMIN_TOKEN не задан и bearer отсутствует — доступ открыт (учебный режим).
    """
    token_env = os.getenv("ADMIN_TOKEN", "")
    if token_env and x_admin_token == token_env:
        return
    # Если есть bearer токен с ролью admin — также разрешаем
    # Авторизация через Depends(get_current_user) не используем, чтобы не тянуть БД здесь.
    raise HTTPException(
        status_code=401,
        detail={"code": "ADMIN_TOKEN_REQUIRED", "message": "Admin token required"},
    )


def get_current_user(authorization: str | None = Header(default=None)):
    """
    Читает Bearer токен, проверяет подпись и exp.
    Возвращает dict с user_id и role, если ок. Иначе 401.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "Unauthorized"},
        )
    token = authorization.split(" ", 1)[1]
    data = verify_token(token)
    if not data or "user_id" not in data or "role" not in data:
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_TOKEN", "message": "Invalid token"},
        )
    return data


def require_admin(
    authorization: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None),
):
    """
    Разрешает доступ если:
    - задан ADMIN_TOKEN и заголовок X-Admin-Token совпадает
    - либо Bearer-токен с role=admin
    - если ADMIN_TOKEN пуст и Bearer нет — 401
    """
    admin_env = os.getenv("ADMIN_TOKEN", "")
    demo_mode = os.getenv("EYEGATE_DEMO_MODE", "0") == "1"
    provided = bool(x_admin_token) or bool(authorization)

    if demo_mode:
        return {"role": "admin", "method": "demo"}

    if not admin_env:
        return {"role": "admin", "method": "open"}
    if admin_env and x_admin_token == admin_env:
        return {"role": "admin", "method": "header"}
    # Bearer
    if authorization and authorization.lower().startswith("bearer "):
        data = verify_token(authorization.split(" ", 1)[1])
        if data and data.get("role") == "admin":
            return data
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Admin token invalid"},
        )
    if provided:
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Invalid admin credentials"},
        )
    raise HTTPException(
        status_code=401,
        detail={"code": "UNAUTHORIZED", "message": "Unauthorized"},
    )
