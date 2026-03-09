import time

from vision.service import VisionConfig, VisionServiceOpenCV


def test_user_create_and_pin_login(client):
    create = client.post("/api/users/", json={"login": "user1", "pin": "1234"})
    assert create.status_code == 200
    user = create.json()
    assert user["login"] == "user1"

    auth = client.post("/api/auth/pin", json={"pin": "1234"})
    assert auth.status_code == 200
    payload = auth.json()
    assert payload["status"] == "ok"
    assert payload["userId"] == user["id"]

    status = client.get("/api/status/").json()
    assert "doors" in status
    assert "vision" in status


def test_sim_door_actions(client):
    opened = client.post("/api/sim/door/1/open").json()
    assert opened["door1_closed"] is False
    closed = client.post("/api/sim/door/1/close").json()
    assert closed["door1_closed"] is True


def test_ws_status_snapshot(client):
    with client.websocket_connect("/ws/status") as ws:
        msg = ws.receive_json()
        assert "vision" in msg
        assert "doors" in msg
        assert "state" in msg


def test_vision_placeholder_people_zero():
    svc = VisionServiceOpenCV(VisionConfig(camera_index=99), lambda _uid: None)
    time.sleep(0.2)
    snap = svc.last_snapshot()
    svc.stop()
    assert snap.get("people_count", 0) >= 1
    assert snap.get("vision_state") in (
        None,
        "OFF",
        "WARMUP",
        "DETECTING",
        "DECIDING",
        "ALARM",
        "OK",
    )


class _StubVision:
    def last_snapshot(self):
        return {"people_count": 2, "vision_state": "DETECTING"}


def test_alarm_rule(controller):
    controller._vision = _StubVision()  # type: ignore[attr-defined]
    snap = controller.snapshot()
    assert snap["alarm_on"] is True
    assert snap["vision"]["vision_state"] == "ALARM"
