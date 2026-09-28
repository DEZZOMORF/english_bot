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


def member(user_id=1, name="Anna", first_seen=date(2026, 9, 1), last_update=None, posted_today=False, username=None):
    return Member(user_id, name, username, first_seen, last_update, posted_today)


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


def test_reminder_lists_only_missing_members():
    members = [
        member(1, "Bob", username="bob", last_update=date(2026, 9, 24), posted_today=True),
        member(2, "Anna", username="anna", last_update=YESTERDAY, posted_today=True),
        member(3, "Cid <x>", last_update=date(2026, 9, 20)),
        member(4, "Dan", username="dan", last_update=YESTERDAY),
    ]
    text = build_reminder(members, TODAY)
    assert "daily update" in text
    today_block, yesterday_block = text.split("Skipped yesterday (Sep 25):")
    assert "• " + mention(members[2]) in today_block
    assert "• @dan" in today_block
    assert "@bob" not in today_block
    assert "@anna" not in text
    cid = yesterday_block.index(mention(members[2]) + " — 5 days in a row")
    bob = yesterday_block.index("@bob — 1 day in a row")
    assert cid < bob
    assert "@dan" not in yesterday_block


def test_reminder_when_everyone_is_on_track():
    text = build_reminder([member(last_update=YESTERDAY, posted_today=True)], TODAY)
    assert "Everyone has posted today and yesterday 🎉" in text
    assert "Not posted" not in text


def test_reminder_without_members_is_plain():
    text = build_reminder([], TODAY)
    assert "Not posted" not in text
    assert "Everyone" not in text


def test_newcomer_seen_today_is_asked_for_today_only():
    text = build_reminder([member(username="new", first_seen=TODAY)], TODAY)
    assert "Not posted today (Sep 26) yet:\n• @new" in text
    assert "Skipped yesterday" not in text


def test_stats_shows_only_missing_members():
    text = build_stats(
        [
            member(1, "Anna", username="anna", last_update=YESTERDAY, posted_today=True),
            member(2, "Bob", username="bob", last_update=date(2026, 9, 23)),
        ],
        TODAY,
    )
    assert text.startswith("📊 <b>Daily update status</b>")
    assert "@anna" not in text
    assert "• @bob — 2 days in a row" in text


def test_stats_everyone_on_track():
    text = build_stats([member(last_update=YESTERDAY, posted_today=True)], TODAY)
    assert text == "📊 Everyone has posted today and yesterday 🎉"


def test_stats_empty():
    assert "/join" in build_stats([], TODAY)


def test_split_message_respects_limit_on_line_boundaries():
    text = "\n".join(f"line {i}" for i in range(100))
    chunks = split_message(text, limit=50)
    assert all(len(c) <= 50 for c in chunks)
    assert "\n".join(chunks) == text


def test_local_day_uses_kyiv_midnight():
    kyiv = ZoneInfo("Europe/Kyiv")
    assert local_day(datetime(2026, 9, 25, 20, 59, tzinfo=UTC), kyiv) == date(2026, 9, 25)
    assert local_day(datetime(2026, 9, 25, 21, 1, tzinfo=UTC), kyiv) == date(2026, 9, 26)
