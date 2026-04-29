from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True)
class ResolvedRange:
    start: datetime
    end: datetime
    phrase: str
    human: str


_AR_PHRASES = {
    "اليوم": "today",
    "أمس": "yesterday",
    "الأمس": "yesterday",
    "هذا الأسبوع": "this week",
    "الأسبوع الماضي": "last week",
    "هذا الشهر": "this month",
    "الشهر الماضي": "last month",
    "هذا العام": "this year",
    "السنة الماضية": "last year",
    "آخر 7 أيام": "last 7 days",
    "آخر 30 يوم": "last 30 days",
}


def safe_zone(tz_name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name) if tz_name else ZoneInfo("Asia/Riyadh")
    except ZoneInfoNotFoundError:
        return ZoneInfo("Asia/Riyadh")


def _start_of_day(d: date, tz: ZoneInfo) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=tz)


def _start_of_week(d: date, tz: ZoneInfo) -> datetime:
    # Sunday-anchored week (regional convention).
    days_back = (d.weekday() + 1) % 7  # Mon=0, Sun=6 → Sun=0
    sunday = d - timedelta(days=days_back)
    return _start_of_day(sunday, tz)


def _first_of_month(d: date, tz: ZoneInfo) -> datetime:
    return datetime(d.year, d.month, 1, tzinfo=tz)


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def _prev_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


_MONTH_NAMES_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def resolve(now: datetime, tz: ZoneInfo, phrase: str) -> ResolvedRange | None:
    """Resolve relative time phrases in the caller's local timezone (Gregorian)."""
    if phrase is None:
        return None
    raw = phrase.strip().lower()
    canonical = _AR_PHRASES.get(phrase.strip(), raw)
    today = now.astimezone(tz).date()

    if canonical == "today":
        start = _start_of_day(today, tz)
        end = start + timedelta(days=1)
        return ResolvedRange(start, end, phrase, today.isoformat())
    if canonical == "yesterday":
        y = today - timedelta(days=1)
        start = _start_of_day(y, tz)
        return ResolvedRange(start, start + timedelta(days=1), phrase, y.isoformat())
    if canonical == "this week":
        start = _start_of_week(today, tz)
        return ResolvedRange(start, start + timedelta(days=7), phrase, "this week")
    if canonical == "last week":
        this_week = _start_of_week(today, tz)
        start = this_week - timedelta(days=7)
        return ResolvedRange(start, this_week, phrase, "last week")
    if canonical == "this month":
        start = _first_of_month(today, tz)
        ny, nm = _next_month(today.year, today.month)
        end = datetime(ny, nm, 1, tzinfo=tz)
        return ResolvedRange(start, end, phrase, f"{_MONTH_NAMES_EN[today.month - 1]} {today.year}")
    if canonical == "last month":
        py, pm = _prev_month(today.year, today.month)
        start = datetime(py, pm, 1, tzinfo=tz)
        end = _first_of_month(today, tz)
        return ResolvedRange(start, end, phrase, f"{_MONTH_NAMES_EN[pm - 1]} {py}")
    if canonical == "this year":
        start = datetime(today.year, 1, 1, tzinfo=tz)
        end = datetime(today.year + 1, 1, 1, tzinfo=tz)
        return ResolvedRange(start, end, phrase, str(today.year))
    if canonical == "last year":
        start = datetime(today.year - 1, 1, 1, tzinfo=tz)
        end = datetime(today.year, 1, 1, tzinfo=tz)
        return ResolvedRange(start, end, phrase, str(today.year - 1))
    if canonical == "last 7 days":
        end = _start_of_day(today + timedelta(days=1), tz)
        start = end - timedelta(days=7)
        return ResolvedRange(start, end, phrase, "last 7 days")
    if canonical == "last 30 days":
        end = _start_of_day(today + timedelta(days=1), tz)
        start = end - timedelta(days=30)
        return ResolvedRange(start, end, phrase, "last 30 days")
    return None


_DETECT_PHRASES = [
    "today",
    "yesterday",
    "this week",
    "last week",
    "this month",
    "last month",
    "this year",
    "last year",
    "last 7 days",
    "last 30 days",
]


def detect_phrase(text: str) -> str | None:
    """Return the first relative time phrase found in text (en or ar), or None."""
    lowered = text.lower()
    for p in _DETECT_PHRASES:
        if p in lowered:
            return p
    for ar in _AR_PHRASES:
        if ar in text:
            return ar
    return None
