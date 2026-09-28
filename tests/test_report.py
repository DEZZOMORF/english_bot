from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from bot.report import (
    Member,
    build_reminder,
    build_stats,
    local_day,
    mention,
    missed_streak,
    plural_days,
    split_message,
)

YESTERDAY = date(2026, 9, 25)


def member(user_id=1, name="Anna", first_seen=date(2026, 9, 1), last_update=None, username=None):
    return Member(user_id, name, username, first_seen, last_update)


def test_wrote_yesterday_has_no_streak():
    assert missed_streak(member(last_update=YESTERDAY), YESTERDAY) == 0


def test_streak_counts_days_since_last_update():
    assert missed_streak(member(last_update=date(2026, 9, 22)), YESTERDAY) == 3


def test_first_seen_day_is_not_counted_as_missed():
    assert missed_streak(member(first_seen=YESTERDAY), YESTERDAY) == 0
    assert missed_streak(member(first_seen=date(2026, 9, 24)), YESTERDAY) == 1


def test_newcomer_first_seen_today_is_not_blamed():
    assert missed_streak(member(first_seen=date(2026, 9, 26)), YESTERDAY) == 0


def test_rejoin_resets_reference_to_first_seen():
    rejoined = member(first_seen=date(2026, 9, 23), last_update=date(2026, 9, 1))
    assert missed_streak(rejoined, YESTERDAY) == 2


def test_plural_days():
    assert [plural_days(n) for n in (1, 2, 11, 21)] == ["1 day", "2 days", "11 days", "21 days"]


TODAY = date(2026, 9, 26)


def test_mention_prefers_username():
    assert mention(member(username="anna_k")) == "@anna_k"
    assert mention(member(user_id=7, name="Cid <x>")) == '<a href="tg://user?id=7">Cid &lt;x&gt;</a>'


def test_reminder_lists_only_members_over_threshold():
    members = [
        member(1, "Bob", username="bob", last_update=date(2026, 9, 22)),
        member(2, "Anna", username="anna", last_update=date(2026, 9, 23)),
        member(3, "Cid <x>", last_update=date(2026, 9, 20)),
        member(4, "Dan", username="dan", last_update=YESTERDAY),
    ]
    text = build_reminder(members, TODAY, min_days=3)
    assert "daily update" in text
    assert "No update for 3+ days:" in text
    cid = text.index(mention(members[2]) + " — 5 days")
    bob = text.index("@bob — 3 days")
    assert cid < bob
    assert "@anna" not in text
    assert "@dan" not in text
    assert "today" not in text


def test_reminder_without_anyone_over_threshold_is_plain():
    text = build_reminder([member(last_update=date(2026, 9, 23))], TODAY, min_days=3)
    assert text == "⏰ Time to write your <b>daily update</b>!\nTell the chat how your day went."


def test_threshold_is_configurable():
    text = build_reminder([member(username="a", last_update=date(2026, 9, 23))], TODAY, min_days=2)
    assert "No update for 2+ days:\n• @a — 2 days" in text


def test_newcomer_is_not_listed():
    assert "@new" not in build_reminder([member(username="new", first_seen=TODAY)], TODAY, min_days=1)


def test_stats_shows_only_members_over_threshold():
    text = build_stats(
        [
            member(1, "Anna", username="anna", last_update=YESTERDAY),
            member(2, "Bob", username="bob", last_update=date(2026, 9, 21)),
        ],
        TODAY,
        min_days=3,
    )
    assert text.startswith("📊 <b>Daily update status</b>")
    assert "@anna" not in text
    assert "• @bob — 4 days" in text


def test_stats_nobody_over_threshold():
    text = build_stats([member(last_update=YESTERDAY)], TODAY, min_days=3)
    assert text == "📊 Nobody has gone 3+ days without an update 🎉"


def test_stats_empty():
    assert "/join" in build_stats([], TODAY, min_days=3)


def test_split_message_respects_limit_on_line_boundaries():
    text = "\n".join(f"line {i}" for i in range(100))
    chunks = split_message(text, limit=50)
    assert all(len(c) <= 50 for c in chunks)
    assert "\n".join(chunks) == text


def test_local_day_uses_kyiv_midnight():
    kyiv = ZoneInfo("Europe/Kyiv")
    assert local_day(datetime(2026, 9, 25, 20, 59, tzinfo=UTC), kyiv) == date(2026, 9, 25)
    assert local_day(datetime(2026, 9, 25, 21, 1, tzinfo=UTC), kyiv) == date(2026, 9, 26)
