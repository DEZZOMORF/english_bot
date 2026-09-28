from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from bot.report import (
    Member,
    build_reminder,
    build_stats,
    describe,
    local_day,
    mention,
    silence,
    split_message,
)

NOW = datetime(2026, 9, 28, 17, 0, tzinfo=UTC)
LONG_AGO = datetime(2026, 9, 1, tzinfo=UTC)


def ago(hours):
    return NOW - timedelta(hours=hours)


def member(user_id=1, name="Anna", seen_at=LONG_AGO, last_update_at=None, username=None):
    return Member(user_id, name, username, seen_at, last_update_at)


def test_silence_counts_from_last_update():
    assert silence(member(last_update_at=ago(30)), NOW) == timedelta(hours=30)


def test_silence_counts_from_join_when_no_updates():
    assert silence(member(seen_at=ago(10)), NOW) == timedelta(hours=10)


def test_rejoin_resets_reference_to_seen_at():
    assert silence(member(seen_at=ago(5), last_update_at=ago(500)), NOW) == timedelta(hours=5)


def test_describe_rounds_down_to_days():
    assert describe(timedelta(hours=48)) == "2 days"
    assert describe(timedelta(hours=71)) == "2 days"
    assert describe(timedelta(hours=72)) == "3 days"
    assert describe(timedelta(hours=24)) == "1 day"


def test_mention_prefers_username():
    assert mention(member(username="anna_k")) == "@anna_k"
    assert mention(member(user_id=7, name="Cid <x>")) == '<a href="tg://user?id=7">Cid &lt;x&gt;</a>'


def test_reminder_lists_only_members_silent_for_48_hours():
    members = [
        member(1, "Bob", username="bob", last_update_at=ago(48)),
        member(2, "Anna", username="anna", last_update_at=ago(47)),
        member(3, "Cid <x>", last_update_at=ago(120)),
        member(4, "Dan", username="dan", seen_at=ago(47.9)),
        member(5, "Eve", username="eve", seen_at=ago(49)),
    ]
    text = build_reminder(members, NOW, hours=48)
    assert "No update for 48+ hours:" in text
    cid = text.index(mention(members[2]) + " — 5 days")
    bob = text.index("@bob — 2 days")
    eve = text.index("@eve — 2 days")
    assert cid < eve < bob
    assert "@anna" not in text
    assert "@dan" not in text


def test_reminder_without_anyone_over_threshold_is_plain():
    text = build_reminder([member(last_update_at=ago(20))], NOW, hours=48)
    assert text == "⏰ Time to write your <b>daily update</b>!\nTell the chat how your day went."


def test_threshold_is_configurable():
    text = build_reminder([member(username="a", last_update_at=ago(25))], NOW, hours=24)
    assert "No update for 24+ hours:\n• @a — 1 day" in text


def test_stats_shows_only_members_over_threshold():
    text = build_stats(
        [
            member(1, "Anna", username="anna", last_update_at=ago(2)),
            member(2, "Bob", username="bob", last_update_at=ago(100)),
        ],
        NOW,
        hours=48,
    )
    assert text.startswith("📊 <b>Daily update status</b>")
    assert "@anna" not in text
    assert "• @bob — 4 days" in text


def test_stats_nobody_over_threshold():
    text = build_stats([member(last_update_at=ago(1))], NOW, hours=48)
    assert text == "📊 Nobody has gone 48+ hours without an update 🎉"


def test_stats_empty():
    assert "join or send a message" in build_stats([], NOW, hours=48)


def test_split_message_respects_limit_on_line_boundaries():
    text = "\n".join(f"line {i}" for i in range(100))
    chunks = split_message(text, limit=50)
    assert all(len(c) <= 50 for c in chunks)
    assert "\n".join(chunks) == text


def test_local_day_uses_kyiv_midnight():
    kyiv = ZoneInfo("Europe/Kyiv")
    assert local_day(datetime(2026, 9, 25, 20, 59, tzinfo=UTC), kyiv) == date(2026, 9, 25)
    assert local_day(datetime(2026, 9, 25, 21, 1, tzinfo=UTC), kyiv) == date(2026, 9, 26)
