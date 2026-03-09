import asyncio

import pytest

from gate.controller import GateController
from gate.models import AuthResult, DoorClosedChanged, FaceMatch, GateState


@pytest.mark.asyncio
async def test_room_analysis_opens_door2_when_single_known(running_controller):
    ctrl: GateController = running_controller
    ctrl._config.door1_close_stabilize_ms = 5
    ctrl._config.room_check_samples = 1
    ctrl._config.check_timeout_sec = 1.0
    ctrl._config.enter_timeout_sec = 1.0
    # Vision dummy: 1 person, recognized user 1
    ctrl._vision.set_values(people_count=1, face_match=FaceMatch.MATCH, recognized_user_ids=[1])  # type: ignore[attr-defined]

    await ctrl._queue.put(AuthResult(allow=True, reason="TEST", user_id=1))  # type: ignore[attr-defined]
    await ctrl._queue.put(DoorClosedChanged(door=1, is_closed=True))

    await asyncio.sleep(0.2)

    assert ctrl.state == GateState.ACCESS_GRANTED
    # Door2 should be unlocked by the FSM action
    doors_state = getattr(ctrl._doors, "state", None)  # type: ignore[attr-defined]
    assert doors_state and doors_state.door2_locked is False


@pytest.mark.asyncio
async def test_room_analysis_alarms_on_unknown_multi(running_controller):
    ctrl: GateController = running_controller
    ctrl._config.door1_close_stabilize_ms = 5
    ctrl._config.room_check_samples = 1
    ctrl._config.check_timeout_sec = 1.0
    ctrl._config.enter_timeout_sec = 1.0
    ctrl._config.max_people_allowed = 1
    ctrl._vision.set_values(people_count=2, face_match=FaceMatch.NO_MATCH, recognized_user_ids=[])  # type: ignore[attr-defined]

    await ctrl._queue.put(AuthResult(allow=True, reason="TEST", user_id=1))  # type: ignore[attr-defined]
    await ctrl._queue.put(DoorClosedChanged(door=1, is_closed=True))

    await asyncio.sleep(0.2)

    assert ctrl.state == GateState.ALARM


@pytest.mark.asyncio
async def test_camera_down_denies_opening_door2(running_controller):
    ctrl: GateController = running_controller
    ctrl._config.door1_close_stabilize_ms = 5
    ctrl._config.room_check_samples = 1
    ctrl._config.check_timeout_sec = 1.0
    ctrl._config.enter_timeout_sec = 1.0
    # Vision: camera is down => policy must deny
    ctrl._vision.set_values(people_count=1, face_match=FaceMatch.MATCH, recognized_user_ids=[1], camera_ok=False)  # type: ignore[attr-defined]

    await ctrl._queue.put(AuthResult(allow=True, reason="TEST", user_id=1))  # type: ignore[attr-defined]
    await ctrl._queue.put(DoorClosedChanged(door=1, is_closed=True))

    await asyncio.sleep(0.2)

    assert ctrl.state == GateState.ACCESS_DENIED
    doors_state = getattr(ctrl._doors, "state", None)  # type: ignore[attr-defined]
    assert doors_state and doors_state.door2_locked is True
