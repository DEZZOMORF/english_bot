import sqlite3
from datetime import UTC, date, datetime

import pytest

from bot.storage import Storage

T1 = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
T2 = datetime(2026, 9, 20, 18, 30, tzinfo=UTC)
T3 = datetime(2026, 9, 24, 7, 15, tzinfo=UTC)


@pytest.fixture
def store(tmp_path):
    s = Storage(str(tmp_path / "test.db"))
    yield s
    s.close()


def test_updates_are_deduplicated_per_day(store):
    store.upsert_member(1, 10, "Anna", "anna", T1)
    store.record_update(1, 10, date(2026, 9, 1), T1)
    store.record_update(1, 10, date(2026, 9, 1), T1)
    assert store.conn.execute("SELECT COUNT(*) FROM updates").fetchone()[0] == 1


def test_last_update_at_keeps_latest_time(store):
    store.upsert_member(1, 10, "Anna", "anna", T1)
    store.record_update(1, 10, date(2026, 9, 24), T3)
    store.record_update(1, 10, date(2026, 9, 20), T2)
    [m] = store.active_members(1)
    assert m.seen_at == T1
    assert m.last_update_at == T3


def test_members_are_scoped_per_chat(store):
    store.upsert_member(1, 10, "Anna", None, T1)
    store.upsert_member(2, 11, "Bob", None, T1)
    store.record_update(2, 10, date(2026, 9, 1), T1)
    [m] = store.active_members(1)
    assert m.name == "Anna"
    assert m.last_update_at is None


def test_upsert_keeps_seen_at_and_refreshes_name(store):
    store.upsert_member(1, 10, "Anna", None, T1)
    store.upsert_member(1, 10, "Anna K", "annak", T2)
    [m] = store.active_members(1)
    assert (m.name, m.username, m.seen_at) == ("Anna K", "annak", T1)


def test_deactivated_member_is_hidden_and_rejoin_resets_seen_at(store):
    store.upsert_member(1, 10, "Anna", None, T1)
    store.deactivate_member(1, 10)
    assert store.active_members(1) == []
    store.upsert_member(1, 10, "Anna", None, T2)
    [m] = store.active_members(1)
    assert m.seen_at == T2


def test_chat_activation(store):
    store.upsert_chat(1, "Group")
    store.upsert_chat(2, "Other")
    store.deactivate_chat(2)
    assert store.active_chats() == [1]
    store.upsert_chat(2, "Other")
    assert store.active_chats() == [1, 2]


def test_migrate_chat_moves_everything(store):
    store.upsert_chat(1, "Group")
    store.upsert_member(1, 10, "Anna", None, T1)
    store.record_update(1, 10, date(2026, 9, 1), T1)
    store.migrate_chat(1, -100)
    assert store.active_chats() == [-100]
    [m] = store.active_members(-100)
    assert m.last_update_at == T1
    assert store.active_members(1) == []


def test_migrate_chat_keeps_existing_destination_rows(store):
    store.upsert_member(1, 10, "Old Anna", None, T1)
    store.deactivate_member(1, 10)
    store.upsert_member(-100, 10, "Anna", None, T2)
    store.upsert_member(1, 11, "Bob", None, T1)
    store.migrate_chat(1, -100)
    members = {m.user_id: m for m in store.active_members(-100)}
    assert members[10].name == "Anna"
    assert members[10].seen_at == T2
    assert members[11].name == "Bob"
    assert store.conn.execute("SELECT COUNT(*) FROM members WHERE chat_id = 1").fetchone()[0] == 0


def test_old_database_is_migrated_with_backfill(tmp_path):
    path = str(tmp_path / "old.db")
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE members (chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL, "
        "name TEXT NOT NULL, username TEXT, first_seen TEXT NOT NULL, "
        "active INTEGER NOT NULL DEFAULT 1, PRIMARY KEY (chat_id, user_id));"
        "CREATE TABLE updates (chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL, "
        "day TEXT NOT NULL, PRIMARY KEY (chat_id, user_id, day));"
        "INSERT INTO members VALUES (1, 10, 'Anna', 'anna', '2026-09-27', 1);"
        "INSERT INTO members VALUES (1, 11, 'Bob', NULL, '2026-09-27', 1);"
        "INSERT INTO updates VALUES (1, 10, '2026-09-27'), (1, 10, '2026-09-28');"
    )
    conn.close()
    s = Storage(path)
    members = {m.user_id: m for m in s.active_members(1)}
    assert members[10].seen_at == datetime(2026, 9, 27, tzinfo=UTC)
    assert members[10].last_update_at == datetime(2026, 9, 28, 23, 59, 59, tzinfo=UTC)
    assert members[11].last_update_at is None
    s.close()
    Storage(path).close()
