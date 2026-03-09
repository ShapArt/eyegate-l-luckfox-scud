from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, Optional


class GPIOError(RuntimeError):
    """Ошибка при работе с GPIO через sysfs."""


@dataclass
class GPIOPinConfig:
    number: int
    direction: Literal["in", "out"]
    active_high: bool = True


class SysfsGPIOPin:
    """Примитивная обёртка над /sys/class/gpio."""

    def __init__(self, cfg: GPIOPinConfig) -> None:
        self.cfg = cfg
        self._base_path = f"/sys/class/gpio/gpio{cfg.number}"
        self._export_if_needed()
        self._set_direction(cfg.direction)

    def _export_if_needed(self) -> None:
        if not os.path.isdir(self._base_path):
            try:
                with open("/sys/class/gpio/export", "w", encoding="utf-8") as f:
                    f.write(str(self.cfg.number))
            except OSError as exc:  # noqa: BLE001
                raise GPIOError(
                    f"Failed to export GPIO {self.cfg.number}: {exc}"
                ) from exc

    def _set_direction(self, direction: str) -> None:
        try:
            with open(
                os.path.join(self._base_path, "direction"), "w", encoding="utf-8"
            ) as f:
                f.write(direction)
        except OSError as exc:  # noqa: BLE001
            raise GPIOError(
                f"Failed to set direction for GPIO {self.cfg.number}: {exc}"
            ) from exc

    def write(self, value: bool) -> None:
        if self.cfg.direction != "out":
            raise GPIOError(f"GPIO {self.cfg.number} is not configured as output")

        logical = bool(value)
        physical = logical if self.cfg.active_high else (not logical)
        svalue = "1" if physical else "0"

        try:
            with open(
                os.path.join(self._base_path, "value"), "w", encoding="utf-8"
            ) as f:
                f.write(svalue)
        except OSError as exc:  # noqa: BLE001
            raise GPIOError(f"Failed to write GPIO {self.cfg.number}: {exc}") from exc

    def read(self) -> bool:
        if self.cfg.direction != "in":
            raise GPIOError(f"GPIO {self.cfg.number} is not configured as input")
        try:
            with open(
                os.path.join(self._base_path, "value"), "r", encoding="utf-8"
            ) as f:
                raw = f.read().strip()
        except OSError as exc:  # noqa: BLE001
            raise GPIOError(f"Failed to read GPIO {self.cfg.number}: {exc}") from exc

        physical = raw == "1"
        logical = physical if self.cfg.active_high else (not physical)
        return logical

    def close(self) -> None:
        try:
            if os.path.isdir(self._base_path):
                with open("/sys/class/gpio/unexport", "w", encoding="utf-8") as f:
                    f.write(str(self.cfg.number))
        except OSError:
            pass


@dataclass
class DoorsConfig:
    door1_lock_gpio: int
    door2_lock_gpio: int
    door1_closed_gpio: int
    door2_closed_gpio: int
    lock_active_high: bool = True
    closed_active_high: bool = False


class DoorsController:
    """Реализация управления дверями на GPIO для GateController."""

    def __init__(self, cfg: DoorsConfig) -> None:
        self._cfg = cfg
        self._pin_lock1 = SysfsGPIOPin(
            GPIOPinConfig(
                number=cfg.door1_lock_gpio,
                direction="out",
                active_high=cfg.lock_active_high,
            )
        )
        self._pin_lock2 = SysfsGPIOPin(
            GPIOPinConfig(
                number=cfg.door2_lock_gpio,
                direction="out",
                active_high=cfg.lock_active_high,
            )
        )
        self._pin_closed1 = SysfsGPIOPin(
            GPIOPinConfig(
                number=cfg.door1_closed_gpio,
                direction="in",
                active_high=cfg.closed_active_high,
            )
        )
        self._pin_closed2 = SysfsGPIOPin(
            GPIOPinConfig(
                number=cfg.door2_closed_gpio,
                direction="in",
                active_high=cfg.closed_active_high,
            )
        )
        self.lock_both()

    def lock_door1(self) -> None:
        self._pin_lock1.write(True)

    def unlock_door1(self) -> None:
        self._pin_lock1.write(False)

    def lock_door2(self) -> None:
        self._pin_lock2.write(True)

    def unlock_door2(self) -> None:
        self._pin_lock2.write(False)

    def lock_both(self) -> None:
        self._pin_lock1.write(True)
        self._pin_lock2.write(True)

    def is_door1_closed(self) -> Optional[bool]:
        try:
            return self._pin_closed1.read()
        except GPIOError:
            return None

    def is_door2_closed(self) -> Optional[bool]:
        try:
            return self._pin_closed2.read()
        except GPIOError:
            return None

    def close(self) -> None:
        self._pin_lock1.close()
        self._pin_lock2.close()
        self._pin_closed1.close()
        self._pin_closed2.close()
