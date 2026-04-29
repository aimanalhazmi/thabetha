"""Time-resolver unit tests (FR-013)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.ai.merchant_chat.time_resolver import detect_phrase, resolve, safe_zone


def test_safe_zone_falls_back_on_invalid() -> None:
    assert safe_zone("Not/A_Zone").key == "Asia/Riyadh"
    assert safe_zone(None).key == "Asia/Riyadh"


def test_last_month_in_april_resolves_to_march() -> None:
    tz = ZoneInfo("Asia/Riyadh")
    now = datetime(2026, 4, 30, 14, 0, tzinfo=tz)
    rng = resolve(now, tz, "last month")
    assert rng is not None
    assert rng.start.isoformat() == "2026-03-01T00:00:00+03:00"
    assert rng.end.isoformat() == "2026-04-01T00:00:00+03:00"
    assert rng.human == "March 2026"


def test_today_and_yesterday() -> None:
    tz = ZoneInfo("Asia/Riyadh")
    now = datetime(2026, 4, 30, 14, 0, tzinfo=tz)
    today_rng = resolve(now, tz, "today")
    assert today_rng is not None
    assert today_rng.start.date().isoformat() == "2026-04-30"
    yest_rng = resolve(now, tz, "yesterday")
    assert yest_rng is not None
    assert yest_rng.start.date().isoformat() == "2026-04-29"


def test_unknown_phrase_returns_none() -> None:
    tz = ZoneInfo("Asia/Riyadh")
    now = datetime(2026, 4, 30, tzinfo=tz)
    assert resolve(now, tz, "next century") is None


def test_arabic_phrase_resolution() -> None:
    tz = ZoneInfo("Asia/Riyadh")
    now = datetime(2026, 4, 30, tzinfo=tz)
    rng = resolve(now, tz, "الشهر الماضي")
    assert rng is not None
    assert rng.start.isoformat().startswith("2026-03-01")


def test_detect_phrase_finds_english_and_arabic() -> None:
    assert detect_phrase("Did Ahmed pay me last month?") == "last month"
    assert detect_phrase("ماذا حدث الشهر الماضي؟") == "الشهر الماضي"
    assert detect_phrase("How are you?") is None
