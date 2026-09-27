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


def local_day(moment: datetime, tz: tzinfo) -> date:
    return moment.astimezone(tz).date()


def missed_streak(member: Member, yesterday: date) -> int:
    reference = max(member.first_seen, member.last_update or member.first_seen)
    return max(0, (yesterday - reference).days)


def plural_days(count: int) -> str:
    return f"{count} day" if count == 1 else f"{count} days"


def mention(member: Member) -> str:
    return f'<a href="tg://user?id={member.user_id}">{html.escape(member.name)}</a>'


def build_reminder(members: list[Member], yesterday: date) -> str:
    lines = [
        "⏰ Time to write your <b>daily update</b>!",
        "Tell the chat how your day went.",
    ]
    missed = sorted(
        ((missed_streak(m, yesterday), m) for m in members),
        key=lambda pair: (-pair[0], pair[1].name.lower()),
    )
    missed = [(streak, m) for streak, m in missed if streak > 0]
    if missed:
        lines.append("")
        lines.append(f"No update yesterday ({yesterday:%b %d}):")
        for streak, m in missed:
            lines.append(f"• {mention(m)} — {plural_days(streak)} in a row")
    elif members:
        lines.append("")
        lines.append(f"Everyone posted an update yesterday ({yesterday:%b %d}) 🎉")
    return "\n".join(lines)


def build_stats(members: list[Member], today: date) -> str:
    if not members:
        return "I don't know anyone in this chat yet. Send a message or /join."
    yesterday = today - timedelta(days=1)
    lines = ["📊 <b>Daily update stats</b>"]
    for m in sorted(members, key=lambda m: m.name.lower()):
        name = html.escape(m.name)
        if m.last_update == today:
            lines.append(f"• {name} — today ✅")
            continue
        streak = missed_streak(m, yesterday)
        last = f"last update {m.last_update:%b %d}" if m.last_update else "no updates yet"
        tail = f", {plural_days(streak)} without an update" if streak else ""
        lines.append(f"• {name} — {last}{tail}")
    return "\n".join(lines)


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
