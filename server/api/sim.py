from __future__ import annotations

from fastapi import APIRouter

from hw.simulated import SimulatedDoors
from server.api.common import fail
from server.deps import get_gate_controller
from server.schemas import SimState
from server.status_bus import status_bus

router = APIRouter()


def _get_simulator() -> SimulatedDoors:
    controller = get_gate_controller()
    doors = getattr(controller, "_doors", None)
    if not isinstance(doors, SimulatedDoors):
        fail(400, "SIM_DISABLED", "Simulator not enabled")
    return doors
    return doors


@router.get("/", response_model=SimState)
async def get_state() -> SimState:
    doors = _get_simulator()
    st = doors.snapshot()
    return SimState(
        door1_closed=st.door1_closed,
        door2_closed=st.door2_closed,
        lock1_unlocked=st.lock1_unlocked,
        lock2_unlocked=st.lock2_unlocked,
        lock1_power=st.lock1_power,
        lock2_power=st.lock2_power,
        sensor1_open=getattr(st, "sensor1_open", None),
        sensor2_open=getattr(st, "sensor2_open", None),
        auto_close_ms=doors.auto_close_ms(),
        door1_auto_close_ms=doors.auto_close_ms(1),
        door2_auto_close_ms=doors.auto_close_ms(2),
    )


@router.post("/door/{door_id}/{action}", response_model=SimState)
async def set_door(
    door_id: int,
    action: str,
) -> SimState:
    controller = get_gate_controller()
    doors = _get_simulator()
    if door_id not in (1, 2):
        fail(400, "BAD_DOOR", "door_id must be 1 or 2")
    if action not in ("open", "close", "power_on", "power_off"):
        fail(400, "BAD_ACTION", "Unsupported action")
    if action == "open":
        doors.open_door(door_id)
    elif action == "close":
        doors.close_door(door_id)
    elif action == "power_on":
        doors.power_lock(door_id, True)
    elif action == "power_off":
        doors.power_lock(door_id, False)
    st = doors.snapshot()
    # Broadcast fresh status so the simulator UI syncs immediately.
    try:
        await status_bus.broadcast(controller.snapshot())
    except Exception:
        pass
    return SimState(
        door1_closed=st.door1_closed,
        door2_closed=st.door2_closed,
        lock1_unlocked=st.lock1_unlocked,
        lock2_unlocked=st.lock2_unlocked,
        lock1_power=st.lock1_power,
        lock2_power=st.lock2_power,
        sensor1_open=getattr(st, "sensor1_open", None),
        sensor2_open=getattr(st, "sensor2_open", None),
        auto_close_ms=doors.auto_close_ms(),
        door1_auto_close_ms=doors.auto_close_ms(1),
        door2_auto_close_ms=doors.auto_close_ms(2),
    )


@router.post("/sensor/{door_id}/{state}", response_model=SimState)
async def set_sensor(door_id: int, state: str) -> SimState:
    controller = get_gate_controller()
    doors = _get_simulator()
    if door_id not in (1, 2):
        fail(400, "BAD_DOOR", "door_id must be 1 or 2")
    if state not in ("open", "closed"):
        fail(400, "BAD_STATE", "state must be open or closed")
    doors.set_sensor(door_id, is_closed=(state == "closed"))
    st = doors.snapshot()
    try:
        await status_bus.broadcast(controller.snapshot())
    except Exception:
        pass
    return SimState(
        door1_closed=st.door1_closed,
        door2_closed=st.door2_closed,
        lock1_unlocked=st.lock1_unlocked,
        lock2_unlocked=st.lock2_unlocked,
        lock1_power=st.lock1_power,
        lock2_power=st.lock2_power,
        sensor1_open=getattr(st, "sensor1_open", None),
        sensor2_open=getattr(st, "sensor2_open", None),
        auto_close_ms=doors.auto_close_ms(),
        door1_auto_close_ms=doors.auto_close_ms(1),
        door2_auto_close_ms=doors.auto_close_ms(2),
    )


@router.post("/auto_close", response_model=SimState)
async def set_auto_close(payload: dict) -> SimState:
    controller = get_gate_controller()
    doors = _get_simulator()
    try:
        delay_ms = int(payload.get("delay_ms", 0))
    except Exception:
        fail(400, "BAD_DELAY", "delay_ms must be int")
    door_id = payload.get("door_id")
    if door_id is not None:
        try:
            door_id_int = int(door_id)
        except Exception:
            fail(400, "BAD_DOOR", "door_id must be 1 or 2")
        if door_id_int not in (1, 2):
            fail(400, "BAD_DOOR", "door_id must be 1 or 2")
        doors.set_auto_close(delay_ms if delay_ms >= 0 else None, door=door_id_int)
    else:
        doors.set_auto_close(delay_ms if delay_ms >= 0 else None)
    st = doors.snapshot()
    try:
        await status_bus.broadcast(controller.snapshot())
    except Exception:
        pass
    return SimState(
        door1_closed=st.door1_closed,
        door2_closed=st.door2_closed,
        lock1_unlocked=st.lock1_unlocked,
        lock2_unlocked=st.lock2_unlocked,
        lock1_power=st.lock1_power,
        lock2_power=st.lock2_power,
        auto_close_ms=doors.auto_close_ms(),
        door1_auto_close_ms=doors.auto_close_ms(1),
        door2_auto_close_ms=doors.auto_close_ms(2),
    )
