from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import List, Optional

from auth.passwords import verify_password

from .base import get_connection


@dataclass
class UserRecord:
    id: int
    name: str
    login: str
    password_hash: str
    pin_hash: Optional[str]
    card_id: str
    is_blocked: bool
    access_level: int
    face_embedding: Optional[bytes]
    role: str = "user"
    status: str = "active"  # pending | active | rejected
    approved_by: Optional[int] = None
    approved_at: Optional[dt.datetime] = None


@dataclass
class EventRecord:
    id: int
    timestamp: dt.datetime
    level: str
    message: str
    reason: Optional[str]
    state: str
    card_id: Optional[str]
    user_id: Optional[int]


def create_tables_if_not_exists() -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            login TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            pin_hash TEXT,
            card_id TEXT NOT NULL UNIQUE,
            is_blocked INTEGER NOT NULL DEFAULT 0,
            access_level INTEGER NOT NULL DEFAULT 1,
            face_embedding BLOB,
            role TEXT NOT NULL DEFAULT 'user',
            status TEXT NOT NULL DEFAULT 'active',
            approved_by INTEGER,
            approved_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            reason TEXT,
            state TEXT NOT NULL,
            card_id TEXT,
            user_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )
    _migrate_users_table(conn)
    conn.commit()


def _row_to_user(row) -> UserRecord:
    role_value = "user"
    status_value = "active"
    approved_by_value = None
    approved_at_value = None
    pin_hash_value = row["pin_hash"] if "pin_hash" in row.keys() else None
    if hasattr(row, "keys"):
        keys = row.keys()
        if "role" in keys:
            role_value = row["role"]
        if "status" in keys:
            status_value = row["status"]
        if "approved_by" in keys:
            approved_by_value = row["approved_by"]
        if "approved_at" in keys and row["approved_at"]:
            approved_at_value = dt.datetime.fromisoformat(row["approved_at"])
    return UserRecord(
        id=row["id"],
        name=row["name"],
        login=row["login"],
        password_hash=row["password_hash"],
        pin_hash=pin_hash_value,
        card_id=row["card_id"],
        is_blocked=bool(row["is_blocked"]),
        access_level=row["access_level"],
        face_embedding=row["face_embedding"],
        role=role_value,
        status=status_value,
        approved_by=approved_by_value,
        approved_at=approved_at_value,
    )


def get_user_by_card(card_id: str) -> Optional[UserRecord]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE card_id = ?;", (card_id,))
    row = cur.fetchone()
    if row is None:
        return None
    return _row_to_user(row)


def get_user_by_login(login: str) -> Optional[UserRecord]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE login = ?;", (login,))
    row = cur.fetchone()
    if row is None:
        return None
    return _row_to_user(row)


def get_user_by_id(user_id: int) -> Optional[UserRecord]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?;", (user_id,))
    row = cur.fetchone()
    if row is None:
        return None
    return _row_to_user(row)


def find_user_by_pin(pin: str) -> Optional[UserRecord]:
    """Linear search over users verifying bcrypt pin hashes (demo-scale)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE pin_hash IS NOT NULL;")
    rows = cur.fetchall()
    for row in rows:
        user = _row_to_user(row)
        if user.pin_hash and verify_password(pin, user.pin_hash):
            return user
    return None


def create_user(
    name: str,
    login: str,
    password_hash: str,
    card_id: str,
    access_level: int = 1,
    is_blocked: bool = False,
    face_embedding: Optional[bytes] = None,
    role: str = "user",
    status: str = "pending",
    approved_by: Optional[int] = None,
    approved_at: Optional[dt.datetime] = None,
    pin_hash: Optional[str] = None,
) -> int:
    conn = get_connection()
    cur = conn.cursor()
    now = dt.datetime.now().isoformat()
    approved_at_iso = approved_at.isoformat() if approved_at else None
    cur.execute(
        """
        INSERT INTO users (name, login, password_hash, pin_hash, card_id, is_blocked, access_level, face_embedding, role, status, approved_by, approved_at, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            name,
            login,
            password_hash,
            pin_hash,
            card_id,
            int(is_blocked),
            access_level,
            face_embedding,
            role,
            status,
            approved_by,
            approved_at_iso,
            now,
            now,
        ),
    )
    conn.commit()
    return cur.lastrowid


def update_user(
    user_id: int,
    name: Optional[str] = None,
    login: Optional[str] = None,
    password_hash: Optional[str] = None,
    pin_hash: Optional[str] = None,
    card_id: Optional[str] = None,
    access_level: Optional[int] = None,
    is_blocked: Optional[bool] = None,
    face_embedding: Optional[bytes] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    approved_by: Optional[int] = None,
    approved_at: Optional[dt.datetime] = None,
) -> None:
    conn = get_connection()
    cur = conn.cursor()
    fields = []
    values = []
    if name is not None:
        fields.append("name = ?")
        values.append(name)
    if login is not None:
        fields.append("login = ?")
        values.append(login)
    if password_hash is not None:
        fields.append("password_hash = ?")
        values.append(password_hash)
    if pin_hash is not None:
        fields.append("pin_hash = ?")
        values.append(pin_hash)
    if card_id is not None:
        fields.append("card_id = ?")
        values.append(card_id)
    if access_level is not None:
        fields.append("access_level = ?")
        values.append(access_level)
    if is_blocked is not None:
        fields.append("is_blocked = ?")
        values.append(int(is_blocked))
    if face_embedding is not None:
        fields.append("face_embedding = ?")
        values.append(face_embedding)
    if role is not None:
        fields.append("role = ?")
        values.append(role)
    if status is not None:
        fields.append("status = ?")
        values.append(status)
    if approved_by is not None:
        fields.append("approved_by = ?")
        values.append(approved_by)
    if approved_at is not None:
        fields.append("approved_at = ?")
        values.append(approved_at.isoformat())
    if not fields:
        return
    fields.append("updated_at = ?")
    values.append(dt.datetime.now().isoformat())
    values.append(user_id)
    sql = "UPDATE users SET " + ", ".join(fields) + " WHERE id = ?;"
    cur.execute(sql, tuple(values))
    conn.commit()


def clear_face_embedding(user_id: int) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET face_embedding = NULL, updated_at = ? WHERE id = ?;",
        (dt.datetime.now().isoformat(), user_id),
    )
    conn.commit()


def delete_user(user_id: int) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id = ?;", (user_id,))
    conn.commit()


def list_users() -> List[UserRecord]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users ORDER BY id;")
    rows = cur.fetchall()
    return [_row_to_user(r) for r in rows]


def set_user_status(
    user_id: int, status: str, approved_by: Optional[int] = None
) -> None:
    now = dt.datetime.now().isoformat()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE users SET status = ?, approved_by = ?, approved_at = ?, updated_at = ?
        WHERE id = ?;
        """,
        (status, approved_by, now, now, user_id),
    )
    conn.commit()


def insert_event(
    level: str,
    message: str,
    reason: Optional[str],
    state: str,
    card_id: Optional[str],
    user_id: Optional[int],
) -> int:
    conn = get_connection()
    cur = conn.cursor()
    ts = dt.datetime.now().isoformat()
    cur.execute(
        """
        INSERT INTO events (timestamp, level, message, reason, state, card_id, user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        (ts, level, message, reason, state, card_id, user_id),
    )
    conn.commit()
    return cur.lastrowid


def get_events(limit: int = 100) -> List[EventRecord]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM events
        ORDER BY id DESC
        LIMIT ?;
        """,
        (limit,),
    )
    rows = cur.fetchall()
    result: List[EventRecord] = []
    for row in rows:
        result.append(
            EventRecord(
                id=row["id"],
                timestamp=dt.datetime.fromisoformat(row["timestamp"]),
                level=row["level"],
                message=row["message"],
                reason=row["reason"],
                state=row["state"],
                card_id=row["card_id"],
                user_id=row["user_id"],
            )
        )
    return result


def _migrate_users_table(conn) -> None:
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(users);")
    rows = cur.fetchall()
    columns = {row["name"] for row in rows}
    altered = False
    if "login" not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN login TEXT;")
        altered = True
    if "password_hash" not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN password_hash TEXT;")
        altered = True
    if "pin_hash" not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN pin_hash TEXT;")
        altered = True
    if "role" not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user';")
        altered = True
    if "status" not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active';")
        altered = True
    if "approved_by" not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN approved_by INTEGER;")
        altered = True
    if "approved_at" not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN approved_at TEXT;")
        altered = True
    if altered:
        conn.commit()
    cur.execute(
        "UPDATE users SET login = COALESCE(login, card_id) WHERE login IS NULL;"
    )
    cur.execute(
        "UPDATE users SET password_hash = COALESCE(password_hash, '') WHERE password_hash IS NULL;"
    )
    cur.execute(
        "UPDATE users SET pin_hash = COALESCE(pin_hash, password_hash) WHERE pin_hash IS NULL;"
    )
    cur.execute("UPDATE users SET role = COALESCE(role, 'user') WHERE role IS NULL;")
    cur.execute(
        "UPDATE users SET status = COALESCE(status, 'active') WHERE status IS NULL;"
    )
    conn.commit()
