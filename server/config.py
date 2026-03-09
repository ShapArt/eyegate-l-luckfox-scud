from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv


def _load_env() -> None:
    """
    Load .env early, so every module sees the same environment.

    Order:
      1) EYEGATE_ENV_FILE (if provided)
      2) <repo_root>/.env
      3) fallback: whatever is already in process env
    """
    repo_root = Path(__file__).resolve().parents[1]
    env_file = os.getenv("EYEGATE_ENV_FILE", "").strip()
    candidate = Path(env_file) if env_file else (repo_root / ".env")
    if candidate.exists():
        load_dotenv(candidate, override=False)
    else:
        print(f"[env] .env not found, expected at {candidate}", file=sys.stderr)


def _is_wsl() -> bool:
    try:
        rel = os.uname().release.lower()
        return "microsoft" in rel or "wsl" in rel
    except Exception:
        return False


def _is_docker() -> bool:
    try:
        return Path("/.dockerenv").exists()
    except Exception:
        return False


def _detect_windows_host_ip() -> str:
    """
    Best-effort Windows host IP for WSL -> Windows service access (RTSP/Mediamtx).

    Typical WSL case:
      - Windows host is the default gateway from `ip route` inside WSL
      - or nameserver in /etc/resolv.conf
    """
    if not _is_wsl():
        return "127.0.0.1"

    # 1) ip route default via X.X.X.X
    try:
        out = subprocess.check_output(
            ["sh", "-lc", "ip route | awk '/^default/ {print $3; exit}'"],
            text=True,
        ).strip()
        if out and re.match(r"^\d+\.\d+\.\d+\.\d+$", out):
            return out
    except Exception:
        pass

    # 2) /etc/resolv.conf nameserver X.X.X.X
    try:
        with open("/etc/resolv.conf", "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith("nameserver"):
                    ip = line.split()[1].strip()
                    if re.match(r"^\d+\.\d+\.\d+\.\d+$", ip):
                        return ip
    except Exception:
        pass

    return "127.0.0.1"


_load_env()


@dataclass
class AppConfig:
    env: Literal["dev", "prod"] = "dev"
    host: str = "0.0.0.0"
    port: int = 8000
    use_dummy_hw: bool = True
    demo_mode: bool = False

    # Vision
    vision_mode: Literal["dummy", "real"] = "real"
    vision_match_threshold: float = 0.6
    vision_match_metric: str = "l2"
    vision_detection_score_threshold: float = 0.7
    vision_detection_model_path: str = "models/face_detection_yunet_2023mar.onnx"
    vision_recognition_model_path: str = "models/face_recognition_sface_2021dec.onnx"
    vision_auto_download: bool = False
    vision_stale_after_sec: float = 2.0
    vision_smooth_window: int = 5
    vision_smooth_hits: int = 3
    vision_smooth_ttl_frames: int = 2
    vision_smooth_score_jitter: float = 0.08
    vision_smooth_iou_threshold: float = 0.3
    # Back-compat: numeric webcam index (only used if VISION_CAMERA_SOURCE empty/invalid)
    vision_camera_index: int = 0
    # Preferred: RTSP / HTTP / file path / gstreamer pipeline / numeric index as string
    vision_camera_source: str = ""
    # OpenCV backend hint: "" (auto), "ffmpeg", "gstreamer"
    vision_camera_backend: str = ""
    vision_frame_width: int = 960
    vision_frame_height: int = 720
    camera_rtsp_url: str = "rtsp://127.0.0.1:8554/live/0"
    rtsp_transport: str = "tcp"
    ffmpeg_path: str = "ffmpeg"
    vision_rotate: int = 0  # 0/90/180/270
    vision_flip: Literal["none", "h", "v", "hv"] = "none"

    # Capture robustness
    vision_open_timeout_ms: int = 5000
    vision_read_timeout_ms: int = 2500
    vision_reconnect_backoff_ms: int = 200
    vision_reconnect_backoff_max_ms: int = 5000

    # Background/people
    bg_history: int = 200
    bg_var_threshold: float = 40.0
    people_min_area: int = 5000
    people_min_area_ratio: float = 0.015
    people_min_width_ratio: float = 0.06
    people_min_height_ratio: float = 0.18
    people_min_extent: float = 0.18
    people_min_aspect_ratio: float = 0.25
    people_max_aspect_ratio: float = 1.8
    people_border_margin_ratio: float = 0.02
    people_merge_margin_ratio: float = 0.02
    people_dominant_second_area_ratio: float = 0.35
    people_present_frames: int = 3
    people_absent_frames: int = 6

    # Doors
    door1_auto_close_ms: int = 0
    door2_auto_close_ms: int = 0
    sim_auto_close_ms: int = 0

    enter_timeout_sec: float = 15.0
    check_timeout_sec: float = 10.0
    exit_timeout_sec: float = 15.0
    alarm_timeout_sec: float = 60.0
    allow_multi_known: bool = False
    require_face_match_for_door2: bool = True
    max_people_allowed: int = 1
    door1_close_stabilize_ms: int = 1500
    room_check_samples: int = 5

    sensor_mode: Literal["sim", "serial"] = "sim"
    sensor_serial_port: str = ""
    sensor_serial_baud: int = 115200

    # Auth
    auth_auto_approve_registration: bool = True

    # Dev/demo
    vision_demo_fixed_login: str = ""


def load_config() -> AppConfig:
    cfg = AppConfig()

    def _env_bool(*names: str, default: bool = False) -> bool:
        for name in names:
            raw = os.getenv(name, "").strip()
            if raw:
                return raw.lower() in ("1", "true", "yes", "on")
        return default

    cfg.env = os.getenv("EYEGATE_ENV", os.getenv("ENV", cfg.env))
    cfg.host = os.getenv("EYEGATE_HOST", os.getenv("HOST", cfg.host))
    cfg.port = int(os.getenv("EYEGATE_PORT", os.getenv("PORT", str(cfg.port))))
    cfg.use_dummy_hw = _env_bool(
        "EYEGATE_DUMMY_HW",
        "USE_DUMMY_HW",
        default=cfg.use_dummy_hw,
    )
    cfg.demo_mode = _env_bool("EYEGATE_DEMO_MODE", default=cfg.demo_mode)

    cfg.vision_mode = os.getenv("VISION_MODE", cfg.vision_mode)
    if cfg.vision_mode not in ("dummy", "real"):
        cfg.vision_mode = "real"
    cfg.vision_match_threshold = float(
        os.getenv("VISION_MATCH_THRESHOLD", str(cfg.vision_match_threshold))
    )
    cfg.vision_match_metric = (
        os.getenv("VISION_MATCH_METRIC", cfg.vision_match_metric).strip().lower()
    )
    if cfg.vision_match_metric not in ("l2", "cosine"):
        cfg.vision_match_metric = "l2"

    # Prefer VISION_DET_SCORE (used in tests and earlier configs) over the alias VISION_DETECTOR_THRESHOLD.
    cfg.vision_detection_score_threshold = float(
        os.getenv(
            "VISION_DET_SCORE",
            os.getenv(
                "VISION_DETECTOR_THRESHOLD", str(cfg.vision_detection_score_threshold)
            ),
        )
    )
    cfg.vision_detection_model_path = os.getenv(
        "VISION_MODEL_DET", cfg.vision_detection_model_path
    ).strip()
    cfg.vision_recognition_model_path = os.getenv(
        "VISION_MODEL_REC", cfg.vision_recognition_model_path
    ).strip()
    cfg.vision_auto_download = _env_bool(
        "VISION_AUTO_DOWNLOAD", default=cfg.vision_auto_download
    )
    cfg.vision_stale_after_sec = float(
        os.getenv("VISION_TTL_SEC", str(cfg.vision_stale_after_sec))
    )
    cfg.vision_smooth_window = int(
        os.getenv("VISION_SMOOTH_WINDOW", str(cfg.vision_smooth_window))
    )
    cfg.vision_smooth_hits = int(
        os.getenv("VISION_SMOOTH_HITS", str(cfg.vision_smooth_hits))
    )
    cfg.vision_smooth_ttl_frames = int(
        os.getenv("VISION_SMOOTH_TTL", str(cfg.vision_smooth_ttl_frames))
    )
    cfg.vision_smooth_score_jitter = float(
        os.getenv("VISION_SMOOTH_SCORE_JITTER", str(cfg.vision_smooth_score_jitter))
    )
    cfg.vision_smooth_iou_threshold = float(
        os.getenv("VISION_SMOOTH_IOU_THRESHOLD", str(cfg.vision_smooth_iou_threshold))
    )
    cfg.vision_camera_index = int(
        os.getenv("VISION_CAMERA_INDEX", str(cfg.vision_camera_index))
    )
    cfg.vision_camera_backend = os.getenv(
        "VISION_CAMERA_BACKEND", cfg.vision_camera_backend
    ).strip()
    cfg.vision_frame_width = int(
        os.getenv("VISION_FRAME_WIDTH", str(cfg.vision_frame_width))
    )
    cfg.vision_frame_height = int(
        os.getenv("VISION_FRAME_HEIGHT", str(cfg.vision_frame_height))
    )
    cfg.rtsp_transport = (
        os.getenv("RTSP_TRANSPORT", cfg.rtsp_transport).strip().lower()
        or cfg.rtsp_transport
    )
    cfg.ffmpeg_path = (
        os.getenv("FFMPEG_PATH", cfg.ffmpeg_path).strip() or cfg.ffmpeg_path
    )
    repo_root = Path(__file__).resolve().parents[1]
    local_ffmpeg = repo_root / "tools" / "ffmpeg" / "ffmpeg"
    if cfg.ffmpeg_path == "ffmpeg" and local_ffmpeg.exists():
        cfg.ffmpeg_path = str(local_ffmpeg)

    raw_source = os.getenv("CAMERA_RTSP_URL", "").strip()
    source_from_env = bool(raw_source)
    if not raw_source:
        legacy_source = os.getenv("VISION_CAMERA_SOURCE", "").strip()
        if legacy_source:
            raw_source = legacy_source
            source_from_env = True
    if not raw_source:
        raw_source = cfg.camera_rtsp_url
        source_from_env = False

    windows_host = _detect_windows_host_ip()
    if "<WINDOWS_HOST>" in raw_source:
        raw_source = raw_source.replace("<WINDOWS_HOST>", windows_host)
    if not source_from_env and _is_wsl() and windows_host != "127.0.0.1":
        for host in ("127.0.0.1", "localhost", "0.0.0.0", "[::1]"):
            prefix = f"rtsp://{host}"
            if raw_source.startswith(prefix):
                rewritten = raw_source.replace(prefix, f"rtsp://{windows_host}", 1)
                print(
                    f"[env] CAMERA_RTSP_URL rewritten for WSL: {raw_source} -> {rewritten}",
                    file=sys.stderr,
                )
                raw_source = rewritten
                break
    if _is_docker() and raw_source.lower().startswith("rtsp://"):
        host_part = raw_source[7:].split("/", 1)[0]
        if "@" in host_part:
            host_part = host_part.split("@", 1)[1]
        host = host_part.split("]", 1)[0].lstrip("[")
        host = host.split(":", 1)[0]
        if host in ("127.0.0.1", "localhost", "0.0.0.0", "::1"):
            print(
                "[env] CAMERA_RTSP_URL points to localhost inside Docker; use host.docker.internal or host network.",
                file=sys.stderr,
            )
    cfg.vision_camera_source = raw_source
    cfg.camera_rtsp_url = raw_source

    try:
        cfg.vision_rotate = int(os.getenv("VISION_ROTATE", str(cfg.vision_rotate)))
    except Exception:
        cfg.vision_rotate = 0
    cfg.vision_rotate = (
        cfg.vision_rotate if cfg.vision_rotate in (0, 90, 180, 270) else 0
    )

    flip = os.getenv("VISION_FLIP", cfg.vision_flip).strip().lower()
    cfg.vision_flip = flip if flip in ("none", "h", "v", "hv") else "none"

    cfg.vision_open_timeout_ms = int(
        os.getenv("VISION_OPEN_TIMEOUT_MS", str(cfg.vision_open_timeout_ms))
    )
    cfg.vision_read_timeout_ms = int(
        os.getenv("VISION_READ_TIMEOUT_MS", str(cfg.vision_read_timeout_ms))
    )
    cfg.vision_reconnect_backoff_ms = int(
        os.getenv("VISION_RECONNECT_BACKOFF_MS", str(cfg.vision_reconnect_backoff_ms))
    )
    cfg.vision_reconnect_backoff_max_ms = int(
        os.getenv(
            "VISION_RECONNECT_BACKOFF_MAX_MS", str(cfg.vision_reconnect_backoff_max_ms)
        )
    )

    cfg.bg_history = int(os.getenv("BG_HISTORY", str(cfg.bg_history)))
    cfg.bg_var_threshold = float(
        os.getenv("BG_VAR_THRESHOLD", str(cfg.bg_var_threshold))
    )
    cfg.people_min_area = int(os.getenv("PEOPLE_MIN_AREA", str(cfg.people_min_area)))
    cfg.people_min_area_ratio = float(
        os.getenv("PEOPLE_MIN_AREA_RATIO", str(cfg.people_min_area_ratio))
    )
    cfg.people_min_width_ratio = float(
        os.getenv("PEOPLE_MIN_WIDTH_RATIO", str(cfg.people_min_width_ratio))
    )
    cfg.people_min_height_ratio = float(
        os.getenv("PEOPLE_MIN_HEIGHT_RATIO", str(cfg.people_min_height_ratio))
    )
    cfg.people_min_extent = float(
        os.getenv("PEOPLE_MIN_EXTENT", str(cfg.people_min_extent))
    )
    cfg.people_min_aspect_ratio = float(
        os.getenv("PEOPLE_MIN_ASPECT_RATIO", str(cfg.people_min_aspect_ratio))
    )
    cfg.people_max_aspect_ratio = float(
        os.getenv("PEOPLE_MAX_ASPECT_RATIO", str(cfg.people_max_aspect_ratio))
    )
    cfg.people_border_margin_ratio = float(
        os.getenv("PEOPLE_BORDER_MARGIN_RATIO", str(cfg.people_border_margin_ratio))
    )
    cfg.people_merge_margin_ratio = float(
        os.getenv("PEOPLE_MERGE_MARGIN_RATIO", str(cfg.people_merge_margin_ratio))
    )
    cfg.people_dominant_second_area_ratio = float(
        os.getenv(
            "PEOPLE_DOMINANT_SECOND_AREA_RATIO",
            str(cfg.people_dominant_second_area_ratio),
        )
    )
    cfg.people_present_frames = int(
        os.getenv("PEOPLE_PRESENT_FRAMES", str(cfg.people_present_frames))
    )
    cfg.people_absent_frames = int(
        os.getenv("PEOPLE_ABSENT_FRAMES", str(cfg.people_absent_frames))
    )

    cfg.vision_demo_fixed_login = os.getenv("VISION_DEMO_FIXED_LOGIN", "").strip()

    def _sec_to_ms(env_name: str, default: str) -> int:
        try:
            return int(float(os.getenv(env_name, default)) * 1000)
        except Exception:
            return 0

    common_auto_close_ms = _sec_to_ms("DOOR_AUTO_CLOSE_SEC", "0")
    cfg.door1_auto_close_ms = (
        _sec_to_ms("DOOR1_AUTO_CLOSE_SEC", "0") or common_auto_close_ms
    )
    cfg.door2_auto_close_ms = (
        _sec_to_ms("DOOR2_AUTO_CLOSE_SEC", "0") or common_auto_close_ms
    )

    legacy_sim_auto_close = int(os.getenv("SIM_AUTO_CLOSE_MS", "0"))
    if (
        legacy_sim_auto_close > 0
        and common_auto_close_ms == 0
        and cfg.door1_auto_close_ms == 0
        and cfg.door2_auto_close_ms == 0
    ):
        cfg.door1_auto_close_ms = cfg.door2_auto_close_ms = legacy_sim_auto_close
    cfg.sim_auto_close_ms = legacy_sim_auto_close

    cfg.enter_timeout_sec = float(
        os.getenv("EYEGATE_ENTER_TIMEOUT", str(cfg.enter_timeout_sec))
    )
    cfg.check_timeout_sec = float(
        os.getenv("EYEGATE_CHECK_TIMEOUT", str(cfg.check_timeout_sec))
    )
    cfg.exit_timeout_sec = float(
        os.getenv("EYEGATE_EXIT_TIMEOUT", str(cfg.exit_timeout_sec))
    )
    cfg.alarm_timeout_sec = float(
        os.getenv("EYEGATE_ALARM_TIMEOUT", str(cfg.alarm_timeout_sec))
    )
    cfg.allow_multi_known = _env_bool(
        "ALLOW_MULTI_KNOWN", default=cfg.allow_multi_known
    )
    cfg.require_face_match_for_door2 = _env_bool(
        "REQUIRE_FACE_MATCH_FOR_DOOR2",
        default=cfg.require_face_match_for_door2,
    )
    cfg.max_people_allowed = int(
        os.getenv("MAX_PEOPLE_ALLOWED", str(cfg.max_people_allowed))
    )
    cfg.door1_close_stabilize_ms = int(
        os.getenv("DOOR1_CLOSE_STABILIZE_MS", str(cfg.door1_close_stabilize_ms))
    )
    cfg.room_check_samples = int(
        os.getenv("ROOM_CHECK_SAMPLES", str(cfg.room_check_samples))
    )

    sensor_mode = os.getenv("SENSOR_MODE", cfg.sensor_mode).strip().lower()
    if sensor_mode not in ("sim", "serial"):
        sensor_mode = "sim"
    cfg.sensor_mode = sensor_mode
    cfg.sensor_serial_port = os.getenv("SENSOR_SERIAL_PORT", "").strip()
    cfg.sensor_serial_baud = int(
        os.getenv("SENSOR_SERIAL_BAUD", str(cfg.sensor_serial_baud))
    )

    cfg.auth_auto_approve_registration = _env_bool(
        "AUTH_AUTO_APPROVE_REGISTRATION",
        "AUTO_APPROVE_REGISTRATION",
        default=cfg.auth_auto_approve_registration,
    )

    return cfg
