import sys

import pytest

from db import base


def test_windows_wsl_unc_db_path_is_rejected(monkeypatch):
    base.close_all_connections()
    monkeypatch.setattr(sys, "platform", "win32", raising=False)
    monkeypatch.setenv(
        "EYEGATE_DB_PATH",
        r"\\wsl.localhost\Ubuntu\home\user\eyegate-mantrap\data\eyegate_scud.db",
    )

    with pytest.raises(RuntimeError) as exc:
        base.get_connection()

    msg = str(exc.value).lower()
    assert "wsl" in msg
    assert "eyegate_db_path" in msg or "\\\\wsl" in msg
