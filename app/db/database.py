"""
Async SQLite database layer using aiosqlite.
Handles all schema creation and CRUD helpers.
"""
import aiosqlite
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from app.models.schemas import Message, MemoryFact, Session

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    # ── Schema ────────────────────────────────────────────────────────────────

    async def init(self) -> None:
        """Create tables if they don't exist."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS messages (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id  TEXT    NOT NULL,
                    role        TEXT    NOT NULL CHECK(role IN ('user','assistant','system')),
                    content     TEXT    NOT NULL,
                    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
                );

                CREATE INDEX IF NOT EXISTS idx_messages_session
                    ON messages(session_id, created_at);

                CREATE TABLE IF NOT EXISTS memory_facts (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    key         TEXT    NOT NULL UNIQUE,
                    value       TEXT    NOT NULL,
                    source      TEXT    NOT NULL DEFAULT 'manual',
                    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    id          TEXT    PRIMARY KEY,
                    title       TEXT,
                    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
                );
            """)
            await db.commit()
        logger.info("Database initialised at %s", self.db_path)

    # ── Messages ──────────────────────────────────────────────────────────────

    async def add_message(self, session_id: str, role: str, content: str) -> int:
        """Insert a message and return its new id."""
        # Ensure session row exists
        await self._ensure_session(session_id)
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content),
            )
            await db.commit()
            return cursor.lastrowid

    async def get_recent_messages(
        self, session_id: str, limit: int = 10
    ) -> list[Message]:
        """Return the last `limit` messages for a session, oldest-first."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT * FROM (
                    SELECT id, session_id, role, content, created_at
                    FROM messages
                    WHERE session_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                ) ORDER BY id ASC
                """,
                (session_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
        return [Message(**dict(r)) for r in rows]

    async def get_all_messages(self, session_id: str) -> list[Message]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            ) as cursor:
                rows = await cursor.fetchall()
        return [Message(**dict(r)) for r in rows]

    async def delete_session_messages(self, session_id: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            await db.commit()

    # ── Memory Facts ──────────────────────────────────────────────────────────

    async def upsert_fact(self, key: str, value: str, source: str = "manual") -> None:
        """Insert or update a memory fact by key."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO memory_facts (key, value, source, updated_at)
                VALUES (?, ?, ?, datetime('now'))
                ON CONFLICT(key) DO UPDATE SET
                    value      = excluded.value,
                    source     = excluded.source,
                    updated_at = datetime('now')
                """,
                (key, value, source),
            )
            await db.commit()

    async def get_fact(self, key: str) -> Optional[MemoryFact]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM memory_facts WHERE key = ?", (key,)
            ) as cursor:
                row = await cursor.fetchone()
        return MemoryFact(**dict(row)) if row else None

    async def get_all_facts(self) -> list[MemoryFact]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM memory_facts ORDER BY updated_at DESC"
            ) as cursor:
                rows = await cursor.fetchall()
        return [MemoryFact(**dict(r)) for r in rows]

    async def delete_fact(self, key: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM memory_facts WHERE key = ?", (key,)
            )
            await db.commit()
            return cursor.rowcount > 0

    # ── Sessions ──────────────────────────────────────────────────────────────

    async def _ensure_session(self, session_id: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO sessions (id) VALUES (?)", (session_id,)
            )
            await db.commit()

    async def list_sessions(self) -> list[Session]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT s.id, s.title, s.created_at,
                       COUNT(m.id) AS message_count
                FROM sessions s
                LEFT JOIN messages m ON m.session_id = s.id
                GROUP BY s.id
                ORDER BY s.created_at DESC
                """
            ) as cursor:
                rows = await cursor.fetchall()
        return [Session(**dict(r)) for r in rows]

    async def update_session_title(self, session_id: str, title: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE sessions SET title = ? WHERE id = ?", (title, session_id)
            )
            await db.commit()
