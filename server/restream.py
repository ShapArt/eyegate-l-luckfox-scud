from __future__ import annotations

import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class RestreamConfig:
    input_url: str
    output_dir: Path
    stream_name: str = "live0"
    transport: str = "tcp"
    hls_time: float = 1.0
    hls_list_size: int = 6
    ffmpeg_path: str = "ffmpeg"


class RestreamService:
    def __init__(self, cfg: RestreamConfig) -> None:
        self._cfg = cfg
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._process: Optional[subprocess.Popen[bytes]] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._stderr_lines: deque[str] = deque(maxlen=5)
        self._use_copy = True
        self._backoff = 0.5
        self._error: Optional[str] = None

    @property
    def playlist_path(self) -> Path:
        return self._cfg.output_dir / "index.m3u8"

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

    def status(self) -> dict:
        return {
            "running": self._process is not None and self._process.poll() is None,
            "error": self._error,
            "copy_mode": self._use_copy,
            "playlist": str(self.playlist_path),
        }

    def _run_loop(self) -> None:
        self._cfg.output_dir.mkdir(parents=True, exist_ok=True)
        while not self._stop_event.is_set():
            self._cleanup_output(max_age_sec=0)
            process = self._start_process(self._use_copy)
            if process is None:
                self._error = "FFMPEG_START_FAILED"
                self._sleep_backoff()
                continue

            start_time = time.time()
            while not self._stop_event.is_set():
                if process.poll() is not None:
                    break
                time.sleep(0.5)

            runtime = time.time() - start_time
            error = self._consume_stderr() or "RESTREAM_EXITED"
            if not self._stop_event.is_set():
                print(f"[restream] ffmpeg exited after {runtime:.1f}s: {error}")
            self._error = error
            self._stop_process()
            self._cleanup_output(max_age_sec=30)
            if self._stop_event.is_set():
                break
            if self._use_copy and runtime < 5.0:
                self._use_copy = False
                print("[restream] copy failed; falling back to libx264")
            self._sleep_backoff()
            self._bump_backoff()

    def _build_cmd(self, use_copy: bool) -> list[str]:
        transport = (self._cfg.transport or "tcp").lower()
        segment_pattern = str(self._cfg.output_dir / "seg_%03d.ts")
        cmd = [
            self._cfg.ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "warning",
            "-rtsp_transport",
            transport,
            "-i",
            self._cfg.input_url,
            "-an",
            "-sn",
            "-dn",
        ]
        if use_copy:
            cmd += ["-c:v", "copy"]
        else:
            cmd += [
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-tune",
                "zerolatency",
                "-pix_fmt",
                "yuv420p",
                "-g",
                "30",
                "-keyint_min",
                "30",
                "-sc_threshold",
                "0",
            ]
        cmd += [
            "-f",
            "hls",
            "-hls_time",
            str(self._cfg.hls_time),
            "-hls_list_size",
            str(self._cfg.hls_list_size),
            "-hls_flags",
            "delete_segments+append_list+program_date_time",
            "-hls_segment_filename",
            segment_pattern,
            str(self.playlist_path),
        ]
        return cmd

    def _start_process(self, use_copy: bool) -> Optional[subprocess.Popen[bytes]]:
        self._stop_process()
        cmd = self._build_cmd(use_copy)
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                bufsize=10**6,
            )
        except FileNotFoundError:
            self._error = "FFMPEG_NOT_FOUND"
            return None
        except Exception as exc:  # noqa: BLE001
            self._error = f"FFMPEG_START_ERROR: {exc}"
            return None
        self._process = process
        self._stderr_lines.clear()
        self._stderr_thread = threading.Thread(
            target=self._stderr_reader,
            args=(process.stderr,),  # type: ignore[arg-type]
            daemon=True,
        )
        self._stderr_thread.start()
        print(
            f"[restream] starting ffmpeg ({'copy' if use_copy else 'x264'}) -> {self.playlist_path}"
        )
        return process

    def _stderr_reader(self, stream) -> None:
        try:
            for line in iter(stream.readline, b""):
                text = line.decode("utf-8", errors="ignore").strip()
                if not text:
                    continue
                self._stderr_lines.append(text)
        except Exception:
            return

    def _consume_stderr(self) -> Optional[str]:
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

    def _cleanup_output(self, max_age_sec: int = 120) -> None:
        try:
            now = time.time()
            for path in self._cfg.output_dir.glob("*.ts"):
                if max_age_sec == 0 or (now - path.stat().st_mtime) > max_age_sec:
                    path.unlink(missing_ok=True)
            playlist = self.playlist_path
            if playlist.exists() and max_age_sec == 0:
                playlist.unlink(missing_ok=True)
        except Exception:
            return

    def _sleep_backoff(self) -> None:
        time.sleep(self._backoff)

    def _bump_backoff(self) -> None:
        self._backoff = min(5.0, self._backoff * 2)
