from datetime import date

import pytest

from bot.storage import Storage

DAY = date(2026, 9, 25)
TODAY = date(2026, 9, 27)


@pytest.fixture
def store(tmp_path):
    s = Storage(str(tmp_path / "test.db"))
    yield s
    s.close()


def test_updates_are_deduplicated_per_day(store):
    store.upsert_member(1, 10, "Anna", "anna", DAY)
    store.record_update(1, 10, DAY)
    store.record_update(1, 10, DAY)
    count = store.conn.execute("SELECT COUNT(*) FROM updates").fetchone()[0]
    assert count == 1


def test_active_members_carry_last_update(store):
    store.upsert_member(1, 10, "Anna", "anna", date(2026, 9, 1))
    store.record_update(1, 10, date(2026, 9, 20))
    store.record_update(1, 10, date(2026, 9, 24))
    [m] = store.active_members(1, TODAY)
    assert m.first_seen == date(2026, 9, 1)
    assert m.last_update == date(2026, 9, 24)


def test_members_are_scoped_per_chat(store):
    store.upsert_member(1, 10, "Anna", None, DAY)
    store.upsert_member(2, 11, "Bob", None, DAY)
    store.record_update(2, 10, DAY)
    assert [m.name for m in store.active_members(1, TODAY)] == ["Anna"]
    assert store.active_members(1, TODAY)[0].last_update is None


def test_upsert_keeps_first_seen_and_refreshes_name(store):
    store.upsert_member(1, 10, "Anna", None, date(2026, 9, 1))
    store.upsert_member(1, 10, "Anna K", "annak", date(2026, 9, 20))
    [m] = store.active_members(1, TODAY)
    assert (m.name, m.username, m.first_seen) == ("Anna K", "annak", date(2026, 9, 1))


def test_deactivated_member_is_hidden_and_rejoin_resets_first_seen(store):
    store.upsert_member(1, 10, "Anna", None, date(2026, 9, 1))
    store.deactivate_member(1, 10)
    assert store.active_members(1, TODAY) == []
    store.upsert_member(1, 10, "Anna", None, date(2026, 9, 20))
    [m] = store.active_members(1, TODAY)
    assert m.first_seen == date(2026, 9, 20)


def test_chat_activation(store):
    store.upsert_chat(1, "Group")
    store.upsert_chat(2, "Other")
    store.deactivate_chat(2)
    assert store.active_chats() == [1]
    store.upsert_chat(2, "Other")
    assert store.active_chats() == [1, 2]


def test_migrate_chat_moves_everything(store):
    store.upsert_chat(1, "Group")
    store.upsert_member(1, 10, "Anna", None, DAY)
    store.record_update(1, 10, DAY)
    store.migrate_chat(1, -100)
    assert store.active_chats() == [-100]
    [m] = store.active_members(-100, TODAY)
    assert m.last_update == DAY
    assert store.active_members(1, TODAY) == []


def test_active_members_split_today_from_earlier_updates(store):
    store.upsert_member(1, 10, "Anna", None, date(2026, 9, 1))
    store.record_update(1, 10, date(2026, 9, 24))
    store.record_update(1, 10, date(2026, 9, 26))
    [m] = store.active_members(1, date(2026, 9, 26))
    assert (m.last_update, m.posted_today) == (date(2026, 9, 24), True)
    [m] = store.active_members(1, date(2026, 9, 25))
    assert (m.last_update, m.posted_today) == (date(2026, 9, 24), False)


def test_migrate_chat_keeps_existing_destination_rows(store):
    store.upsert_member(1, 10, "Old Anna", None, date(2026, 9, 1))
    store.deactivate_member(1, 10)
    store.upsert_member(-100, 10, "Anna", None, date(2026, 9, 20))
    store.upsert_member(1, 11, "Bob", None, date(2026, 9, 1))
    store.migrate_chat(1, -100)
    members = {m.user_id: m for m in store.active_members(-100, TODAY)}
    assert members[10].name == "Anna"
    assert members[10].first_seen == date(2026, 9, 20)
    assert members[11].name == "Bob"
    count = store.conn.execute("SELECT COUNT(*) FROM members WHERE chat_id = 1").fetchone()[0]
    assert count == 0
