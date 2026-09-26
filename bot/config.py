from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import time
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Config:
    token: str
    db_path: str
    timezone: ZoneInfo
    reminder_time: time


def parse_time(value: str, tz: ZoneInfo) -> time:
    hours, minutes = value.strip().split(":")
    return time(int(hours), int(minutes), tzinfo=tz)


def load_config() -> Config:
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("BOT_TOKEN is not set")
    tz = ZoneInfo(os.environ.get("BOT_TIMEZONE", "Europe/Kyiv"))
    return Config(
        token=token,
        db_path=os.environ.get("DB_PATH", "data.db"),
        timezone=tz,
        reminder_time=parse_time(os.environ.get("REMINDER_TIME", "20:00"), tz),
    )
