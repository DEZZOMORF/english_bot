from __future__ import annotations

import sqlite3
from datetime import date, datetime

from bot.report import Member

SCHEMA = """
CREATE TABLE IF NOT EXISTS chats (
    chat_id INTEGER PRIMARY KEY,
    title TEXT,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS members (
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    username TEXT,
    first_seen TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    seen_at TEXT,
    last_update_at TEXT,
    PRIMARY KEY (chat_id, user_id)
);
CREATE TABLE IF NOT EXISTS updates (
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    day TEXT NOT NULL,
    PRIMARY KEY (chat_id, user_id, day)
);
"""


class Storage:
    def __init__(self, path: str) -> None:
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)
        columns = {row[1] for row in self.conn.execute("PRAGMA table_info(members)")}
        if "seen_at" not in columns:
            self.conn.execute("ALTER TABLE members ADD COLUMN seen_at TEXT")
            self.conn.execute("ALTER TABLE members ADD COLUMN last_update_at TEXT")
            self.conn.execute(
                "UPDATE members SET seen_at = first_seen || 'T00:00:00+00:00', "
                "last_update_at = (SELECT MAX(u.day) || 'T23:59:59+00:00' FROM updates u "
                "WHERE u.chat_id = members.chat_id AND u.user_id = members.user_id)"
            )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def upsert_chat(self, chat_id: int, title: str | None) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO chats (chat_id, title, active) VALUES (?, ?, 1) "
                "ON CONFLICT(chat_id) DO UPDATE SET title = excluded.title, active = 1",
                (chat_id, title),
            )

    def deactivate_chat(self, chat_id: int) -> None:
        with self.conn:
            self.conn.execute("UPDATE chats SET active = 0 WHERE chat_id = ?", (chat_id,))

    def active_chats(self) -> list[int]:
        rows = self.conn.execute("SELECT chat_id FROM chats WHERE active = 1 ORDER BY chat_id")
        return [row[0] for row in rows]

    def migrate_chat(self, old_id: int, new_id: int) -> None:
        with self.conn:
            for table in ("chats", "members", "updates"):
                self.conn.execute(
                    f"UPDATE OR IGNORE {table} SET chat_id = ? WHERE chat_id = ?",
                    (new_id, old_id),
                )
                self.conn.execute(f"DELETE FROM {table} WHERE chat_id = ?", (old_id,))

    def upsert_member(
        self, chat_id: int, user_id: int, name: str, username: str | None, now: datetime
    ) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO members "
                "(chat_id, user_id, name, username, first_seen, active, seen_at) "
                "VALUES (?, ?, ?, ?, ?, 1, ?) "
                "ON CONFLICT(chat_id, user_id) DO UPDATE SET "
                "name = excluded.name, username = excluded.username, "
                "first_seen = CASE WHEN members.active = 0 THEN excluded.first_seen "
                "ELSE members.first_seen END, "
                "seen_at = CASE WHEN members.active = 0 OR members.seen_at IS NULL "
                "THEN excluded.seen_at ELSE members.seen_at END, "
                "active = 1",
                (chat_id, user_id, name, username, now.date().isoformat(), now.isoformat()),
            )

    def deactivate_member(self, chat_id: int, user_id: int) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE members SET active = 0 WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id),
            )

    def record_update(self, chat_id: int, user_id: int, day: date, at: datetime) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO updates (chat_id, user_id, day) VALUES (?, ?, ?)",
                (chat_id, user_id, day.isoformat()),
            )
            self.conn.execute(
                "UPDATE members SET last_update_at = ? WHERE chat_id = ? AND user_id = ? "
                "AND (last_update_at IS NULL OR last_update_at < ?)",
                (at.isoformat(), chat_id, user_id, at.isoformat()),
            )

    def active_members(self, chat_id: int) -> list[Member]:
        rows = self.conn.execute(
            "SELECT user_id, name, username, seen_at, last_update_at FROM members "
            "WHERE chat_id = ? AND active = 1",
            (chat_id,),
        )
        return [
            Member(
                user_id=user_id,
                name=name,
                username=username,
                seen_at=datetime.fromisoformat(seen_at),
                last_update_at=datetime.fromisoformat(last) if last else None,
            )
            for user_id, name, username, seen_at, last in rows
        ]
