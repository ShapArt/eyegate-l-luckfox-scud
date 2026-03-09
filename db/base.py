from __future__ import annotations

import logging
import os
import sqlite3
import sys
import threading
import time
from pathlib import Path
from typing import Optional

_DB_CONN: Optional[sqlite3.Connection] = None
_DB_LOCAL = threading.local()
_OPEN_CONNS: set[sqlite3.Connection] = set()
_OPEN_CONNS_LOCK = threading.Lock()
_ROOT = Path(__file__).resolve().parents[1]
logger = logging.getLogger(__name__)


def _is_wsl_unc_path(path: str) -> bool:
    """
    Detect Windows UNC paths pointing to the WSL filesystem (\\wsl$ / \\wsl.localhost).

    SQLite locking is unreliable on these mounts when using Windows Python, which can
    manifest as long hangs or `database is locked` errors even for simple operations.
    """
    normalized = path.replace("/", "\\").lower()
    return normalized.startswith("\\\\wsl$\\") or normalized.startswith(
        "\\\\wsl.localhost\\"
    )


def get_db_path() -> Path:
    env = os.getenv("EYEGATE_DB_PATH")
    if env:
        # PowerShell sometimes prepends provider text like "Microsoft.PowerShell.Core\FileSystem::"
        # which breaks Path.resolve(); strip it if present.
        provider_prefix = "Microsoft.PowerShell.Core\\FileSystem::"
        if env.startswith(provider_prefix):
            env = env[len(provider_prefix) :]
        if sys.platform.startswith("win") and _is_wsl_unc_path(env):
            raise RuntimeError(
                "SQLite DB path points to the WSL filesystem (\\\\wsl$ / \\\\wsl.localhost). "
                "Windows Python cannot reliably acquire SQLite locks there.\n\n"
                "Fix:\n"
                "  - Run backend/init inside WSL (python3), OR\n"
                "  - Set EYEGATE_DB_PATH to a Windows path (e.g. C:\\\\...\\\\eyegate_scud.db).\n"
            )
        return Path(env).expanduser().resolve()
    return (_ROOT / "data" / "eyegate_scud.db").resolve()


def _set_journal_mode(conn: sqlite3.Connection, preferred: str) -> None:
    """
    Apply journal mode with a fallback when the database is temporarily locked
    (common on Windows/WSL UNC paths with the reload process).
    """
    preferred = preferred.upper()
    candidates = [preferred]
    if preferred != "DELETE":
        candidates.append("DELETE")

    for mode in candidates:
        for attempt in range(3):
            try:
                row = conn.execute(f"PRAGMA journal_mode={mode};").fetchone()
                applied = row[0] if row else mode
                if applied and applied.upper() != mode:
                    logger.warning(
                        "Requested journal_mode=%s but SQLite applied %s", mode, applied
                    )
                return
            except sqlite3.OperationalError as exc:
                msg = str(exc).lower()
                if "locked" in msg and attempt < 2:
                    # Give the other process a moment to release the lock.
                    time.sleep(0.2 * (attempt + 1))
                    continue
                if mode != "DELETE":
                    logger.warning(
                        "journal_mode=%s failed (%s); falling back to DELETE", mode, exc
                    )
                    break
                raise


def get_connection() -> sqlite3.Connection:
    """
    Return a SQLite connection.

    Production: a connection is cached per-thread to avoid sharing a single connection across
    FastAPI threadpool workers (common cause of `database is locked` on reload/concurrency).

    Tests: may inject a global `_DB_CONN` override.
    """
    global _DB_CONN
    if _DB_CONN is not None:
        try:
            _DB_CONN.execute("SELECT 1;")
            return _DB_CONN
        except sqlite3.Error:
            _DB_CONN = None

    existing = getattr(_DB_LOCAL, "conn", None)
    if existing is not None:
        try:
            existing.execute("SELECT 1;")
            return existing
        except sqlite3.Error:
            try:
                existing.close()
            except Exception:
                pass
            try:
                with _OPEN_CONNS_LOCK:
                    _OPEN_CONNS.discard(existing)
            except Exception:
                pass
            _DB_LOCAL.conn = None

    db_path = get_db_path()
    if sys.platform.startswith("win") and _is_wsl_unc_path(str(db_path)):
        raise RuntimeError(
            "SQLite DB path points to the WSL filesystem (\\\\wsl$ / \\\\wsl.localhost). "
            "Windows Python cannot reliably acquire SQLite locks there.\n\n"
            "Fix:\n"
            "  - Run backend/init inside WSL (python3), OR\n"
            "  - Set EYEGATE_DB_PATH to a Windows path (e.g. C:\\\\...\\\\eyegate_scud.db).\n"
        )
    db_path.parent.mkdir(parents=True, exist_ok=True)

    timeout = float(os.getenv("EYEGATE_DB_TIMEOUT", "5.0"))
    busy_timeout_ms = int(timeout * 1000)
    journal_mode_env = os.getenv("EYEGATE_DB_JOURNAL_MODE")
    if journal_mode_env:
        journal_mode = journal_mode_env
    else:
        # On Windows/WSL UNC paths, WAL frequently causes lock issues; default to DELETE.
        journal_mode = "DELETE" if str(db_path).startswith("\\\\") else "WAL"

    for attempt in range(3):
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = sqlite3.connect(
                str(db_path),
                timeout=timeout,
                check_same_thread=False,
                isolation_level=None,
            )
            conn.row_factory = sqlite3.Row
            conn.execute(f"PRAGMA busy_timeout = {busy_timeout_ms};")
            _set_journal_mode(conn, journal_mode)
            conn.execute("PRAGMA foreign_keys = ON;")
            _DB_LOCAL.conn = conn
            with _OPEN_CONNS_LOCK:
                _OPEN_CONNS.add(conn)
            return conn
        except sqlite3.OperationalError as exc:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            if "locked" in str(exc).lower() and attempt < 2:
                time.sleep(0.3 * (attempt + 1))
                continue
            raise

    raise RuntimeError("Unreachable")


def close_connection() -> None:
    """Close the current thread's cached connection (if any)."""
    global _DB_CONN
    if _DB_CONN is not None:
        try:
            _DB_CONN.close()
        except Exception:
            pass
        _DB_CONN = None

    conn = getattr(_DB_LOCAL, "conn", None)
    if conn is None:
        return
    try:
        conn.close()
    except Exception:
        pass
    try:
        with _OPEN_CONNS_LOCK:
            _OPEN_CONNS.discard(conn)
    except Exception:
        pass
    _DB_LOCAL.conn = None


def close_all_connections() -> None:
    """Close all cached connections (used at app shutdown / DB path switches)."""
    global _DB_CONN
    if _DB_CONN is not None:
        try:
            _DB_CONN.close()
        except Exception:
            pass
        _DB_CONN = None

    with _OPEN_CONNS_LOCK:
        conns = list(_OPEN_CONNS)
        _OPEN_CONNS.clear()
    for conn in conns:
        try:
            conn.close()
        except Exception:
            pass
    _DB_LOCAL.conn = None
