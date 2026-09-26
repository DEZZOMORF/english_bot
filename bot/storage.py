from __future__ import annotations

import sqlite3
from datetime import date

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
                    f"UPDATE OR REPLACE {table} SET chat_id = ? WHERE chat_id = ?",
                    (new_id, old_id),
                )

    def upsert_member(
        self, chat_id: int, user_id: int, name: str, username: str | None, today: date
    ) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO members (chat_id, user_id, name, username, first_seen, active) "
                "VALUES (?, ?, ?, ?, ?, 1) "
                "ON CONFLICT(chat_id, user_id) DO UPDATE SET "
                "name = excluded.name, username = excluded.username, "
                "first_seen = CASE WHEN members.active = 0 THEN excluded.first_seen "
                "ELSE members.first_seen END, "
                "active = 1",
                (chat_id, user_id, name, username, today.isoformat()),
            )

    def deactivate_member(self, chat_id: int, user_id: int) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE members SET active = 0 WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id),
            )

    def record_update(self, chat_id: int, user_id: int, day: date) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO updates (chat_id, user_id, day) VALUES (?, ?, ?)",
                (chat_id, user_id, day.isoformat()),
            )

    def active_members(self, chat_id: int) -> list[Member]:
        rows = self.conn.execute(
            "SELECT m.user_id, m.name, m.username, m.first_seen, MAX(u.day) "
            "FROM members m "
            "LEFT JOIN updates u ON u.chat_id = m.chat_id AND u.user_id = m.user_id "
            "WHERE m.chat_id = ? AND m.active = 1 "
            "GROUP BY m.user_id, m.name, m.username, m.first_seen",
            (chat_id,),
        )
        return [
            Member(
                user_id=user_id,
                name=name,
                username=username,
                first_seen=date.fromisoformat(first_seen),
                last_update=date.fromisoformat(last) if last else None,
            )
            for user_id, name, username, first_seen, last in rows
        ]
