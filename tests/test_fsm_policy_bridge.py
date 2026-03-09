from gate.fsm import GateFSM
from gate.models import ActionType, FaceMatch, RoomAnalyzed, TransitionResult


def _actions_of(result: TransitionResult, atype: ActionType) -> bool:
    return any(a.type == atype for a in result.actions)


def test_policy_open_unlocks_door2():
    fsm = GateFSM()
    fsm.state = fsm.state.CHECK_ROOM  # type: ignore[assignment]
    res = fsm.handle_event(
        RoomAnalyzed(
            people_count=1,
            face_match=FaceMatch.MATCH,
            policy_action="open_door2",
            policy_reason="SINGLE_RECOGNIZED",
        )
    )
    assert res.next_state.name == "ACCESS_GRANTED"
    assert _actions_of(res, ActionType.UNLOCK_DOOR2)


def test_policy_alarm_triggers_alarm_actions():
    fsm = GateFSM()
    fsm.state = fsm.state.CHECK_ROOM  # type: ignore[assignment]
    res = fsm.handle_event(
        RoomAnalyzed(
            people_count=2,
            face_match=FaceMatch.NO_MATCH,
            policy_action="alarm",
            policy_reason="TAILGATING",
        )
    )
    assert res.next_state.name == "ALARM"
    assert _actions_of(res, ActionType.SET_ALARM_ON)
    assert _actions_of(res, ActionType.LOCK_BOTH)
