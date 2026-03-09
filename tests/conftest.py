import asyncio
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

# Ensure project root on sys.path for module imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from auth.service import AuthServiceDB
from db.init_db import init_db
from db.logger import SQLiteEventLogger
from gate.controller import GateConfig, GateController
from gate.fsm import GateFSM
from hw.dummy import DummyAlarm, DummyDoors
from server import deps as server_deps
from vision.service import VisionServiceDummy


class InMemoryLogger(SQLiteEventLogger):
    """In-memory logger: writes to SQLite but can silence stdout."""

    def __init__(self, mirror_to_stdout: bool = False) -> None:
        super().__init__(mirror_to_stdout=mirror_to_stdout)


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    """Fresh SQLite file per test, reset cached connection."""
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.close()
    monkeypatch.setenv("EYEGATE_DB_PATH", tmp.name)
    monkeypatch.setenv("EYEGATE_DEMO_MODE", "0")
    monkeypatch.setenv("EYEGATE_SKIP_STARTUP", "1")
    monkeypatch.setenv("VISION_MODE", "dummy")
    server_deps.get_config.cache_clear()
    server_deps.get_gate_controller.cache_clear()
    import db.base as base  # type: ignore

    if getattr(base, "_DB_CONN", None) is not None:
        try:
            base._DB_CONN.close()  # type: ignore[attr-defined]
        except Exception:
            pass
        base._DB_CONN = None  # type: ignore[attr-defined]
    conn = sqlite3.connect(tmp.name, timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    base._DB_CONN = conn  # type: ignore[attr-defined]
    init_db()
    yield
    import db.base as base  # type: ignore

    if getattr(base, "_DB_CONN", None) is not None:
        try:
            base._DB_CONN.close()  # type: ignore[attr-defined]
        except Exception:
            pass
        base._DB_CONN = None  # type: ignore[attr-defined]
    # Do not delete temp DB to avoid Windows locking during teardown.
    if getattr(base, "_DB_CONN", None) is not None:
        try:
            base._DB_CONN.close()  # type: ignore[attr-defined]
        except Exception:
            pass
        base._DB_CONN = None  # type: ignore[attr-defined]


@pytest.fixture
def controller():
    fsm = GateFSM()
    doors = DummyDoors()
    alarm = DummyAlarm()
    vision = VisionServiceDummy()
    auth = AuthServiceDB()
    logger = InMemoryLogger(mirror_to_stdout=False)
    cfg = GateConfig(
        enter_timeout_sec=0.05,
        check_timeout_sec=0.2,
        exit_timeout_sec=0.2,
        alarm_timeout_sec=0.2,
    )
    ctrl = GateController(
        fsm=fsm,
        doors=doors,
        vision=vision,
        auth=auth,
        logger=logger,
        alarm=alarm,
        config=cfg,
    )
    return ctrl


@pytest_asyncio.fixture
async def running_controller(controller):
    """Run GateController loop in background for async tests."""
    task = asyncio.create_task(controller.run())
    await asyncio.sleep(0)
    yield controller
    await controller.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.fixture
def client():
    from server.main import app as fastapi_app

    with TestClient(fastapi_app) as c:
        yield c
