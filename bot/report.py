from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import date, datetime, timedelta, tzinfo

MESSAGE_LIMIT = 4096


@dataclass(frozen=True)
class Member:
    user_id: int
    name: str
    username: str | None
    first_seen: date
    last_update: date | None
    posted_today: bool = False


def local_day(moment: datetime, tz: tzinfo) -> date:
    return moment.astimezone(tz).date()


def missed_streak(member: Member, yesterday: date) -> int:
    reference = max(member.first_seen, member.last_update or member.first_seen)
    return max(0, (yesterday - reference).days)


def plural_days(count: int) -> str:
    return f"{count} day" if count == 1 else f"{count} days"


def mention(member: Member) -> str:
    if member.username:
        return f"@{member.username}"
    return f'<a href="tg://user?id={member.user_id}">{html.escape(member.name)}</a>'


def sort_key(member: Member) -> str:
    return (member.username or member.name).lower()


def missing_lines(members: list[Member], today: date) -> list[str]:
    yesterday = today - timedelta(days=1)
    not_today = sorted(
        (m for m in members if not m.posted_today), key=sort_key
    )
    skipped = sorted(
        ((missed_streak(m, yesterday), m) for m in members),
        key=lambda pair: (-pair[0], sort_key(pair[1])),
    )
    skipped = [(streak, m) for streak, m in skipped if streak > 0]
    lines: list[str] = []
    if not_today:
        lines.append("")
        lines.append(f"Not posted today ({today:%b %d}) yet:")
        lines.extend(f"• {mention(m)}" for m in not_today)
    if skipped:
        lines.append("")
        lines.append(f"Skipped yesterday ({yesterday:%b %d}):")
        lines.extend(f"• {mention(m)} — {plural_days(streak)} in a row" for streak, m in skipped)
    return lines


def build_reminder(members: list[Member], today: date) -> str:
    lines = [
        "⏰ Time to write your <b>daily update</b>!",
        "Tell the chat how your day went.",
    ]
    missing = missing_lines(members, today)
    if missing:
        lines.extend(missing)
    elif members:
        lines.append("")
        lines.append("Everyone has posted today and yesterday 🎉")
    return "\n".join(lines)


def build_stats(members: list[Member], today: date) -> str:
    if not members:
        return "I don't know anyone in this chat yet. Send a message or /join."
    missing = missing_lines(members, today)
    if not missing:
        return "📊 Everyone has posted today and yesterday 🎉"
    return "\n".join(["📊 <b>Daily update status</b>", *missing])


def split_message(text: str, limit: int = MESSAGE_LIMIT) -> list[str]:
    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = line[:limit]
    if current:
        chunks.append(current)
    return chunks
