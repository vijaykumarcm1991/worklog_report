"""Time handling: the whole app runs on IST (Asia/Kolkata, UTC+05:30).

Both Jira instances are in IST, so worklog timestamps are stored exactly as
Jira reports them (IST wall-clock time) with no timezone conversion. IST has
no daylight saving, so a fixed offset is exact and needs no tzdata.
"""
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30), name="IST")


def now_ist() -> datetime:
    """Current IST wall-clock time as a naive datetime (how the DB stores it)."""
    return datetime.now(IST).replace(tzinfo=None)


def today_ist_start() -> datetime:
    """Midnight today, IST, as a naive datetime."""
    return now_ist().replace(hour=0, minute=0, second=0, microsecond=0)
