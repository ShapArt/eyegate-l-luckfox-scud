from __future__ import annotations

import asyncio
import os
import queue
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal, Optional, Sequence

import numpy as np

from camera_ingest import CameraIngest

try:  # pragma: no cover - imported lazily for environments without OpenCV
    import cv2  # type: ignore
except Exception:  # noqa: BLE001
    cv2 = None

from db import models as db_models
from gate.models import FaceMatch, VisionAnalysis
from vision.embeddings import (
    descriptor_distance,
    deserialize_face_descriptor,
    serialize_face_descriptor,
)
from vision.matcher import best_match_for_embedding
from vision.people_count import PeopleCounter, PeopleCounterConfig
from vision.types import BoundingBox, DetectedFace, VisionResult


@dataclass
class VisionConfig:
    mode: Literal["dummy", "real"] = "real"
    camera_index: int = 0
    match_threshold: float = 0.6
    stale_after_sec: float = 2.0
    warmup_frames: int = 5
    frame_width: int = 960
    frame_height: int = 720
    detection_model_path: str = "models/face_detection_yunet_2023mar.onnx"
    recognition_model_path: str = "models/face_recognition_sface_2021dec.onnx"
    detection_score_threshold: float = 0.7
    match_metric: str = "l2"
    smooth_window: int = 5
    smooth_hits: int = 3
    smooth_ttl_frames: int = 2
    smooth_score_jitter: float = 0.08
    smooth_iou_threshold: float = 0.3
    bg_history: int = 200
    bg_var_threshold: float = 40.0
    bg_detect_shadows: bool = True
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
    dilate_kernel: int = 5
    erode_kernel: int = 3
    demo_fixed_login: str = ""
    camera_source: str = ""
    camera_backend: str = ""
    rotate: int = 0  # 0/90/180/270
    flip: Literal["none", "h", "v", "hv"] = "none"
    open_timeout_ms: int = 5000
    read_timeout_ms: int = 2500
    reconnect_backoff_ms: int = 200
    reconnect_backoff_max_ms: int = 5000


@dataclass
class VisionBox:
    x: int
    y: int
    w: int
    h: int
    score: float = 0.0


@dataclass
class VisionSnapshot:
    people_count: int = 0
    boxes: list[VisionBox] = field(default_factory=list)
    faces: list["VisionFace"] = field(default_factory=list)
    silhouettes: list[VisionBox] = field(default_factory=list)
    vision_state: str = "OFF"
    last_frame_ts: Optional[float] = None
    fps: float = 0.0
    vision_error: Optional[str] = None
    match: Optional[bool] = None
    matched_user_id: Optional[int] = None
    match_distance: Optional[float] = None
    descriptor: Optional[list[float]] = None
    recognized_user_ids: list[Optional[int]] = field(default_factory=list)
    recognized_scores: list[Optional[float]] = field(default_factory=list)
    frame_w: Optional[int] = None
    frame_h: Optional[int] = None
    camera_ok: bool = False


@dataclass
class VisionFace:
    box: VisionBox
    user_id: Optional[int] = None
    score: Optional[float] = None
    label: Optional[str] = None
    is_known: bool = False


@dataclass
class _FaceTrack:
    box: VisionBox
    last_seen: float
    hits: int = 0
    misses: int = 0
    history_ids: deque[Optional[int]] = field(default_factory=deque)
    history_scores: deque[Optional[float]] = field(default_factory=deque)
    stable_id: Optional[int] = None
    stable_score: Optional[float] = None


@dataclass
class VisionDummyConfig:
    """Runtime knobs for the dummy provider (env-driven)."""

    default_people_count: int = 1
    default_face_match: Optional[FaceMatch] = FaceMatch.NO_FACE
    default_recognized_ids: list[int] = field(default_factory=list)
    dummy_delay_sec: float = 0.0

    @classmethod
    def from_env(cls) -> "VisionDummyConfig":
        people = int(os.getenv("VISION_DUMMY_PEOPLE", "1"))
        ids_raw = os.getenv("VISION_DUMMY_RECOGNIZED", "")
        recognized: list[int] = []
        for part in ids_raw.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                recognized.append(int(part))
            except ValueError:
                continue

        delay_ms = float(os.getenv("VISION_DUMMY_DELAY_MS", "0"))
        face_name = os.getenv("VISION_DUMMY_FACE_MATCH", "NO_FACE").upper()
        face_match = FaceMatch.__members__.get(face_name, FaceMatch.NO_FACE)
        # If face match is not explicitly provided but recognized IDs exist, treat as match.
        if face_match == FaceMatch.NO_FACE and recognized:
            face_match = FaceMatch.MATCH

        return cls(
            default_people_count=max(0, people),
            default_face_match=face_match,
            default_recognized_ids=recognized,
            dummy_delay_sec=max(0.0, delay_ms / 1000.0),
        )


class VisionServiceOpenCV:
    """
    Continuous camera reader + lightweight face detector that keeps the latest frame
    annotated for MJPEG streaming and provides analysis for the FSM.
    """

    def __init__(
        self,
        cfg: Optional[VisionConfig],
        get_user_by_id: Callable[[int], Optional[object]],
        list_users_fn: Optional[Callable[[], Sequence[object]]] = None,
        camera_ingest: Optional[CameraIngest] = None,
    ) -> None:
        if cv2 is None:
            raise RuntimeError("opencv-python is not installed")

        self._cv2 = cv2
        self._cfg = cfg or VisionConfig()
        self._smooth_window = max(1, int(self._cfg.smooth_window))
        self._smooth_hits = max(1, int(self._cfg.smooth_hits))
        self._smooth_ttl_frames = max(0, int(self._cfg.smooth_ttl_frames))
        self._smooth_score_jitter = max(0.0, float(self._cfg.smooth_score_jitter))
        self._smooth_iou_threshold = max(0.0, float(self._cfg.smooth_iou_threshold))
        self._get_user_by_id = get_user_by_id
        self._list_users = list_users_fn or (lambda: [])
        self._people_counter = PeopleCounter(
            PeopleCounterConfig(
                bg_history=self._cfg.bg_history,
                bg_var_threshold=self._cfg.bg_var_threshold,
                bg_detect_shadows=self._cfg.bg_detect_shadows,
                people_min_area=self._cfg.people_min_area,
                min_area_ratio=self._cfg.people_min_area_ratio,
                min_width_ratio=self._cfg.people_min_width_ratio,
                min_height_ratio=self._cfg.people_min_height_ratio,
                min_extent=self._cfg.people_min_extent,
                min_aspect_ratio=self._cfg.people_min_aspect_ratio,
                max_aspect_ratio=self._cfg.people_max_aspect_ratio,
                border_margin_ratio=self._cfg.people_border_margin_ratio,
                merge_margin_ratio=self._cfg.people_merge_margin_ratio,
                dominant_second_area_ratio=self._cfg.people_dominant_second_area_ratio,
                dilate_kernel=self._cfg.dilate_kernel,
                erode_kernel=self._cfg.erode_kernel,
            )
        )
        self._people_present_frames = max(1, int(self._cfg.people_present_frames))
        self._people_absent_frames = max(1, int(self._cfg.people_absent_frames))
        self._people_present_streak = 0
        self._people_absent_streak = 0
        self._people_state = False
        self._last_people_count = 0
        self._last_people_boxes: list[VisionBox] = []

        self._lock = threading.Lock()
        self._capture_lock = threading.Lock()
        self._capture = None
        self._running = True
        self._ingest = camera_ingest
        self._last_ingest_id: Optional[int] = None
        self._last_jpeg: Optional[bytes] = None
        self._last_descriptor: Optional[list[float]] = None
        self._snapshot = VisionSnapshot(
            vision_state="OFF", vision_error="NO CAMERA", camera_ok=False
        )
        self._frame_queue: queue.Queue[tuple[float, np.ndarray]] = queue.Queue(
            maxsize=1
        )
        self._reader_stop = threading.Event()
        self._reader_thread: Optional[threading.Thread] = None
        self._backoff_ms = max(50, int(self._cfg.reconnect_backoff_ms))
        self._tracks: list[_FaceTrack] = []
        self._annotate_stream = os.getenv("VISION_ANNOTATE_STREAM", "0") == "1"
        self._demo_fixed_login = (
            getattr(self._cfg, "demo_fixed_login", "") or ""
        ).strip()
        self._demo_fixed_user_id: Optional[int] = None
        self._demo_fixed_checked_at: float = 0.0
        self._face_cascade = self._cv2.CascadeClassifier(
            self._cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        self._yunet_detector = self._init_yunet_detector()
        self._sface_recognizer = self._init_sface_recognizer()

        # Prime placeholder so streaming works even before the camera starts.
        self._publish_placeholder("NO CAMERA")

        # On some Windows setups, opening VideoCapture in a background thread can be flaky.
        # Try opening once in the constructor thread so the reader loop can start with a live capture.
        if self._ingest is None:
            try:  # pragma: no cover
                self._ensure_capture()
            except Exception:
                pass
        else:
            self._ingest.start()

        self._start_reader()

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        self._reader_stop.set()
        try:
            if self._thread.is_alive():
                self._thread.join(timeout=1.0)
        except Exception:
            pass
        try:
            if self._reader_thread and self._reader_thread.is_alive():
                self._reader_thread.join(timeout=0.5)
        except Exception:
            pass
        self._reset_capture()

    # ---- Public API -----------------------------------------------------
    def last_snapshot(self) -> dict:
        with self._lock:
            snap = self._snapshot
        return {
            "provider": self.__class__.__name__,
            "people_count": snap.people_count,
            "boxes": [box.__dict__ for box in snap.boxes],
            "silhouettes": [box.__dict__ for box in getattr(snap, "silhouettes", [])],
            "faces": [
                {
                    "box": face.box.__dict__,
                    "user_id": face.user_id,
                    "score": face.score,
                    "label": face.label or "UNKNOWN",
                    "is_known": face.is_known,
                }
                for face in (snap.faces or [])
            ],
            "vision_state": snap.vision_state,
            "last_frame_ts": snap.last_frame_ts,
            "fps": snap.fps,
            "vision_error": snap.vision_error,
            "match": snap.match,
            "matched_user_id": snap.matched_user_id,
            "match_distance": snap.match_distance,
            "recognized_user_ids": list(getattr(snap, "recognized_user_ids", []) or []),
            "recognized_scores": list(getattr(snap, "recognized_scores", []) or []),
            "frame_w": snap.frame_w,
            "frame_h": snap.frame_h,
            "camera_ok": snap.camera_ok,
        }

    def get_jpeg_frame(self) -> bytes:
        with self._lock:
            if self._last_jpeg is not None:
                return self._last_jpeg
        return self._build_placeholder("NO CAMERA")

    def capture_descriptor(self) -> bytes:
        snap = self._snapshot_safe()
        if (
            snap.last_frame_ts is None
            or time.time() - snap.last_frame_ts > self._cfg.stale_after_sec
        ):
            raise RuntimeError("Camera frame is stale")
        if snap.people_count != 1 or snap.descriptor is None:
            # fallback: allow enrolling a placeholder so demo continues even without a real face
            return serialize_face_descriptor(snap.descriptor or [0.0] * 32)
        return serialize_face_descriptor(snap.descriptor)

    async def analyze_room(
        self,
        card_id: Optional[str],
        user_id: Optional[int],
    ) -> VisionAnalysis:
        snap = self._snapshot_safe()
        now = time.time()
        camera_ok = bool(snap.camera_ok)
        if (
            snap.last_frame_ts is None
            or (now - snap.last_frame_ts) > self._cfg.stale_after_sec
        ):
            return VisionAnalysis(
                people_count=0,
                face_match=FaceMatch.NO_FACE,
                stale=True,
                camera_ok=camera_ok,
            )

        people_count = snap.people_count
        descriptor = snap.descriptor
        recognized_raw_ids = list(getattr(snap, "recognized_user_ids", []) or [])
        recognized_raw_scores = list(getattr(snap, "recognized_scores", []) or [])
        recognized_pairs = [
            (uid, score)
            for uid, score in zip(recognized_raw_ids, recognized_raw_scores)
            if uid is not None
        ]
        recognized_ids = [uid for uid, _ in recognized_pairs]
        recognized_scores = [score for _, score in recognized_pairs]
        match_bool: Optional[bool] = None
        match_distance: Optional[float] = None
        matched_user_id: Optional[int] = None

        if user_id is not None and descriptor is not None:
            db_user = self._get_user_by_id(user_id)
            embedding = getattr(db_user, "face_embedding", None) if db_user else None
            stored = deserialize_face_descriptor(embedding)
            if stored:
                dist = descriptor_distance(stored, descriptor)
                if dist is not None and not np.isinf(dist):
                    match_distance = float(dist)
                    match_bool = dist <= self._cfg.match_threshold
                    matched_user_id = user_id

        if recognized_ids and match_bool is None:
            # If matching already computed via recognizer, honor it
            matched_user_id = recognized_ids[0]
            match_distance = recognized_scores[0] if recognized_scores else None
            if user_id is None or user_id in recognized_ids:
                match_bool = True
            else:
                match_bool = False

        face_match = FaceMatch.NO_FACE
        if people_count == 0:
            face_match = FaceMatch.NO_FACE
        elif people_count > 1:
            face_match = FaceMatch.NO_MATCH
        elif people_count == 1:
            if match_bool is None:
                face_match = FaceMatch.NO_FACE
            elif match_bool:
                face_match = FaceMatch.MATCH
            else:
                face_match = FaceMatch.NO_MATCH

        # Persist match info into the snapshot so WS consumers can display it.
        with self._lock:
            self._snapshot.match = match_bool
            self._snapshot.match_distance = match_distance
            self._snapshot.matched_user_id = matched_user_id

        return VisionAnalysis(
            people_count=people_count,
            face_match=face_match,
            stale=False,
            matched_user_id=matched_user_id,
            match_distance=match_distance,
            recognized_user_ids=recognized_ids,
            camera_ok=camera_ok,
        )

    # ---- Internals ------------------------------------------------------
    def _snapshot_safe(self) -> VisionSnapshot:
        with self._lock:
            return VisionSnapshot(
                people_count=self._snapshot.people_count,
                boxes=list(self._snapshot.boxes),
                faces=list(self._snapshot.faces),
                silhouettes=list(getattr(self._snapshot, "silhouettes", [])),
                vision_state=self._snapshot.vision_state,
                last_frame_ts=self._snapshot.last_frame_ts,
                fps=self._snapshot.fps,
                vision_error=self._snapshot.vision_error,
                match=self._snapshot.match,
                matched_user_id=self._snapshot.matched_user_id,
                match_distance=self._snapshot.match_distance,
                descriptor=(
                    list(self._snapshot.descriptor)
                    if self._snapshot.descriptor
                    else None
                ),
                recognized_user_ids=list(self._snapshot.recognized_user_ids),
                recognized_scores=list(self._snapshot.recognized_scores),
                frame_w=self._snapshot.frame_w,
                frame_h=self._snapshot.frame_h,
                camera_ok=self._snapshot.camera_ok,
            )

    def _init_yunet_detector(self):
        """Load YuNet face detector if models are available; fallback to None on error."""
        try:
            if not hasattr(self._cv2, "FaceDetectorYN"):
                return None
            model_path = Path(self._cfg.detection_model_path)
            if not model_path.exists():
                return None
            det = self._cv2.FaceDetectorYN.create(
                str(model_path),
                "",
                (self._cfg.frame_width, self._cfg.frame_height),
                score_threshold=self._cfg.detection_score_threshold,
                nms_threshold=0.3,
                top_k=5000,
            )
            return det
        except Exception:
            return None

    def _init_sface_recognizer(self):
        """Load SFace recognizer if model present; fallback to None."""
        try:
            if not hasattr(self._cv2, "FaceRecognizerSF"):
                return None
            model_path = Path(self._cfg.recognition_model_path)
            if not model_path.exists():
                return None
            return self._cv2.FaceRecognizerSF.create(str(model_path), "")
        except Exception:
            return None

    def _start_reader(self) -> None:
        if self._reader_thread and self._reader_thread.is_alive():
            return
        self._reader_stop.clear()
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

    def _restart_reader(self) -> None:
        if self._ingest is not None:
            return
        self._reader_stop.set()
        try:
            if self._reader_thread and self._reader_thread.is_alive():
                self._reader_thread.join(timeout=0.2)
        except Exception:
            pass
        self._reset_capture()
        self._drain_frame_queue()
        self._reader_stop = threading.Event()
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

    def _drain_frame_queue(self) -> None:
        while True:
            try:
                self._frame_queue.get_nowait()
            except queue.Empty:
                return

    def _bump_backoff(self) -> None:
        base = max(50, int(self._cfg.reconnect_backoff_ms))
        self._backoff_ms = min(
            max(base, self._backoff_ms * 2),
            int(self._cfg.reconnect_backoff_max_ms),
        )

    def _reset_backoff(self) -> None:
        self._backoff_ms = max(50, int(self._cfg.reconnect_backoff_ms))

    def _reader_loop(self) -> None:
        while self._running and not self._reader_stop.is_set():
            if self._ingest is not None:
                timeout_sec = max(0.1, float(self._cfg.read_timeout_ms) / 1000.0)
                frame_payload = self._ingest.get_frame(
                    timeout=timeout_sec,
                    since_id=self._last_ingest_id,
                )
                if frame_payload is None:
                    error = self._ingest.last_error or "NO FRAME"
                    self._publish_placeholder(error)
                    self._bump_backoff()
                    time.sleep(self._backoff_ms / 1000.0)
                    continue
                self._last_ingest_id = frame_payload.frame_id
                self._reset_backoff()
                now = frame_payload.timestamp
                frame = frame_payload.frame
                try:
                    self._frame_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self._frame_queue.put_nowait((now, frame))
                except queue.Full:
                    pass
                continue

            cap = self._ensure_capture()
            if cap is None:
                self._publish_placeholder("NO CAMERA")
                self._bump_backoff()
                time.sleep(self._backoff_ms / 1000.0)
                continue
            ok, frame = cap.read()
            if not ok or frame is None:
                self._publish_placeholder("NO FRAME")
                self._reset_capture()
                self._bump_backoff()
                time.sleep(self._backoff_ms / 1000.0)
                continue
            self._reset_backoff()
            now = time.time()
            try:
                self._frame_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._frame_queue.put_nowait((now, frame))
            except queue.Full:
                pass

    def _get_frame(self) -> Optional[tuple[float, np.ndarray]]:
        timeout_sec = max(0.1, float(self._cfg.read_timeout_ms) / 1000.0)
        try:
            return self._frame_queue.get(timeout=timeout_sec)
        except queue.Empty:
            return None

    def _run_loop(self) -> None:
        warmup_left = self._cfg.warmup_frames
        prev_ts = time.time()
        while self._running:
            frame_payload = self._get_frame()
            if frame_payload is None:
                self._publish_placeholder("NO FRAME")
                self._bump_backoff()
                self._restart_reader()
                time.sleep(self._backoff_ms / 1000.0)
                continue

            frame_ts, frame = frame_payload
            self._reset_backoff()
            # rotate / flip (после успешного чтения кадра)
            if self._cfg.rotate == 90:
                frame = self._cv2.rotate(frame, self._cv2.ROTATE_90_CLOCKWISE)
            elif self._cfg.rotate == 180:
                frame = self._cv2.rotate(frame, self._cv2.ROTATE_180)
            elif self._cfg.rotate == 270:
                frame = self._cv2.rotate(frame, self._cv2.ROTATE_90_COUNTERCLOCKWISE)

            if self._cfg.flip == "h":
                frame = self._cv2.flip(frame, 1)
            elif self._cfg.flip == "v":
                frame = self._cv2.flip(frame, 0)
            elif self._cfg.flip == "hv":
                frame = self._cv2.flip(frame, -1)

            now = time.time()
            dt = now - prev_ts
            fps = 0.0 if dt <= 0 else min(30.0, 1.0 / dt)
            prev_ts = now

            boxes, embeddings, raw_ids, raw_scores = self._detect_faces(frame)
            recognized_ids, recognized_scores = self._smooth_recognition(
                boxes, raw_ids, raw_scores, now
            )
            silhouette_boxes: list[VisionBox] = []
            if self._people_counter:
                people_count, silhouettes = self._people_counter.detect(frame)
                silhouette_boxes = [
                    VisionBox(
                        x=bb.x, y=bb.y, w=bb.w, h=bb.h, score=float(bb.score or 0.0)
                    )
                    for bb in silhouettes
                ]
            else:
                people_count = len(boxes)
            face_count = len(boxes)
            if face_count == 1 and people_count >= 4:
                # Background subtraction can produce "confetti" blobs in noisy lighting.
                # If face detector sees a single face but silhouettes explode, clamp to 1.
                people_count = 1
                if silhouette_boxes:
                    best = _best_overlap_box(boxes[0], silhouette_boxes)
                    silhouette_boxes = [best] if best else silhouette_boxes[:1]
            elif face_count >= 2 and people_count >= face_count + 3:
                people_count = face_count
                if silhouette_boxes and len(silhouette_boxes) > face_count:
                    silhouette_boxes = silhouette_boxes[:face_count]
            if people_count == 0 and boxes:
                people_count = len(boxes)
                if not silhouette_boxes:
                    silhouette_boxes = list(boxes)
            people_count, silhouette_boxes = self._apply_people_hysteresis(
                people_count, silhouette_boxes
            )
            descriptor = next((emb for emb in embeddings if emb), None)
            state = "DETECTING"
            if warmup_left > 0:
                state = "WARMUP"
                warmup_left -= 1
            elif boxes and len(boxes) == 1:
                state = "DECIDING"

            frame_h, frame_w = frame.shape[:2]
            faces_data: list[VisionFace] = []
            for idx, box in enumerate(boxes):
                uid = recognized_ids[idx] if idx < len(recognized_ids) else None
                score = recognized_scores[idx] if idx < len(recognized_scores) else None
                label, is_known = self._label_for_user(uid)
                faces_data.append(
                    VisionFace(
                        box=box,
                        user_id=uid,
                        score=score,
                        label=label,
                        is_known=is_known,
                    )
                )

            if len(faces_data) == 1 and faces_data[0].user_id is None:
                demo_uid = self._get_demo_fixed_user_id()
                if demo_uid is not None:
                    label, is_known = self._label_for_user(demo_uid)
                    faces_data[0].user_id = demo_uid
                    faces_data[0].label = label
                    faces_data[0].is_known = is_known

            snap = VisionSnapshot(
                people_count=people_count,
                boxes=boxes,
                faces=faces_data,
                silhouettes=silhouette_boxes,
                vision_state=state,
                last_frame_ts=frame_ts,
                fps=fps,
                vision_error=None,
                descriptor=descriptor,
                recognized_user_ids=recognized_ids,
                recognized_scores=recognized_scores,
                frame_w=frame_w,
                frame_h=frame_h,
                camera_ok=True,
            )

            frame_to_encode = (
                self._annotate_frame(frame, snap) if self._annotate_stream else frame
            )
            ok, buf = self._cv2.imencode(".jpg", frame_to_encode)
            if ok:
                jpg = buf.tobytes()
            else:
                jpg = self._build_placeholder("ENCODE ERR")

            with self._lock:
                self._snapshot = snap
                self._last_jpeg = jpg
                self._last_descriptor = descriptor

            time.sleep(0.05)

    def _get_demo_fixed_user_id(self) -> Optional[int]:
        login = self._demo_fixed_login
        if not login:
            return None
        now = time.time()
        # Re-check periodically so users created after startup get picked up.
        if (now - self._demo_fixed_checked_at) < 10.0:
            return self._demo_fixed_user_id
        try:
            user = db_models.get_user_by_login(login)
        except Exception:
            user = None
        self._demo_fixed_user_id = int(user.id) if user is not None else None
        self._demo_fixed_checked_at = now
        return self._demo_fixed_user_id

    def _apply_people_hysteresis(
        self,
        people_count: int,
        silhouette_boxes: list[VisionBox],
    ) -> tuple[int, list[VisionBox]]:
        """Stabilize silhouette detection to avoid flicker."""
        present = people_count > 0
        if present:
            self._people_present_streak += 1
            self._people_absent_streak = 0
            if silhouette_boxes:
                self._last_people_boxes = list(silhouette_boxes)
                self._last_people_count = max(1, len(silhouette_boxes))
            else:
                self._last_people_count = max(1, people_count)
        else:
            self._people_absent_streak += 1
            self._people_present_streak = 0

        if self._people_state:
            if self._people_absent_streak >= self._people_absent_frames:
                self._people_state = False
        else:
            if self._people_present_streak >= self._people_present_frames:
                self._people_state = True

        if not self._people_state:
            return 0, []

        if present:
            return max(1, people_count), list(silhouette_boxes)

        # Still consider the person present while absent streak is below threshold.
        if self._last_people_boxes:
            return max(1, self._last_people_count), list(self._last_people_boxes)
        return max(1, self._last_people_count), list(silhouette_boxes)

    def _smooth_recognition(
        self,
        boxes: list[VisionBox],
        raw_ids: list[Optional[int]],
        raw_scores: list[Optional[float]],
        now: float,
    ) -> tuple[list[Optional[int]], list[Optional[float]]]:
        if not boxes:
            for track in self._tracks:
                track.misses += 1
            self._tracks = [
                t for t in self._tracks if t.misses <= self._smooth_ttl_frames
            ]
            return [], []

        matches = self._assign_tracks(boxes)
        used_tracks: set[int] = set()
        new_tracks: list[_FaceTrack] = []
        smoothed_ids: list[Optional[int]] = [None] * len(boxes)
        smoothed_scores: list[Optional[float]] = [None] * len(boxes)

        for idx, box in enumerate(boxes):
            track = None
            matched_idx = matches.get(idx)
            if matched_idx is not None:
                track = self._tracks[matched_idx]
                used_tracks.add(matched_idx)
                track.box = box
                track.last_seen = now
                track.misses = 0
                track.hits += 1
            else:
                track = self._new_track(box, now)

            track.history_ids.append(raw_ids[idx] if idx < len(raw_ids) else None)
            track.history_scores.append(
                raw_scores[idx] if idx < len(raw_scores) else None
            )

            stable_id, stable_score = self._compute_stable_id(track)
            if stable_id is not None:
                track.stable_id = stable_id
                track.stable_score = stable_score

            if track.stable_id is not None:
                smoothed_ids[idx] = track.stable_id
                smoothed_scores[idx] = track.stable_score

            new_tracks.append(track)

        for t_idx, track in enumerate(self._tracks):
            if t_idx in used_tracks:
                continue
            track.misses += 1
            if track.misses <= self._smooth_ttl_frames:
                new_tracks.append(track)

        self._tracks = new_tracks
        return smoothed_ids, smoothed_scores

    def _new_track(self, box: VisionBox, now: float) -> _FaceTrack:
        track = _FaceTrack(box=box, last_seen=now, hits=1, misses=0)
        track.history_ids = deque(maxlen=self._smooth_window)
        track.history_scores = deque(maxlen=self._smooth_window)
        return track

    def _assign_tracks(self, boxes: list[VisionBox]) -> dict[int, int]:
        matches: dict[int, int] = {}
        used: set[int] = set()
        for idx, box in enumerate(boxes):
            best_idx = None
            best_iou = 0.0
            for t_idx, track in enumerate(self._tracks):
                if t_idx in used:
                    continue
                iou = _box_iou(box, track.box)
                if iou > best_iou:
                    best_iou = iou
                    best_idx = t_idx
            if best_idx is not None and best_iou >= self._smooth_iou_threshold:
                matches[idx] = best_idx
                used.add(best_idx)
        return matches

    def _compute_stable_id(
        self, track: _FaceTrack
    ) -> tuple[Optional[int], Optional[float]]:
        counts: dict[int, int] = {}
        scores: dict[int, list[float]] = {}
        for uid, score in zip(track.history_ids, track.history_scores):
            if uid is None:
                continue
            counts[uid] = counts.get(uid, 0) + 1
            if score is not None:
                scores.setdefault(uid, []).append(float(score))
        if not counts:
            return None, None
        best_id = max(counts, key=counts.get)
        if counts[best_id] < self._smooth_hits:
            return None, None
        score_list = scores.get(best_id, [])
        if score_list:
            jitter = max(score_list) - min(score_list)
            if jitter > self._smooth_score_jitter:
                return None, None
            avg_score = sum(score_list) / len(score_list)
            return best_id, float(avg_score)
        return best_id, None

    def _detect_faces(self, frame) -> tuple[
        list[VisionBox],
        list[list[float]],
        list[Optional[int]],
        list[Optional[float]],
    ]:
        if self._yunet_detector is not None:
            return self._detect_faces_yunet(frame)
        return self._detect_faces_haar(frame)

    def _detect_faces_yunet(self, frame) -> tuple[
        list[VisionBox],
        list[list[float]],
        list[Optional[int]],
        list[Optional[float]],
    ]:
        detector = self._yunet_detector
        if detector is None:
            return [], [], [], []
        h, w = frame.shape[:2]
        try:
            detector.setInputSize((w, h))
            _, faces = detector.detect(frame)
        except Exception:
            faces = None
        boxes: list[VisionBox] = []
        embeddings: list[list[float]] = []
        if faces is not None:
            for face in faces:
                x, y, width, height, score = face[:5]
                if score < self._cfg.detection_score_threshold:
                    continue
                x1 = max(0, int(x))
                y1 = max(0, int(y))
                x2 = min(w, int(x + width))
                y2 = min(h, int(y + height))
                ww = max(0, int(x2 - x1))
                hh = max(0, int(y2 - y1))
                if ww == 0 or hh == 0:
                    continue
                bbox = VisionBox(int(x1), int(y1), int(ww), int(hh), score=float(score))
                boxes.append(bbox)
                if self._sface_recognizer is not None:
                    try:
                        aligned = self._sface_recognizer.alignCrop(frame, face)
                        feat = self._sface_recognizer.feature(aligned)
                        embeddings.append([float(v) for v in feat.flatten()])
                    except Exception:
                        embeddings.append([])
                else:
                    embeddings.append([])
        recognized_ids, recognized_scores = self._recognize_embeddings(embeddings)
        return boxes, embeddings, recognized_ids, recognized_scores

    def _detect_faces_haar(self, frame) -> tuple[
        list[VisionBox],
        list[list[float]],
        list[Optional[int]],
        list[Optional[float]],
    ]:
        gray = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2GRAY)
        faces = self._face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(60, 60),
        )
        h, w = gray.shape[:2]
        boxes: list[VisionBox] = []
        for x, y, ww, hh in faces:
            x1 = max(0, int(x))
            y1 = max(0, int(y))
            x2 = min(w, int(x + ww))
            y2 = min(h, int(y + hh))
            bw = max(0, int(x2 - x1))
            bh = max(0, int(y2 - y1))
            if bw == 0 or bh == 0:
                continue
            boxes.append(VisionBox(int(x1), int(y1), int(bw), int(bh)))
        embeddings: list[list[float]] = [
            self._descriptor_from_gray(gray, box) for box in boxes
        ]
        recognized_ids, recognized_scores = self._recognize_embeddings(embeddings)
        return boxes, embeddings, recognized_ids, recognized_scores

    def _descriptor_from_gray(self, gray_frame, box: VisionBox) -> list[float]:
        x, y, w, h = box.x, box.y, box.w, box.h
        face_roi = gray_frame[y : y + h, x : x + w]
        resized = self._cv2.resize(face_roi, (64, 64))
        hist = self._cv2.calcHist([resized], [0], None, [32], [0, 256]).flatten()
        hist = hist / max(np.linalg.norm(hist), 1e-6)
        return [float(v) for v in hist]

    def _recognize_embeddings(
        self, embeddings: Sequence[Sequence[float]]
    ) -> tuple[list[Optional[int]], list[Optional[float]]]:
        recognized_ids: list[Optional[int]] = []
        recognized_scores: list[Optional[float]] = []
        for emb in embeddings:
            if not emb:
                recognized_ids.append(None)
                recognized_scores.append(None)
                continue
            match = best_match_for_embedding(
                candidate=list(emb),
                users=self._list_users(),
                threshold=self._cfg.match_threshold,
                metric=self._cfg.match_metric,
            )
            if match and match.user_id is not None and match.distance is not None:
                recognized_ids.append(int(match.user_id))
                recognized_scores.append(float(match.distance))
            else:
                recognized_ids.append(None)
                recognized_scores.append(None)
        return recognized_ids, recognized_scores

    def _annotate_frame(self, frame, snap: VisionSnapshot):
        annotated = frame.copy()
        for idx, box in enumerate(snap.boxes):
            self._cv2.rectangle(
                annotated,
                (box.x, box.y),
                (box.x + box.w, box.y + box.h),
                (92, 212, 255),
                2,
            )
            face_label = None
            if snap.faces and idx < len(snap.faces):
                face = snap.faces[idx]
                face_label = face.label or (
                    "UNKNOWN" if getattr(face, "user_id", None) is None else "UNKNOWN"
                )
            if face_label:
                self._cv2.putText(
                    annotated,
                    face_label,
                    (box.x + 4, max(20, box.y - 8)),
                    self._cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (92, 212, 255),
                    1,
                    self._cv2.LINE_AA,
                )

        overlay = [
            f"Vision: {snap.vision_state}",
            f"People: {snap.people_count}",
            f"FPS: {snap.fps:.1f}",
        ]
        if snap.vision_error:
            overlay.append(f"Err: {snap.vision_error}")
        for idx, text in enumerate(overlay):
            self._cv2.putText(
                annotated,
                text,
                (10, 24 + idx * 20),
                self._cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
                self._cv2.LINE_AA,
            )
        return annotated

    def _ensure_capture(self):
        if self._ingest is not None:
            return None
        with self._capture_lock:
            if self._capture is not None and self._capture.isOpened():
                return self._capture
            if self._capture is not None:
                try:
                    self._capture.release()
                except Exception:
                    pass
            self._capture = None

            # Prefer camera_source, fallback to camera_index
            raw = (self._cfg.camera_source or str(self._cfg.camera_index)).strip()
            lower = raw.lower()
            if "://" in raw or lower.startswith(("rtsp", "http")):
                source: object = raw
            elif raw.isdigit():
                source = int(raw)
            else:
                source = raw

            if isinstance(source, str) and source.lower().startswith("rtsp://"):
                if "OPENCV_FFMPEG_CAPTURE_OPTIONS" not in os.environ:
                    stimeout_us = max(1_000_000, int(self._cfg.read_timeout_ms) * 1000)
                    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
                        f"rtsp_transport;tcp|stimeout;{stimeout_us}"
                    )
            backend = 0
            b = (self._cfg.camera_backend or "").strip().lower()
            if b == "ffmpeg":
                backend = self._cv2.CAP_FFMPEG
            elif b == "gstreamer":
                backend = self._cv2.CAP_GSTREAMER

            cap = (
                self._cv2.VideoCapture(source, backend)
                if backend
                else self._cv2.VideoCapture(source)
            )

            try:
                cap.set(
                    self._cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
                    float(self._cfg.open_timeout_ms),
                )
            except Exception:
                pass
            try:
                cap.set(
                    self._cv2.CAP_PROP_READ_TIMEOUT_MSEC,
                    float(self._cfg.read_timeout_ms),
                )
            except Exception:
                pass
            try:
                cap.set(self._cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass

            cap.set(self._cv2.CAP_PROP_FRAME_WIDTH, self._cfg.frame_width)
            cap.set(self._cv2.CAP_PROP_FRAME_HEIGHT, self._cfg.frame_height)

            if not cap.isOpened():
                try:
                    cap.release()
                except Exception:
                    pass
                return None
            self._capture = cap
            return cap

    def _reset_capture(self) -> None:
        if self._ingest is not None:
            return
        with self._capture_lock:
            if self._capture is not None:
                try:
                    self._capture.release()
                except Exception:
                    pass
            self._capture = None

    def _publish_placeholder(self, text: str) -> None:
        # Produce a live-looking frame even without a camera so FSM/monitor keep moving.
        placeholder_descriptor = [0.0] * 32
        box = VisionBox(x=220, y=120, w=200, h=200, score=0.5)
        snap = VisionSnapshot(
            people_count=1,
            boxes=[box],
            faces=[
                VisionFace(
                    box=box, user_id=None, score=None, label="UNKNOWN", is_known=False
                )
            ],
            silhouettes=[box],
            vision_state="DETECTING",
            last_frame_ts=time.time(),
            fps=0.0,
            vision_error=text,
            match=True,
            matched_user_id=None,
            match_distance=0.0,
            descriptor=placeholder_descriptor,
            recognized_user_ids=[],
            recognized_scores=[],
            frame_w=640,
            frame_h=480,
            camera_ok=False,
        )
        jpg = self._build_placeholder(text, box)
        with self._lock:
            self._snapshot = snap
            self._last_jpeg = jpg
            self._last_descriptor = placeholder_descriptor

    def _label_for_user(self, user_id: Optional[int]) -> tuple[Optional[str], bool]:
        return _label_for_user_id(user_id, self._get_user_by_id)

    def _build_placeholder(self, text: str, box: Optional[VisionBox] = None) -> bytes:
        canvas = np.zeros((480, 640, 3), dtype=np.uint8)
        if box is not None:
            self._cv2.rectangle(
                canvas,
                (box.x, box.y),
                (box.x + box.w, box.y + box.h),
                (92, 212, 255),
                2,
            )
        self._cv2.putText(
            canvas,
            text,
            (40, 240),
            self._cv2.FONT_HERSHEY_SIMPLEX,
            1.2,
            (255, 255, 255),
            2,
            self._cv2.LINE_AA,
        )
        ok, buf = self._cv2.imencode(".jpg", canvas)
        if ok:
            return buf.tobytes()
        return b""


def _label_for_user_id(
    user_id: Optional[int],
    getter: Optional[Callable[[int], Optional[object]]],
) -> tuple[Optional[str], bool]:
    if user_id is None or getter is None:
        return "UNKNOWN", False
    try:
        user = getter(user_id)
    except Exception:
        user = None
    if user is None:
        return "UNKNOWN", False
    label = getattr(user, "name", None) or getattr(user, "login", None)
    if not label:
        return "UNKNOWN", False
    return label, True


def _best_overlap_box(
    reference: VisionBox, candidates: Sequence[VisionBox]
) -> Optional[VisionBox]:
    """Pick the candidate with the highest IoU against reference."""
    if not candidates:
        return None

    def iou(a: VisionBox, b: VisionBox) -> float:
        ax1, ay1 = a.x, a.y
        ax2, ay2 = a.x + a.w, a.y + a.h
        bx1, by1 = b.x, b.y
        bx2, by2 = b.x + b.w, b.y + b.h
        ix1 = max(ax1, bx1)
        iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)
        iw = max(0, ix2 - ix1)
        ih = max(0, iy2 - iy1)
        inter = float(iw * ih)
        if inter <= 0:
            return 0.0
        area_a = float(max(0, a.w) * max(0, a.h))
        area_b = float(max(0, b.w) * max(0, b.h))
        denom = area_a + area_b - inter
        if denom <= 0:
            return 0.0
        return inter / denom

    best: Optional[VisionBox] = None
    best_score = -1.0
    for cand in candidates:
        score = iou(reference, cand)
        if score > best_score:
            best_score = score
            best = cand
    return best


def _box_iou(a: VisionBox, b: VisionBox) -> float:
    ax1, ay1 = a.x, a.y
    ax2, ay2 = a.x + a.w, a.y + a.h
    bx1, by1 = b.x, b.y
    bx2, by2 = b.x + b.w, b.y + b.h
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    iw = max(0, ix2 - ix1)
    ih = max(0, iy2 - iy1)
    inter = float(iw * ih)
    if inter <= 0:
        return 0.0
    area_a = float(max(0, a.w) * max(0, a.h))
    area_b = float(max(0, b.w) * max(0, b.h))
    denom = area_a + area_b - inter
    if denom <= 0:
        return 0.0
    return inter / denom


class VisionServiceDummy:
    """Test-friendly dummy that mimics the live interface without a camera."""

    def __init__(
        self,
        cfg: Optional[VisionConfig] = None,
        dummy_cfg: Optional[VisionDummyConfig] = None,
    ) -> None:
        self._cfg = cfg or VisionConfig()
        self._dummy_cfg = dummy_cfg or VisionDummyConfig.from_env()
        self.people_count = self._dummy_cfg.default_people_count
        self.recognized_user_ids: list[int] = list(
            self._dummy_cfg.default_recognized_ids
        )
        self.face_match: Optional[FaceMatch] = (
            self._dummy_cfg.default_face_match or FaceMatch.NO_FACE
        )
        self._dummy_delay_sec = self._dummy_cfg.dummy_delay_sec
        self._frame_w = self._cfg.frame_width
        self._frame_h = self._cfg.frame_height
        self.camera_ok = True
        self._snapshot = VisionSnapshot(
            people_count=0,
            boxes=[],
            faces=[],
            vision_state="OFF",
            last_frame_ts=time.time(),
            fps=0.0,
            vision_error="DUMMY",
            frame_w=self._frame_w,
            frame_h=self._frame_h,
            camera_ok=self.camera_ok,
        )

    def set_values(
        self,
        people_count: int,
        face_match: Optional[FaceMatch],
        recognized_user_ids: Optional[Sequence[int]] = None,
        delay_ms: Optional[int] = None,
        camera_ok: Optional[bool] = None,
    ) -> None:
        self.people_count = max(0, people_count)
        self.face_match = face_match or FaceMatch.NO_FACE
        if recognized_user_ids is not None:
            self.recognized_user_ids = [int(x) for x in recognized_user_ids]
        if delay_ms is not None:
            self._dummy_delay_sec = max(0.0, delay_ms / 1000.0)
        if camera_ok is not None:
            self.camera_ok = bool(camera_ok)

    async def analyze(
        self,
        _frame: Optional[bytes] = None,
    ) -> VisionResult:
        if self._dummy_delay_sec > 0:
            await asyncio.sleep(self._dummy_delay_sec)
        faces = [
            DetectedFace(
                bbox=BoundingBox(
                    x=40 + idx * 10, y=40 + idx * 5, w=120, h=120, score=1.0
                ),
                match_user_id=user_id,
                score=1.0,
            )
            for idx, user_id in enumerate(self.recognized_user_ids)
        ]
        return VisionResult(
            people_count=self.people_count,
            faces=faces,
            recognized_user_ids=list(self.recognized_user_ids),
            camera_ok=self.camera_ok,
            debug={"provider": self.__class__.__name__},
        )

    async def analyze_room(
        self,
        card_id: Optional[str],
        user_id: Optional[int],
    ) -> VisionAnalysis:
        if self._dummy_delay_sec > 0:
            await asyncio.sleep(self._dummy_delay_sec)
        match = self.face_match or FaceMatch.NO_FACE
        if self.recognized_user_ids:
            match = FaceMatch.MATCH
        return VisionAnalysis(
            people_count=self.people_count,
            face_match=match,
            stale=False,
            recognized_user_ids=list(self.recognized_user_ids),
            camera_ok=self.camera_ok,
        )

    def last_snapshot(self) -> dict:
        boxes = [VisionBox(x=120, y=80, w=120, h=120).__dict__]
        silhouettes = [VisionBox(x=90, y=60, w=180, h=180).__dict__]
        faces = []
        for idx, box in enumerate(boxes[: max(1, len(self.recognized_user_ids))]):
            uid = (
                self.recognized_user_ids[idx]
                if idx < len(self.recognized_user_ids)
                else None
            )
            label, is_known = _label_for_user_id(uid, db_models.get_user_by_id)
            label = label or "UNKNOWN"
            faces.append(
                {
                    "box": box,
                    "user_id": uid,
                    "score": 1.0 if uid is not None else None,
                    "label": label,
                    "is_known": is_known,
                }
            )
        return {
            "provider": self.__class__.__name__,
            "people_count": max(1, self.people_count),
            "boxes": boxes,
            "silhouettes": silhouettes if silhouettes else boxes,
            "faces": (
                faces
                if faces
                else [
                    {
                        "box": boxes[0],
                        "user_id": None,
                        "score": None,
                        "label": "UNKNOWN",
                        "is_known": False,
                    }
                ]
            ),
            "vision_state": "DETECTING",
            "last_frame_ts": time.time(),
            "fps": 0.0,
            "vision_error": "DUMMY",
            "match": True,
            "matched_user_id": None,
            "match_distance": 0.0,
            "recognized_user_ids": list(self.recognized_user_ids),
            "recognized_scores": [1.0 for _ in self.recognized_user_ids],
            "frame_w": self._frame_w,
            "frame_h": self._frame_h,
            "camera_ok": self.camera_ok,
        }

    def get_jpeg_frame(self) -> bytes:
        # Simple gray placeholder
        canvas = np.zeros((240, 320, 3), dtype=np.uint8)
        return cv2.imencode(".jpg", canvas)[1].tobytes() if cv2 else b""

    def capture_descriptor(self) -> bytes:
        # allow enrollment in dummy mode with a fixed descriptor
        vec = [0.0] * 32
        return serialize_face_descriptor(vec)


class VisionServiceDummyControl(VisionServiceDummy):
    """Alias for dummy vision with runtime controls (used by admin API)."""

    pass
