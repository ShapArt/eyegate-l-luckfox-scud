from __future__ import annotations

import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class CameraIngestConfig:
    url: str
    transport: str = "tcp"
    width: int = 960
    height: int = 720
    read_timeout_sec: float = 2.5
    backoff_initial_sec: float = 0.5
    backoff_max_sec: float = 5.0
    ffmpeg_path: str = "ffmpeg"


@dataclass
class CameraFrame:
    timestamp: float
    frame: np.ndarray
    frame_id: int


class CameraIngest:
    def __init__(self, cfg: CameraIngestConfig) -> None:
        self._cfg = cfg
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._process: Optional[subprocess.Popen[bytes]] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._stderr_lines: deque[str] = deque(maxlen=5)
        self._frame: Optional[np.ndarray] = None
        self._frame_ts: Optional[float] = None
        self._frame_id = 0
        self._fps = 0.0
        self._error: Optional[str] = "NOT_STARTED"
        self._backoff = max(0.1, float(self._cfg.backoff_initial_sec))
        self._connected = False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._stop_process()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    @property
    def frame_id(self) -> int:
        with self._lock:
            return self._frame_id

    @property
    def last_frame_ts(self) -> Optional[float]:
        with self._lock:
            return self._frame_ts

    @property
    def fps(self) -> float:
        with self._lock:
            return self._fps

    @property
    def last_error(self) -> Optional[str]:
        with self._lock:
            return self._error

    def status(self) -> dict:
        with self._lock:
            return {
                "ok": self._frame_ts is not None,
                "last_frame_ts": self._frame_ts,
                "fps": self._fps,
                "error": self._error,
                "frame_id": self._frame_id,
            }

    def get_frame(
        self,
        timeout: float = 1.0,
        since_id: Optional[int] = None,
    ) -> Optional[CameraFrame]:
        deadline = time.time() + max(0.0, float(timeout))
        with self._cond:
            if since_id is None:
                if self._frame is not None and self._frame_ts is not None:
                    return CameraFrame(
                        timestamp=self._frame_ts,
                        frame=self._frame.copy(),
                        frame_id=self._frame_id,
                    )
                since_id = self._frame_id
            while not self._stop_event.is_set():
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                self._cond.wait(timeout=remaining)
                if (
                    self._frame is not None
                    and self._frame_ts is not None
                    and self._frame_id != since_id
                ):
                    return CameraFrame(
                        timestamp=self._frame_ts,
                        frame=self._frame.copy(),
                        frame_id=self._frame_id,
                    )
        return None

    def _run_loop(self) -> None:
        frame_size = int(self._cfg.width * self._cfg.height * 3)
        while not self._stop_event.is_set():
            process = self._start_process()
            if process is None:
                self._set_error("FFMPEG_START_FAILED")
                self._sleep_backoff()
                continue

            self._connected = False
            while not self._stop_event.is_set():
                data = self._read_exact(process.stdout, frame_size)  # type: ignore[arg-type]
                if data is None:
                    break
                frame = np.frombuffer(data, dtype=np.uint8)
                try:
                    frame = frame.reshape((self._cfg.height, self._cfg.width, 3))
                except ValueError:
                    self._set_error("FRAME_SHAPE_ERROR")
                    continue
                now = time.time()
                self._update_frame(frame, now)
                if not self._connected:
                    self._connected = True
                    self._reset_backoff()
                    print(f"[camera_ingest] connected to {self._cfg.url}")

            error = self._consume_stderr() or "STREAM_DISCONNECTED"
            if not self._stop_event.is_set():
                print(f"[camera_ingest] stream ended: {error}")
            self._set_error(error)
            self._stop_process()
            if self._stop_event.is_set():
                break
            self._sleep_backoff()
            self._bump_backoff()

    def _build_cmd(self) -> list[str]:
        transport = (self._cfg.transport or "tcp").lower()
        cmd = [
            self._cfg.ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-rtsp_transport",
            transport,
            "-i",
            self._cfg.url,
            "-an",
            "-sn",
            "-dn",
            "-vf",
            f"scale={self._cfg.width}:{self._cfg.height}",
            "-pix_fmt",
            "bgr24",
            "-f",
            "rawvideo",
            "-",
        ]
        return cmd

    def _start_process(self) -> Optional[subprocess.Popen[bytes]]:
        self._stop_process()
        cmd = self._build_cmd()
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=10**6,
            )
        except FileNotFoundError:
            self._set_error("FFMPEG_NOT_FOUND")
            return None
        except Exception as exc:  # noqa: BLE001
            self._set_error(f"FFMPEG_START_ERROR: {exc}")
            return None

        self._process = process
        self._stderr_lines.clear()
        self._stderr_thread = threading.Thread(
            target=self._stderr_reader,
            args=(process.stderr,),  # type: ignore[arg-type]
            daemon=True,
        )
        self._stderr_thread.start()
        print(f"[camera_ingest] connecting to {self._cfg.url}")
        return process

    def _stderr_reader(self, stream) -> None:
        try:
            for line in iter(stream.readline, b""):
                text = line.decode("utf-8", errors="ignore").strip()
                if not text:
                    continue
                with self._lock:
                    self._stderr_lines.append(text)
        except Exception:
            return

    def _consume_stderr(self) -> Optional[str]:
        with self._lock:
            if self._stderr_lines:
                return self._stderr_lines[-1]
        return None

    def _stop_process(self) -> None:
        proc = self._process
        self._process = None
        if proc is None:
            return
        try:
            proc.terminate()
            proc.wait(timeout=1.0)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        try:
            if proc.stdout:
                proc.stdout.close()
        except Exception:
            pass
        try:
            if proc.stderr:
                proc.stderr.close()
        except Exception:
            pass

    def _read_exact(self, stream, size: int) -> Optional[bytes]:
        buf = bytearray(size)
        view = memoryview(buf)
        read_total = 0
        while read_total < size and not self._stop_event.is_set():
            chunk = stream.read(size - read_total)
            if not chunk:
                return None
            view[read_total : read_total + len(chunk)] = chunk
            read_total += len(chunk)
        if read_total < size:
            return None
        return bytes(buf)

    def _update_frame(self, frame: np.ndarray, ts: float) -> None:
        with self._cond:
            prev_ts = self._frame_ts
            self._frame = frame
            self._frame_ts = ts
            self._frame_id += 1
            if prev_ts is not None:
                dt = ts - prev_ts
                if dt > 0:
                    inst_fps = min(60.0, 1.0 / dt)
                    self._fps = (
                        inst_fps
                        if self._fps <= 0
                        else (0.9 * self._fps + 0.1 * inst_fps)
                    )
            self._error = None
            self._cond.notify_all()

    def _set_error(self, error: str) -> None:
        with self._cond:
            self._error = error
            self._cond.notify_all()

    def _sleep_backoff(self) -> None:
        time.sleep(self._backoff)

    def _bump_backoff(self) -> None:
        self._backoff = min(self._cfg.backoff_max_sec, self._backoff * 2)

    def _reset_backoff(self) -> None:
        self._backoff = max(0.1, float(self._cfg.backoff_initial_sec))
