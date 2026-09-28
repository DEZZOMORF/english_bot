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
    seen_at: datetime
    last_update_at: datetime | None


def local_day(moment: datetime, tz: tzinfo) -> date:
    return moment.astimezone(tz).date()


def silence(member: Member, now: datetime) -> timedelta:
    reference = max(member.seen_at, member.last_update_at or member.seen_at)
    return max(timedelta(0), now - reference)


def describe(gap: timedelta) -> str:
    days = gap.days
    return f"{days} day" if days == 1 else f"{days} days"


def mention(member: Member) -> str:
    if member.username:
        return f"@{member.username}"
    return f'<a href="tg://user?id={member.user_id}">{html.escape(member.name)}</a>'


def sort_key(member: Member) -> str:
    return (member.username or member.name).lower()


def missing_lines(members: list[Member], now: datetime, hours: int) -> list[str]:
    threshold = timedelta(hours=hours)
    silent = sorted(
        ((silence(m, now), m) for m in members),
        key=lambda pair: (-pair[0], sort_key(pair[1])),
    )
    silent = [(gap, m) for gap, m in silent if gap >= threshold]
    if not silent:
        return []
    return [
        "",
        f"No update for {hours}+ hours:",
        *(f"• {mention(m)} — {describe(gap)}" for gap, m in silent),
    ]


def build_reminder(members: list[Member], now: datetime, hours: int) -> str:
    return "\n".join(
        [
            "⏰ Time to write your <b>daily update</b>!",
            "Tell the chat how your day went.",
            *missing_lines(members, now, hours),
        ]
    )


def build_stats(members: list[Member], now: datetime, hours: int) -> str:
    if not members:
        return "I don't know anyone in this chat yet. Members appear here once they join or send a message."
    missing = missing_lines(members, now, hours)
    if not missing:
        return f"📊 Nobody has gone {hours}+ hours without an update 🎉"
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
