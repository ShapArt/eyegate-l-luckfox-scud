from __future__ import annotations

import asyncio
import logging
import threading
from typing import Callable, Iterable, Optional, Tuple

logger = logging.getLogger(__name__)


def parse_sensor_line(line: str) -> Tuple[int, bool]:
    """
    Parse sensor messages like "D1:OPEN" / "D2:CLOSED".
    Returns (door, is_closed).
    """
    line = line.strip()
    if not line:
        raise ValueError("Empty line")

    # Text form D1:OPEN
    parts = line.replace(" ", "").split(":")
    if len(parts) != 2:
        raise ValueError("Unsupported format")
    door_part, state_part = parts
    if not door_part.upper().startswith("D"):
        raise ValueError("Missing door prefix")
    try:
        door = int(door_part[1:])
    except ValueError as exc:
        raise ValueError("Invalid door number") from exc
    state = state_part.lower()
    return _normalize(door, state)


def _normalize(door: int, state: str) -> Tuple[int, bool]:
    if door not in (1, 2):
        raise ValueError("door must be 1 or 2")
    if state not in ("open", "opened", "close", "closed"):
        raise ValueError("state must be open/closed")
    return door, state.startswith("close")


class SerialBridge:
    """
    Minimal serial listener that parses COMPIM-style lines and forwards sensor events.
    Accepts either a real serial port or an iterable of lines for simulation/tests.
    """

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        on_sensor: Optional[Callable[[int, bool], object]] = None,
        simulate_lines: Optional[Iterable[str]] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        self._port = port
        self._baudrate = baudrate
        self._on_sensor = on_sensor
        self._simulate_lines = simulate_lines
        self._loop = loop
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def join(self, timeout: Optional[float] = None) -> None:
        if self._thread:
            self._thread.join(timeout=timeout)

    # ---- internals -----------------------------------------------------
    def _run(self) -> None:
        if self._simulate_lines is not None:
            for line in self._simulate_lines:
                if not self._running:
                    break
                self._handle_line(line)
            return

        try:
            import serial  # type: ignore
        except Exception:
            logger.warning(
                "pyserial is not installed; SENSOR_MODE=serial is unavailable"
            )
            return

        try:
            ser = serial.Serial(self._port, self._baudrate, timeout=1)
        except Exception:
            logger.warning("Failed to open serial port %s", self._port)
            return

        with ser:
            while self._running:
                try:
                    raw = ser.readline()
                    if not raw:
                        continue
                    line = raw.decode(errors="ignore")
                    self._handle_line(line)
                except Exception:
                    continue

    def _handle_line(self, line: str) -> None:
        try:
            door, is_closed = parse_sensor_line(line)
        except ValueError:
            return
        if not self._on_sensor:
            return
        try:
            res = self._on_sensor(door, is_closed)
            if asyncio.iscoroutine(res):
                loop = self._loop
                if loop and loop.is_running():
                    asyncio.run_coroutine_threadsafe(res, loop)
                else:
                    asyncio.run(res)
        except Exception:
            return
