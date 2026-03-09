from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional


@dataclass
class SimDoorsState:
    door1_closed: bool = True
    door2_closed: bool = True
    lock1_unlocked: bool = False
    lock2_unlocked: bool = False
    lock1_power: bool = True
    lock2_power: bool = True
    sensor1_open: bool = False
    sensor2_open: bool = False


class SimulatedDoors:
    """
    Controllable in-memory doors/locks simulator that mirrors DoorsInterface.
    Provides helper methods to toggle sensors and can emit DoorClosedChanged events via callback.
    """

    def __init__(
        self,
        auto_close_ms: int | None = None,
        door1_auto_close_ms: int | None = None,
        door2_auto_close_ms: int | None = None,
    ) -> None:
        self.state = SimDoorsState()
        self._on_door_change: Optional[Callable[[int, bool], Awaitable[None]]] = None
        self._auto_close_ms = auto_close_ms
        self._door_auto_close = {
            1: (
                door1_auto_close_ms
                if door1_auto_close_ms is not None
                else auto_close_ms
            ),
            2: (
                door2_auto_close_ms
                if door2_auto_close_ms is not None
                else auto_close_ms
            ),
        }

    def set_event_handler(
        self, handler: Callable[[int, bool], Awaitable[None]]
    ) -> None:
        self._on_door_change = handler

    def lock_door1(self) -> None:
        if self.state.lock1_power:
            self.state.lock1_unlocked = False

    def unlock_door1(self) -> None:
        if self.state.lock1_power:
            self.state.lock1_unlocked = True

    def lock_door2(self) -> None:
        if self.state.lock2_power:
            self.state.lock2_unlocked = False

    def unlock_door2(self) -> None:
        if self.state.lock2_power:
            self.state.lock2_unlocked = True

    def lock_both(self) -> None:
        self.lock_door1()
        self.lock_door2()

    def open_door(self, door: int) -> None:
        if door == 1:
            self.state.door1_closed = False
            self.state.sensor1_open = True
            self._emit_door_change(1, False)
        elif door == 2:
            self.state.door2_closed = False
            self.state.sensor2_open = True
            self._emit_door_change(2, False)
        self._schedule_autoclose(door)

    def close_door(self, door: int) -> None:
        if door == 1:
            self.state.door1_closed = True
            self.state.sensor1_open = False
            self._emit_door_change(1, True)
        elif door == 2:
            self.state.door2_closed = True
            self.state.sensor2_open = False
            self._emit_door_change(2, True)

    def set_sensor(self, door: int, is_closed: bool) -> None:
        if door == 1:
            self.state.door1_closed = is_closed
            self.state.sensor1_open = not is_closed
            self._emit_door_change(1, is_closed)
        elif door == 2:
            self.state.door2_closed = is_closed
            self.state.sensor2_open = not is_closed
            self._emit_door_change(2, is_closed)

    def power_lock(self, door: int, on: bool) -> None:
        if door == 1:
            self.state.lock1_power = on
            if not on:
                self.state.lock1_unlocked = False
        elif door == 2:
            self.state.lock2_power = on
            if not on:
                self.state.lock2_unlocked = False

    def snapshot(self) -> SimDoorsState:
        return SimDoorsState(
            door1_closed=self.state.door1_closed,
            door2_closed=self.state.door2_closed,
            lock1_unlocked=self.state.lock1_unlocked,
            lock2_unlocked=self.state.lock2_unlocked,
            lock1_power=self.state.lock1_power,
            lock2_power=self.state.lock2_power,
            sensor1_open=self.state.sensor1_open,
            sensor2_open=self.state.sensor2_open,
        )

    def _emit_door_change(self, door: int, is_closed: bool) -> None:
        if self._on_door_change:
            try:
                asyncio.create_task(self._on_door_change(door, is_closed))
            except RuntimeError:
                # event loop not running; ignore
                pass

    def set_auto_close(
        self, delay_ms: Optional[int], door: Optional[int] = None
    ) -> None:
        if door is not None:
            if door not in (1, 2):
                return
            self._door_auto_close[door] = delay_ms
            return
        self._auto_close_ms = delay_ms
        self._door_auto_close[1] = delay_ms
        self._door_auto_close[2] = delay_ms

    def auto_close_ms(self, door: Optional[int] = None) -> Optional[int]:
        if door is not None:
            return self._door_auto_close.get(door)
        if self._door_auto_close[1] == self._door_auto_close[2]:
            return self._door_auto_close[1]
        return None

    def _schedule_autoclose(self, door: int) -> None:
        delay = self._door_auto_close.get(door) or self._auto_close_ms
        if not delay or delay <= 0:
            return

        async def worker() -> None:
            try:
                await asyncio.sleep(delay / 1000.0)
                self.close_door(door)
            except asyncio.CancelledError:
                return

        try:
            asyncio.create_task(worker())
        except RuntimeError:
            # event loop not running; ignore in sync contexts
            pass
