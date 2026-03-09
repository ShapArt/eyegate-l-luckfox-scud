from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DummyDoorsState:
    door1_locked: bool = True
    door2_locked: bool = True
    door1_closed: bool = True
    door2_closed: bool = True


class DummyDoors:
    """Заглушка для DoorsInterface без реального GPIO."""

    def __init__(self) -> None:
        self.state = DummyDoorsState()

    def lock_door1(self) -> None:
        self.state.door1_locked = True
        print("[DummyDoors] lock_door1()")

    def unlock_door1(self) -> None:
        self.state.door1_locked = False
        print("[DummyDoors] unlock_door1()")

    def lock_door2(self) -> None:
        self.state.door2_locked = True
        print("[DummyDoors] lock_door2()")

    def unlock_door2(self) -> None:
        self.state.door2_locked = False
        print("[DummyDoors] unlock_door2()")

    def lock_both(self) -> None:
        self.state.door1_locked = True
        self.state.door2_locked = True
        print("[DummyDoors] lock_both()")

    def is_door1_closed(self) -> bool:
        print(f"[DummyDoors] is_door1_closed() -> {self.state.door1_closed}")
        return self.state.door1_closed

    def is_door2_closed(self) -> bool:
        print(f"[DummyDoors] is_door2_closed() -> {self.state.door2_closed}")
        return self.state.door2_closed

    def set_door1_closed(self, closed: bool) -> None:
        self.state.door1_closed = closed
        print(f"[DummyDoors] set_door1_closed({closed})")

    def set_door2_closed(self, closed: bool) -> None:
        self.state.door2_closed = closed
        print(f"[DummyDoors] set_door2_closed({closed})")


class DummyAlarm:
    def __init__(self) -> None:
        self.is_on = False

    def set_alarm(self, on: bool) -> None:
        self.is_on = on
        print(f"[DummyAlarm] set_alarm({on})")
