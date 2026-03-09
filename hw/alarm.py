from __future__ import annotations

from dataclasses import dataclass

from .doors import GPIOPinConfig, SysfsGPIOPin


@dataclass
class AlarmConfig:
    alarm_gpio: int
    active_high: bool = True


class AlarmGPIO:
    """Управление сиреной/лампой тревоги по GPIO."""

    def __init__(self, cfg: AlarmConfig) -> None:
        self._cfg = cfg
        self._pin = SysfsGPIOPin(
            GPIOPinConfig(
                number=cfg.alarm_gpio,
                direction="out",
                active_high=cfg.active_high,
            )
        )
        self.set_alarm(False)

    def set_alarm(self, on: bool) -> None:
        self._pin.write(on)

    def close(self) -> None:
        self._pin.close()
