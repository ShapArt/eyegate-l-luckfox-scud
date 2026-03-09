from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

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
    TransitionResult,
)


@dataclass
class GateContext:
    """Контекст текущего прохода."""

    current_card_id: Optional[str] = None
    current_user_id: Optional[int] = None
    last_face_match: Optional[FaceMatch] = None
    last_people_count: Optional[int] = None
    last_match_distance: Optional[float] = None
    last_matched_user_id: Optional[int] = None

    def clear(self) -> None:
        self.current_card_id = None
        self.current_user_id = None
        self.last_face_match = None
        self.last_people_count = None
        self.last_match_distance = None
        self.last_matched_user_id = None


@dataclass
class GateFSM:
    """Чистый конечный автомат шлюза."""

    state: GateState = GateState.IDLE
    ctx: GateContext = field(default_factory=GateContext)

    def handle_event(self, event: GateEvent) -> TransitionResult:
        if isinstance(event, ResetEvent):
            return self._handle_reset(event)

        if self.state == GateState.IDLE:
            return self._on_idle(event)
        if self.state == GateState.WAIT_ENTER:
            return self._on_wait_enter(event)
        if self.state == GateState.CHECK_ROOM:
            return self._on_check_room(event)
        if self.state == GateState.ACCESS_GRANTED:
            return self._on_access_granted(event)
        if self.state == GateState.ACCESS_DENIED:
            return self._on_access_denied(event)
        if self.state == GateState.ALARM:
            return self._on_alarm(event)
        if self.state == GateState.RESET:
            return self._on_reset_state(event)

        return self._transition_to(
            GateState.IDLE,
            [
                Action(
                    ActionType.LOG_EVENT, message="Unknown state, forcing reset to IDLE"
                )
            ],
            clear_context=True,
        )

    def _transition_to(
        self,
        next_state: GateState,
        actions: Optional[List[Action]] = None,
        clear_context: bool = False,
    ) -> TransitionResult:
        if actions is None:
            actions = []
        if clear_context:
            self.ctx.clear()
            actions.append(Action(ActionType.CLEAR_CONTEXT, message="Clearing context"))
        self.state = next_state
        return TransitionResult(next_state=next_state, actions=actions)

    def _on_idle(self, event: GateEvent) -> TransitionResult:
        actions: List[Action] = []

        if isinstance(event, CardPresented):
            self.ctx.current_card_id = event.card_id
            actions.append(
                Action(
                    ActionType.LOG_EVENT,
                    message=f"Card presented: {event.card_id}",
                )
            )
            actions.extend(
                [
                    Action(ActionType.UNLOCK_DOOR1, message="Unlock door 1 (card tap)"),
                    Action(
                        ActionType.START_ENTER_TIMEOUT, message="Start enter timeout"
                    ),
                ]
            )
            return self._transition_to(GateState.WAIT_ENTER, actions)

        if isinstance(event, AuthResult):
            if not event.allow:
                actions.append(
                    Action(
                        ActionType.LOG_EVENT,
                        message="Auth denied",
                        reason=event.reason,
                    )
                )
                return self._transition_to(GateState.IDLE, actions, clear_context=True)

            self.ctx.current_user_id = event.user_id
            actions.extend(
                [
                    Action(
                        ActionType.LOG_EVENT,
                        message=f"Auth OK for user_id={event.user_id}",
                    ),
                    Action(
                        ActionType.UNLOCK_DOOR1,
                        message="Unlock door 1 for entry",
                    ),
                    Action(
                        ActionType.START_ENTER_TIMEOUT,
                        message="Start enter timeout",
                    ),
                ]
            )
            return self._transition_to(GateState.WAIT_ENTER, actions)

        actions.append(
            Action(
                ActionType.LOG_EVENT,
                message=f"IDLE: ignoring event {event.type}",
            )
        )
        return self._transition_to(GateState.IDLE, actions)

    def _on_wait_enter(self, event: GateEvent) -> TransitionResult:
        actions: List[Action] = []

        if isinstance(event, AuthResult):
            if not event.allow:
                actions.extend(
                    [
                        Action(
                            ActionType.LOG_EVENT,
                            message="Auth denied in WAIT_ENTER",
                            reason=event.reason,
                        ),
                        Action(ActionType.LOCK_DOOR1, message="Lock door 1"),
                        Action(
                            ActionType.CANCEL_ALL_TIMEOUTS, message="Cancel timeouts"
                        ),
                    ]
                )
                return self._transition_to(GateState.RESET, actions, clear_context=True)
            self.ctx.current_user_id = event.user_id
            actions.append(
                Action(ActionType.LOG_EVENT, message="Auth approved in WAIT_ENTER")
            )
            actions.append(
                Action(ActionType.UNLOCK_DOOR1, message="Ensure door 1 unlocked")
            )
            actions.append(
                Action(ActionType.START_ENTER_TIMEOUT, message="Restart enter timeout")
            )
            return self._transition_to(GateState.WAIT_ENTER, actions)

        if isinstance(event, DoorClosedChanged) and event.door == 1:
            if event.is_closed:
                actions.extend(
                    [
                        Action(
                            ActionType.LOG_EVENT,
                            message="Door 1 closed, starting room analysis",
                        ),
                        Action(
                            ActionType.LOCK_DOOR1,
                            message="Lock door 1",
                        ),
                        Action(
                            ActionType.LOCK_DOOR2,
                            message="Ensure door 2 is locked",
                        ),
                        Action(
                            ActionType.START_ROOM_ANALYSIS,
                            message="Request room analysis",
                        ),
                        Action(
                            ActionType.START_CHECK_TIMEOUT,
                            message="Start check timeout",
                        ),
                    ]
                )
                return self._transition_to(GateState.CHECK_ROOM, actions)

            actions.append(
                Action(
                    ActionType.LOG_EVENT,
                    message="Door 1 opened in WAIT_ENTER",
                )
            )
            return self._transition_to(GateState.WAIT_ENTER, actions)

        if isinstance(event, TimeoutEvent) and event.type == EventType.TIMEOUT_ENTER:
            actions.extend(
                [
                    Action(
                        ActionType.LOG_EVENT,
                        message="Enter timeout, canceling attempt",
                        reason="TIMEOUT_ENTER",
                    ),
                    Action(
                        ActionType.LOCK_DOOR1,
                        message="Lock door 1",
                    ),
                    Action(
                        ActionType.CANCEL_ALL_TIMEOUTS,
                        message="Cancel all timeouts",
                    ),
                ]
            )
            return self._transition_to(GateState.IDLE, actions, clear_context=True)

        actions.append(
            Action(
                ActionType.LOG_EVENT,
                message=f"WAIT_ENTER: ignoring event {event.type}",
            )
        )
        return self._transition_to(GateState.WAIT_ENTER, actions)

    def _on_check_room(self, event: GateEvent) -> TransitionResult:
        actions: List[Action] = []

        if isinstance(event, RoomAnalyzed):
            self.ctx.last_people_count = event.people_count
            self.ctx.last_face_match = event.face_match
            self.ctx.last_match_distance = event.match_distance
            self.ctx.last_matched_user_id = event.matched_user_id
            policy_action = getattr(event, "policy_action", None)
            policy_reason = getattr(event, "policy_reason", None)

            if event.stale:
                actions.extend(
                    [
                        Action(
                            ActionType.LOG_EVENT,
                            message="Vision stale, waiting for fresh frame",
                            reason="VISION_STALE",
                        ),
                        Action(
                            ActionType.LOCK_DOOR2,
                            message="Keep door 2 locked until fresh vision",
                        ),
                        Action(
                            ActionType.START_ROOM_ANALYSIS,
                            message="Retry room analysis",
                        ),
                    ]
                )
                return self._transition_to(GateState.CHECK_ROOM, actions)

            # Policy-aware actions
            if policy_action == "alarm":
                actions.extend(
                    [
                        Action(
                            ActionType.LOG_EVENT,
                            message="Policy => ALARM",
                            reason=policy_reason,
                        ),
                        Action(ActionType.LOCK_BOTH, message="Lock both doors"),
                        Action(ActionType.SET_ALARM_ON, message="Alarm ON"),
                        Action(
                            ActionType.START_ALARM_TIMEOUT,
                            message="Start alarm timeout",
                        ),
                    ]
                )
                return self._transition_to(GateState.ALARM, actions)
            if policy_action == "deny":
                actions.extend(
                    [
                        Action(
                            ActionType.LOG_EVENT,
                            message="Policy => DENY",
                            reason=policy_reason,
                        ),
                        Action(ActionType.LOCK_BOTH, message="Lock both doors"),
                        Action(
                            ActionType.CANCEL_ALL_TIMEOUTS, message="Cancel timeouts"
                        ),
                    ]
                )
                return self._transition_to(GateState.ACCESS_DENIED, actions)
            if policy_action == "open_door2":
                actions.extend(
                    [
                        Action(
                            ActionType.LOG_EVENT,
                            message="Policy => OPEN_DOOR2",
                            reason=policy_reason,
                        ),
                        Action(ActionType.LOCK_DOOR1, message="Ensure door 1 locked"),
                        Action(ActionType.UNLOCK_DOOR2, message="Unlock door 2"),
                        Action(
                            ActionType.CANCEL_ALL_TIMEOUTS,
                            message="Cancel check timeout",
                        ),
                        Action(
                            ActionType.START_EXIT_TIMEOUT, message="Start exit timeout"
                        ),
                    ]
                )
                return self._transition_to(GateState.ACCESS_GRANTED, actions)
            if policy_action == "wait":
                actions.extend(
                    [
                        Action(
                            ActionType.LOG_EVENT,
                            message="Policy => WAIT",
                            reason=policy_reason,
                        ),
                        Action(ActionType.LOCK_DOOR2, message="Keep door 2 locked"),
                        Action(
                            ActionType.START_ROOM_ANALYSIS,
                            message="Retry room analysis",
                        ),
                    ]
                )
                return self._transition_to(GateState.CHECK_ROOM, actions)

            # Fallback legacy behavior
            if event.face_match == FaceMatch.NO_FACE or event.people_count == 0:
                actions.extend(
                    [
                        Action(
                            ActionType.LOG_EVENT,
                            message=(
                                f"Room empty or no face yet "
                                f"(people_count={event.people_count}, face_match={event.face_match.name}), waiting"
                            ),
                            reason="NO_FACE_OR_EMPTY",
                        ),
                        Action(ActionType.LOCK_DOOR2, message="Keep door 2 locked"),
                        Action(
                            ActionType.START_ROOM_ANALYSIS,
                            message="Retry room analysis",
                        ),
                    ]
                )
                return self._transition_to(GateState.CHECK_ROOM, actions)

        if isinstance(event, TimeoutEvent) and event.type == EventType.TIMEOUT_CHECK:
            actions.extend(
                [
                    Action(
                        ActionType.LOG_EVENT,
                        message="ACCESS_DENIED: check timeout",
                        reason="TIMEOUT_CHECK",
                    ),
                    Action(ActionType.LOCK_BOTH, message="Lock both doors"),
                    Action(
                        ActionType.CANCEL_ALL_TIMEOUTS,
                        message="Cancel check timeout",
                    ),
                ]
            )
            return self._transition_to(GateState.IDLE, actions, clear_context=True)

        actions.append(
            Action(
                ActionType.LOG_EVENT,
                message=f"CHECK_ROOM: ignoring event {event.type}",
            )
        )
        return self._transition_to(GateState.CHECK_ROOM, actions)

    def _on_access_granted(self, event: GateEvent) -> TransitionResult:
        actions: List[Action] = []

        if isinstance(event, DoorClosedChanged) and event.door == 2:
            if event.is_closed:
                actions.extend(
                    [
                        Action(
                            ActionType.LOG_EVENT,
                            message="Door 2 closed, access cycle completed",
                        ),
                        Action(
                            ActionType.LOCK_DOOR2,
                            message="Lock door 2",
                        ),
                        Action(
                            ActionType.CANCEL_ALL_TIMEOUTS,
                            message="Cancel exit timeout",
                        ),
                    ]
                )
                return self._transition_to(
                    GateState.IDLE,
                    actions,
                    clear_context=True,
                )

            actions.append(
                Action(
                    ActionType.LOG_EVENT,
                    message="Door 2 opened in ACCESS_GRANTED",
                )
            )
            return self._transition_to(GateState.ACCESS_GRANTED, actions)

        if isinstance(event, TimeoutEvent) and event.type == EventType.TIMEOUT_EXIT:
            actions.extend(
                [
                    Action(
                        ActionType.LOG_EVENT,
                        message="ACCESS_DENIED: exit timeout",
                        reason="TIMEOUT_EXIT",
                    ),
                    Action(
                        ActionType.LOCK_DOOR2,
                        message="Lock door 2",
                    ),
                    Action(
                        ActionType.CANCEL_ALL_TIMEOUTS,
                        message="Cancel exit timeout",
                    ),
                ]
            )
            return self._transition_to(GateState.RESET, actions, clear_context=True)

        actions.append(
            Action(
                ActionType.LOG_EVENT,
                message=f"ACCESS_GRANTED: ignoring event {event.type}",
            )
        )
        return self._transition_to(GateState.ACCESS_GRANTED, actions)

    def _on_access_denied(self, event: GateEvent) -> TransitionResult:
        actions: List[Action] = []

        if isinstance(event, ResetEvent):
            return self._transition_to(GateState.RESET, actions, clear_context=True)

        actions.append(
            Action(
                ActionType.LOG_EVENT,
                message=f"ACCESS_DENIED: waiting for RESET, ignoring {event.type}",
            )
        )
        return self._transition_to(GateState.ACCESS_DENIED, actions)

    def _on_alarm(self, event: GateEvent) -> TransitionResult:
        actions: List[Action] = []

        if isinstance(event, ResetEvent):
            actions.extend(
                [
                    Action(
                        ActionType.LOG_EVENT,
                        message="ALARM: reset by operator",
                    ),
                    Action(ActionType.SET_ALARM_OFF, message="Alarm OFF"),
                    Action(ActionType.LOCK_BOTH, message="Lock both doors"),
                    Action(
                        ActionType.CANCEL_ALL_TIMEOUTS,
                        message="Cancel alarm timeout",
                    ),
                ]
            )
            return self._transition_to(GateState.RESET, actions, clear_context=True)

        if isinstance(event, TimeoutEvent) and event.type == EventType.TIMEOUT_ALARM:
            actions.extend(
                [
                    Action(
                        ActionType.LOG_EVENT,
                        message="ALARM: auto reset after timeout",
                        reason="TIMEOUT_ALARM",
                    ),
                    Action(ActionType.SET_ALARM_OFF, message="Alarm OFF"),
                    Action(ActionType.LOCK_BOTH, message="Lock both doors"),
                ]
            )
            return self._transition_to(GateState.RESET, actions, clear_context=True)

        actions.append(
            Action(
                ActionType.LOG_EVENT,
                message=f"ALARM: ignoring event {event.type}",
            )
        )
        return self._transition_to(GateState.ALARM, actions)

    def _on_reset_state(self, event: GateEvent) -> TransitionResult:
        actions: List[Action] = []
        actions.append(
            Action(
                ActionType.LOG_EVENT,
                message=f"RESET: transition to IDLE on event {event.type}",
            )
        )
        return self._transition_to(GateState.IDLE, actions)

    def _handle_reset(self, event: ResetEvent) -> TransitionResult:
        actions = [
            Action(
                ActionType.LOG_EVENT,
                message=f"Global RESET from state {self.state.name}",
            ),
            Action(ActionType.SET_ALARM_OFF, message="Alarm OFF"),
            Action(ActionType.LOCK_BOTH, message="Lock both doors"),
            Action(ActionType.CANCEL_ALL_TIMEOUTS, message="Cancel all timeouts"),
        ]
        return self._transition_to(GateState.RESET, actions, clear_context=True)
