import secrets
import time

import aiosqlite

from app.config import DATABASE_PATH

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        _db = await aiosqlite.connect(DATABASE_PATH)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                matrix_user_id TEXT NOT NULL,
                matrix_access_token TEXT NOT NULL,
                created_at REAL NOT NULL,
                last_seen REAL NOT NULL
            )
            """
        )
        await _db.commit()
    return _db


async def close_db() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None


async def create_session(matrix_user_id: str, matrix_access_token: str) -> str:
    db = await get_db()
    session_id = secrets.token_urlsafe(32)
    now = time.time()
    await db.execute(
        "INSERT INTO sessions (session_id, matrix_user_id, matrix_access_token, created_at, last_seen) "
        "VALUES (?, ?, ?, ?, ?)",
        (session_id, matrix_user_id, matrix_access_token, now, now),
    )
    await db.commit()
    return session_id


async def get_session(session_id: str) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT session_id, matrix_user_id, matrix_access_token, created_at, last_seen "
        "FROM sessions WHERE session_id = ?",
        (session_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    await db.execute(
        "UPDATE sessions SET last_seen = ? WHERE session_id = ?",
        (time.time(), session_id),
    )
    await db.commit()
    return dict(row)


async def delete_session(session_id: str) -> None:
    db = await get_db()
    await db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
    await db.commit()
