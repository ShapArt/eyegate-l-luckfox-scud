from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, List, Optional, Protocol, Set, Tuple

from policy import PolicyAction, PolicyConfig, PolicyDecision, decide_access

from .fsm import GateFSM
from .models import (
    Action,
    ActionType,
    AuthResult,
    CardPresented,
    DoorClosedChanged,
    EventType,
    FaceMatch,
    GateEvent,
    GateState,
    ResetEvent,
    RoomAnalyzed,
    TimeoutEvent,
    VisionAnalysis,
)


class DoorsInterface(Protocol):
    def lock_door1(self) -> None: ...
    def unlock_door1(self) -> None: ...
    def lock_door2(self) -> None: ...
    def unlock_door2(self) -> None: ...
    def lock_both(self) -> None: ...


class AlarmInterface(Protocol):
    def set_alarm(self, on: bool) -> None: ...


class VisionServiceInterface(Protocol):
    async def analyze_room(
        self,
        card_id: Optional[str],
        user_id: Optional[int],
    ) -> VisionAnalysis: ...


class AuthServiceInterface(Protocol):
    async def check_card(self, card_id: str) -> Tuple[bool, Optional[int], str]: ...


class EventLoggerInterface(Protocol):
    async def log(
        self,
        level: str,
        message: str,
        reason: Optional[str],
        state: GateState,
        card_id: Optional[str],
        user_id: Optional[int],
    ) -> None: ...


@dataclass
class GateConfig:
    enter_timeout_sec: float = 15.0
    check_timeout_sec: float = 10.0
    exit_timeout_sec: float = 15.0
    alarm_timeout_sec: float = 60.0
    auto_open_door1: bool = False
    auto_open_door2: bool = False
    demo_mode: bool = False
    allow_multi_known: bool = False
    require_face_match_for_door2: bool = True
    max_people_allowed: int = 1
    door1_close_stabilize_ms: int = 1500
    room_check_samples: int = 5


class GateController:
    def __init__(
        self,
        fsm: GateFSM,
        doors: DoorsInterface,
        vision: VisionServiceInterface,
        auth: AuthServiceInterface,
        logger: EventLoggerInterface,
        alarm: Optional[AlarmInterface] = None,
        config: Optional[GateConfig] = None,
        on_status: Optional[Callable[[dict], Awaitable[Any]]] = None,
    ) -> None:
        self._fsm = fsm
        self._doors = doors
        self._vision = vision
        self._auth = auth
        self._logger = logger
        self._alarm = alarm
        self._config = config or GateConfig()
        self._on_status = on_status

        self._queue: "asyncio.Queue[GateEvent]" = asyncio.Queue()
        self._running = False
        self._background_tasks: Set[asyncio.Task] = set()
        self._last_event: Optional[str] = None
        self._room_samples: List[VisionAnalysis] = []

    async def run(self) -> None:
        self._running = True
        await self._log_debug("GateController started", None)
        await self._broadcast_status()
        while self._running:
            event = await self._queue.get()
            await self._handle_event(event)

    async def stop(self) -> None:
        self._running = False
        for task in list(self._background_tasks):
            task.cancel()
        self._background_tasks.clear()
        await self._log_debug("GateController stopped", None)

    async def push_event(self, event: GateEvent) -> None:
        await self._queue.put(event)

    async def card_presented(self, card_id: str) -> None:
        await self._queue.put(CardPresented(card_id=card_id))

        async def auth_worker() -> None:
            try:
                allow, user_id, reason = await self._auth.check_card(card_id)
                await self._queue.put(
                    AuthResult(
                        allow=allow,
                        reason=reason,
                        user_id=user_id,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                await self._logger.log(
                    level="ERROR",
                    message=f"AuthService failed: {exc!r}",
                    reason="AUTH_EXCEPTION",
                    state=self._fsm.state,
                    card_id=card_id,
                    user_id=None,
                )
                await self._queue.put(
                    AuthResult(
                        allow=False,
                        reason="AUTH_EXCEPTION",
                        user_id=None,
                    )
                )

        task = asyncio.create_task(auth_worker())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def login_success(self, user_id: int) -> None:
        """Push successful login into the FSM as if auth was approved."""
        await self._queue.put(
            AuthResult(
                allow=True,
                reason="LOGIN_OK",
                user_id=user_id,
            )
        )

    async def door_closed_changed(self, door: int, is_closed: bool) -> None:
        await self._queue.put(DoorClosedChanged(door=door, is_closed=is_closed))

    async def reset(self) -> None:
        await self._queue.put(ResetEvent())

    async def _handle_event(self, event: GateEvent) -> None:
        result = self._fsm.handle_event(event)
        await self._process_actions(result.actions)
        await self._broadcast_status()

    async def _process_actions(self, actions: List[Action]) -> None:
        for action in actions:
            atype = action.type

            if atype == ActionType.UNLOCK_DOOR1:
                self._doors.unlock_door1()
                if getattr(self._config, "auto_open_door1", False) and hasattr(
                    self._doors, "open_door"
                ):
                    try:
                        # auto-open door 1 in demo/sim mode so the UI reflects entry without manual click
                        self._doors.open_door(1)  # type: ignore[attr-defined]
                    except Exception:
                        pass
            elif atype == ActionType.LOCK_DOOR1:
                self._doors.lock_door1()
            elif atype == ActionType.UNLOCK_DOOR2:
                self._doors.unlock_door2()
                if getattr(self._config, "auto_open_door2", False) and hasattr(
                    self._doors, "open_door"
                ):
                    try:
                        self._doors.open_door(2)  # type: ignore[attr-defined]
                    except Exception:
                        pass
            elif atype == ActionType.LOCK_DOOR2:
                self._doors.lock_door2()
            elif atype == ActionType.LOCK_BOTH:
                self._doors.lock_both()
            elif atype == ActionType.START_ENTER_TIMEOUT:
                self._schedule_timeout(
                    EventType.TIMEOUT_ENTER, self._config.enter_timeout_sec
                )
            elif atype == ActionType.START_CHECK_TIMEOUT:
                self._schedule_timeout(
                    EventType.TIMEOUT_CHECK, self._config.check_timeout_sec
                )
            elif atype == ActionType.START_EXIT_TIMEOUT:
                self._schedule_timeout(
                    EventType.TIMEOUT_EXIT, self._config.exit_timeout_sec
                )
            elif atype == ActionType.START_ALARM_TIMEOUT:
                self._schedule_timeout(
                    EventType.TIMEOUT_ALARM, self._config.alarm_timeout_sec
                )
            elif atype == ActionType.CANCEL_ALL_TIMEOUTS:
                self._cancel_timeouts()
            elif atype == ActionType.START_ROOM_ANALYSIS:
                self._schedule_room_analysis()
            elif atype == ActionType.SET_ALARM_ON:
                if self._alarm is not None:
                    self._alarm.set_alarm(True)
            elif atype == ActionType.SET_ALARM_OFF:
                if self._alarm is not None:
                    self._alarm.set_alarm(False)
            elif atype == ActionType.LOG_EVENT:
                self._last_event = action.message or ""
                await self._log_debug(action.message or "", action.reason)
            elif atype == ActionType.CLEAR_CONTEXT:
                await self._log_debug("Context cleared", action.reason)
            else:
                await self._log_debug(f"Unknown action: {atype}", action.reason)

    def _schedule_timeout(self, timeout_type: EventType, delay: float) -> None:
        async def worker() -> None:
            try:
                await asyncio.sleep(delay)
                await self._queue.put(TimeoutEvent(event_type=timeout_type))
            except asyncio.CancelledError:
                return

        task = asyncio.create_task(worker())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    def _cancel_timeouts(self) -> None:
        for task in list(self._background_tasks):
            task.cancel()
        self._background_tasks.clear()

    def _schedule_room_analysis(self) -> None:
        async def worker() -> None:
            try:
                await asyncio.sleep(self._config.door1_close_stabilize_ms / 1000.0)
                card_id = self._fsm.ctx.current_card_id
                user_id = self._fsm.ctx.current_user_id
                samples: List[VisionAnalysis] = []
                for _ in range(max(1, self._config.room_check_samples)):
                    analysis = await self._vision.analyze_room(
                        card_id=card_id,
                        user_id=user_id,
                    )
                    samples.append(analysis)
                    await asyncio.sleep(0.1)
                self._room_samples = samples
                aggregated = self._aggregate_room_samples(samples)
                if not aggregated.camera_ok:
                    policy_decision = PolicyDecision(
                        action=PolicyAction.DENY, reason="CAMERA_DOWN"
                    )
                else:
                    policy_decision = decide_access(
                        people_count=aggregated.people_count,
                        recognized_user_ids=aggregated.recognized_user_ids or [],
                        required_user_id=user_id,
                        config=PolicyConfig(
                            allow_multi_known=self._config.allow_multi_known,
                            require_face_match_for_door2=self._config.require_face_match_for_door2,
                            max_people_allowed=self._config.max_people_allowed,
                        ),
                    )
                await self._queue.put(
                    RoomAnalyzed(
                        people_count=aggregated.people_count,
                        face_match=aggregated.face_match,
                        stale=aggregated.stale,
                        matched_user_id=aggregated.matched_user_id,
                        match_distance=aggregated.match_distance,
                        recognized_user_ids=aggregated.recognized_user_ids,
                        policy_action=policy_decision.action.value,
                        policy_reason=policy_decision.reason,
                        camera_ok=aggregated.camera_ok,
                    )
                )
            except asyncio.CancelledError:
                return
            except Exception as exc:  # noqa: BLE001
                await self._logger.log(
                    level="ERROR",
                    message=f"VisionService failed: {exc!r}",
                    reason="VISION_EXCEPTION",
                    state=self._fsm.state,
                    card_id=self._fsm.ctx.current_card_id,
                    user_id=self._fsm.ctx.current_user_id,
                )
                await self._queue.put(
                    RoomAnalyzed(
                        people_count=0,
                        face_match=FaceMatch.NO_FACE,
                        stale=True,
                    )
                )

        task = asyncio.create_task(worker())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    def _aggregate_room_samples(self, samples: List[VisionAnalysis]) -> VisionAnalysis:
        """Aggregate multiple readings into a robust decision."""
        if not samples:
            return VisionAnalysis(
                people_count=0,
                face_match=FaceMatch.NO_FACE,
                stale=True,
                camera_ok=False,
            )

        people_values = sorted(s.people_count for s in samples)
        median_people = people_values[len(people_values) // 2]

        # choose best match by smallest distance among non-stale samples
        best_match: Optional[VisionAnalysis] = None
        recognized_all: set[int] = set()
        camera_ok = all(getattr(s, "camera_ok", True) for s in samples)
        for s in samples:
            if s.stale:
                continue
            if s.recognized_user_ids:
                recognized_all.update(
                    int(x) for x in s.recognized_user_ids if x is not None
                )
            if best_match is None:
                best_match = s
            elif s.match_distance is not None and best_match.match_distance is not None:
                if s.match_distance < best_match.match_distance:
                    best_match = s

        face_match = FaceMatch.NO_FACE
        matched_user_id = None
        match_distance = None
        stale = any(s.stale for s in samples)
        if best_match is not None:
            face_match = best_match.face_match
            matched_user_id = best_match.matched_user_id
            match_distance = best_match.match_distance

        return VisionAnalysis(
            people_count=median_people,
            face_match=face_match,
            stale=stale,
            matched_user_id=matched_user_id,
            match_distance=match_distance,
            recognized_user_ids=list(
                recognized_all
                or ({matched_user_id} if matched_user_id is not None else set())
            ),
            camera_ok=camera_ok,
        )

    async def _log_debug(self, message: str, reason: Optional[str]) -> None:
        await self._logger.log(
            level="INFO",
            message=message,
            reason=reason,
            state=self._fsm.state,
            card_id=self._fsm.ctx.current_card_id,
            user_id=self._fsm.ctx.current_user_id,
        )

    @property
    def state(self) -> GateState:
        return self._fsm.state

    @property
    def current_card_id(self) -> Optional[str]:
        return self._fsm.ctx.current_card_id

    @property
    def current_user_id(self) -> Optional[int]:
        return self._fsm.ctx.current_user_id

    @property
    def last_event(self) -> Optional[str]:
        return self._last_event

    def snapshot(self) -> dict:
        doors_state = getattr(self._doors, "state", None)
        doors: dict | None = None
        if doors_state is not None:
            doors = {
                "door1_closed": getattr(doors_state, "door1_closed", None),
                "door2_closed": getattr(doors_state, "door2_closed", None),
                "lock1_unlocked": getattr(doors_state, "lock1_unlocked", None),
                "lock2_unlocked": getattr(doors_state, "lock2_unlocked", None),
            }
            if doors.get("lock1_unlocked") is None and hasattr(
                doors_state, "door1_locked"
            ):
                doors["lock1_unlocked"] = not getattr(doors_state, "door1_locked")
            if doors.get("lock2_unlocked") is None and hasattr(
                doors_state, "door2_locked"
            ):
                doors["lock2_unlocked"] = not getattr(doors_state, "door2_locked")
            if hasattr(doors_state, "lock1_power"):
                doors["lock1_power"] = getattr(doors_state, "lock1_power")
            if hasattr(doors_state, "lock2_power"):
                doors["lock2_power"] = getattr(doors_state, "lock2_power")
            if hasattr(doors_state, "sensor1_open"):
                doors["sensor1_open"] = getattr(doors_state, "sensor1_open")
            if hasattr(doors_state, "sensor2_open"):
                doors["sensor2_open"] = getattr(doors_state, "sensor2_open")

        vision_info = None
        if hasattr(self._vision, "last_snapshot"):
            try:
                vision_info = self._vision.last_snapshot()  # type: ignore[attr-defined]
            except Exception:
                vision_info = None
        if isinstance(vision_info, dict):
            vision_info["provider"] = (
                vision_info.get("provider") or self._vision.__class__.__name__
            )

        people_count = 0
        if isinstance(vision_info, dict):
            pc = vision_info.get("people_count")
            if isinstance(pc, (int, float)):
                people_count = int(pc)

        door1_closed = doors.get("door1_closed") if doors else None
        door2_closed = doors.get("door2_closed") if doors else None
        alarm_rule = door1_closed is True and door2_closed is True and people_count > 1

        if alarm_rule:
            if self._alarm is not None:
                try:
                    self._alarm.set_alarm(True)
                except Exception:
                    pass
            alarm_on = True
        else:
            if self._alarm is not None:
                try:
                    self._alarm.set_alarm(False)
                except Exception:
                    pass
            alarm_on = getattr(self._alarm, "is_on", False) if self._alarm else False

        if vision_info is None:
            vision_info = {
                "provider": self._vision.__class__.__name__,
                "people_count": max(people_count, 1),
                "vision_state": "DETECTING",
                "camera_ok": False,
            }
        if alarm_rule:
            vision_info["vision_state"] = "ALARM"
        elif people_count == 1 and vision_info.get("vision_state") in (
            None,
            "DETECTING",
            "DECIDING",
            "WARMUP",
        ):
            vision_info["vision_state"] = "OK"
        vision_info.setdefault("people_count", max(people_count, 1))

        vision_required = self.state == GateState.CHECK_ROOM
        return {
            "state": self.state.name,
            "current_card_id": self.current_card_id,
            "current_user_id": self.current_user_id,
            "doors": doors,
            "alarm_on": alarm_on,
            "last_event": self._last_event,
            "vision": vision_info,
            "vision_required": vision_required,
            "demo_mode": getattr(self._config, "demo_mode", False),
            "timestamp": dt.datetime.utcnow(),
            "policy": {
                "allow_multi_known": getattr(self._config, "allow_multi_known", False),
                "max_people_allowed": getattr(self._config, "max_people_allowed", 1),
                "require_face_match_for_door2": getattr(
                    self._config, "require_face_match_for_door2", True
                ),
            },
            "room_samples": [s.__dict__ for s in getattr(self, "_room_samples", [])],
        }

    async def _broadcast_status(self) -> None:
        if not self._on_status:
            return
        snapshot = self.snapshot()
        await self._on_status(snapshot)
