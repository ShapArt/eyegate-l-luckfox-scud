import time

from fastapi.testclient import TestClient


def test_sensor_endpoint_sets_state(client):
    r = client.post("/api/sim/sensor/1/open")
    assert r.status_code == 200
    body = r.json()
    assert body["door1_closed"] is False
    assert body.get("sensor1_open") is True

    r2 = client.post("/api/sim/sensor/1/closed")
    assert r2.status_code == 200
    assert r2.json()["door1_closed"] is True
    assert r2.json().get("sensor1_open") is False


def test_auto_close(client, monkeypatch):
    # enable small auto close per door
    r = client.post("/api/sim/auto_close", json={"door_id": 1, "delay_ms": 50})
    assert r.status_code == 200
    assert r.json().get("door1_auto_close_ms") == 50

    r_both = client.post("/api/sim/auto_close", json={"door_id": 2, "delay_ms": 30})
    assert r_both.status_code == 200
    assert r_both.json().get("door2_auto_close_ms") == 30

    r2 = client.post("/api/sim/door/1/open")
    assert r2.status_code == 200
    assert r2.json()["door1_closed"] is False
    assert r2.json().get("sensor1_open") is True
    time.sleep(0.08)
    r3 = client.get("/api/sim/")
    assert r3.json()["door1_closed"] is True
    assert r3.json().get("sensor1_open") is False

    # door2 auto-close uses its own delay
    r4 = client.post("/api/sim/door/2/open")
    assert r4.status_code == 200
    assert r4.json()["door2_closed"] is False
    time.sleep(0.05)
    r5 = client.get("/api/sim/")
    assert r5.json()["door2_closed"] is True
    assert r5.json().get("sensor2_open") is False


def test_auto_close_from_env(monkeypatch):
    monkeypatch.setenv("DOOR1_AUTO_CLOSE_SEC", "0.05")
    monkeypatch.setenv("DOOR2_AUTO_CLOSE_SEC", "0.07")

    from server import deps as server_deps

    server_deps.get_config.cache_clear()
    server_deps.get_gate_controller.cache_clear()

    from server.main import app as fastapi_app

    with TestClient(fastapi_app) as client:
        state = client.get("/api/sim/").json()
        assert state["door1_auto_close_ms"] == 50
        assert state["door2_auto_close_ms"] == 70

        opened = client.post("/api/sim/door/1/open")
        assert opened.status_code == 200
        assert opened.json()["door1_closed"] is False
        time.sleep(0.08)
        after = client.get("/api/sim/").json()
        assert after["door1_closed"] is True
        assert after.get("sensor1_open") is False

        opened2 = client.post("/api/sim/door/2/open")
        assert opened2.status_code == 200
        assert opened2.json()["door2_closed"] is False
        time.sleep(0.1)
        after2 = client.get("/api/sim/").json()
        assert after2["door2_closed"] is True
        assert after2.get("sensor2_open") is False
