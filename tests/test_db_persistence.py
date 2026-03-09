from fastapi.testclient import TestClient

import db.base as base
from server import deps as server_deps
from server.main import create_app


def _close_db():
    if getattr(base, "_DB_CONN", None) is not None:
        try:
            base._DB_CONN.close()  # type: ignore[attr-defined]
        except Exception:
            pass
        base._DB_CONN = None  # type: ignore[attr-defined]


def test_user_persists_after_restart(client):
    # create user through API
    payload = {
        "login": "persist_user",
        "pin": "1234",
        "name": "Persist",
        "access_level": 1,
        "is_blocked": False,
    }
    resp = client.post("/api/users/", json=payload)
    assert resp.status_code == 200
    created = resp.json()
    assert created["login"] == "persist_user"

    # simulate restart: drop cached controller/config + DB connection
    server_deps.get_gate_controller.cache_clear()
    server_deps.get_config.cache_clear()
    _close_db()

    # new app instance should see the same DB file
    app = create_app()
    with TestClient(app) as c2:
        resp2 = c2.get("/api/users/")
        assert resp2.status_code == 200
        logins = [u["login"] for u in resp2.json()]
        assert "persist_user" in logins
