import os
import sqlite3

from db import init_db as init_module


def test_init_db_retries_locked_without_switching_db_path(monkeypatch, tmp_path):
    db_path = tmp_path / "eyegate_scud.db"
    monkeypatch.setenv("EYEGATE_DB_PATH", str(db_path))

    calls = {"count": 0}

    def flaky_create_tables_if_not_exists():
        calls["count"] += 1
        if calls["count"] < 3:
            raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(
        init_module, "create_tables_if_not_exists", flaky_create_tables_if_not_exists
    )
    monkeypatch.setattr(init_module, "get_user_by_card", lambda _card_id: object())
    monkeypatch.setattr(init_module, "_ensure_admin_seed", lambda: None)

    init_module.init_db()

    assert os.getenv("EYEGATE_DB_PATH") == str(db_path)
    assert calls["count"] == 3
