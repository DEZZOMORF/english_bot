from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from bot.report import Member, local_day, build_reminder, build_stats, missed_streak, plural_days, split_message

YESTERDAY = date(2026, 9, 25)


def member(user_id=1, name="Anna", first_seen=date(2026, 9, 1), last_update=None):
    return Member(user_id, name, None, first_seen, last_update)


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


def test_reminder_lists_missed_sorted_by_streak_with_mentions():
    members = [
        member(1, "Bob", last_update=date(2026, 9, 24)),
        member(2, "Anna", last_update=YESTERDAY),
        member(3, "Cid <x>", last_update=date(2026, 9, 20)),
    ]
    text = build_reminder(members, YESTERDAY)
    assert "daily update" in text
    assert "No update yesterday (Sep 25):" in text
    cid = text.index('<a href="tg://user?id=3">Cid &lt;x&gt;</a> — 5 days in a row')
    bob = text.index('<a href="tg://user?id=1">Bob</a> — 1 day in a row')
    assert cid < bob
    assert "Anna" not in text


def test_reminder_when_everyone_wrote():
    text = build_reminder([member(last_update=YESTERDAY)], YESTERDAY)
    assert "Everyone posted an update yesterday (Sep 25)" in text


def test_reminder_without_members_is_plain():
    text = build_reminder([], YESTERDAY)
    assert "yesterday" not in text


def test_stats():
    today = date(2026, 9, 26)
    text = build_stats(
        [
            member(1, "Anna", last_update=today),
            member(2, "Bob", last_update=date(2026, 9, 23)),
            member(3, "Cid", first_seen=today),
        ],
        today,
    )
    assert "• Anna — today ✅" in text
    assert "• Bob — last update Sep 23, 2 days without an update" in text
    assert "• Cid — no updates yet" in text


def test_stats_empty():
    assert "/join" in build_stats([], date(2026, 9, 26))


def test_split_message_respects_limit_on_line_boundaries():
    text = "\n".join(f"line {i}" for i in range(100))
    chunks = split_message(text, limit=50)
    assert all(len(c) <= 50 for c in chunks)
    assert "\n".join(chunks) == text


def test_local_day_uses_kyiv_midnight():
    kyiv = ZoneInfo("Europe/Kyiv")
    assert local_day(datetime(2026, 9, 25, 20, 59, tzinfo=UTC), kyiv) == date(2026, 9, 25)
    assert local_day(datetime(2026, 9, 25, 21, 1, tzinfo=UTC), kyiv) == date(2026, 9, 26)


def test_update_written_today_does_not_hide_yesterdays_miss():
    today_writer = member(last_update=date(2026, 9, 24))
    assert "1 day in a row" in build_reminder([today_writer], YESTERDAY)
