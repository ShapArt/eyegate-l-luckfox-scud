from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional, Union


class GateState(Enum):
    """Состояния конечного автомата шлюза."""

    IDLE = auto()
    WAIT_ENTER = auto()
    CHECK_ROOM = auto()
    ACCESS_GRANTED = auto()
    ACCESS_DENIED = auto()
    ALARM = auto()
    RESET = auto()


class FaceMatch(Enum):
    """Результат проверки лица."""

    MATCH = auto()
    NO_MATCH = auto()
    NO_FACE = auto()


class AccessDecision(Enum):
    """Высокоуровневый результат попытки прохода."""

    ALLOW = auto()
    DENY = auto()
    ALARM = auto()


class ActionType(Enum):
    """Типы действий, которые FSM предлагает внешнему миру."""

    LOCK_DOOR1 = auto()
    UNLOCK_DOOR1 = auto()
    LOCK_DOOR2 = auto()
    UNLOCK_DOOR2 = auto()
    LOCK_BOTH = auto()

    START_ENTER_TIMEOUT = auto()
    START_CHECK_TIMEOUT = auto()
    START_EXIT_TIMEOUT = auto()
    START_ALARM_TIMEOUT = auto()
    CANCEL_ALL_TIMEOUTS = auto()

    START_ROOM_ANALYSIS = auto()

    SET_ALARM_ON = auto()
    SET_ALARM_OFF = auto()

    LOG_EVENT = auto()
    CLEAR_CONTEXT = auto()


@dataclass
class Action:
    """Конкретное действие: тип + опциональные данные."""

    type: ActionType
    message: Optional[str] = None
    reason: Optional[str] = None


@dataclass
class VisionAnalysis:
    """Result returned by vision providers when checking the room."""

    people_count: int
    face_match: FaceMatch
    stale: bool = False
    matched_user_id: Optional[int] = None
    match_distance: Optional[float] = None
    recognized_user_ids: Optional[list[int]] = None
    camera_ok: bool = True


class EventType(Enum):
    CARD_PRESENTED = auto()
    AUTH_RESULT = auto()

    DOOR1_CLOSED_CHANGED = auto()
    DOOR2_CLOSED_CHANGED = auto()

    ROOM_ANALYZED = auto()

    TIMEOUT_ENTER = auto()
    TIMEOUT_CHECK = auto()
    TIMEOUT_EXIT = auto()
    TIMEOUT_ALARM = auto()

    RESET = auto()


@dataclass
class Event:
    """Базовый класс события."""

    type: EventType


@dataclass
class CardPresented(Event):
    card_id: str

    def __init__(self, card_id: str) -> None:
        super().__init__(EventType.CARD_PRESENTED)
        self.card_id = card_id


@dataclass
class AuthResult(Event):
    allow: bool
    reason: str
    user_id: Optional[int]

    def __init__(self, allow: bool, reason: str, user_id: Optional[int]) -> None:
        super().__init__(EventType.AUTH_RESULT)
        self.allow = allow
        self.reason = reason
        self.user_id = user_id


@dataclass
class DoorClosedChanged(Event):
    door: int  # 1 или 2
    is_closed: bool

    def __init__(self, door: int, is_closed: bool) -> None:
        if door not in (1, 2):
            raise ValueError("door must be 1 or 2")
        event_type = (
            EventType.DOOR1_CLOSED_CHANGED
            if door == 1
            else EventType.DOOR2_CLOSED_CHANGED
        )
        super().__init__(event_type)
        self.door = door
        self.is_closed = is_closed


@dataclass
class RoomAnalyzed(Event):
    people_count: int
    face_match: FaceMatch
    stale: bool = False
    matched_user_id: Optional[int] = None
    match_distance: Optional[float] = None
    recognized_user_ids: Optional[list[int]] = None
    policy_action: Optional[str] = None
    policy_reason: Optional[str] = None
    camera_ok: bool = True

    def __init__(
        self,
        people_count: int,
        face_match: FaceMatch,
        stale: bool = False,
        matched_user_id: Optional[int] = None,
        match_distance: Optional[float] = None,
        recognized_user_ids: Optional[list[int]] = None,
        policy_action: Optional[str] = None,
        policy_reason: Optional[str] = None,
        camera_ok: bool = True,
    ) -> None:
        super().__init__(EventType.ROOM_ANALYZED)
        self.people_count = people_count
        self.face_match = face_match
        self.stale = stale
        self.matched_user_id = matched_user_id
        self.match_distance = match_distance
        self.recognized_user_ids = recognized_user_ids
        self.policy_action = policy_action
        self.policy_reason = policy_reason
        self.camera_ok = camera_ok


@dataclass
class TimeoutEvent(Event):
    def __init__(self, event_type: EventType) -> None:
        super().__init__(event_type)


@dataclass
class ResetEvent(Event):
    def __init__(self) -> None:
        super().__init__(EventType.RESET)


def timeout_enter() -> TimeoutEvent:
    return TimeoutEvent(EventType.TIMEOUT_ENTER)


def timeout_check() -> TimeoutEvent:
    return TimeoutEvent(EventType.TIMEOUT_CHECK)


def timeout_exit() -> TimeoutEvent:
    return TimeoutEvent(EventType.TIMEOUT_EXIT)


def timeout_alarm() -> TimeoutEvent:
    return TimeoutEvent(EventType.TIMEOUT_ALARM)


@dataclass
class TransitionResult:
    """Результат обработки события: новое состояние и действия."""

    next_state: GateState
    actions: List[Action]


GateEvent = Union[
    CardPresented,
    AuthResult,
    DoorClosedChanged,
    RoomAnalyzed,
    TimeoutEvent,
    ResetEvent,
]
