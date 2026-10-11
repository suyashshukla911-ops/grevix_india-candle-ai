from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)

# NSE equities holidays for 2026 published by NSE. Kept local so the app can
# distinguish "market closed" from "data stale" without a holiday API dependency.
NSE_HOLIDAYS_2026 = {
    date(2026, 1, 15), date(2026, 1, 26), date(2026, 3, 3), date(2026, 3, 26),
    date(2026, 3, 31), date(2026, 4, 3), date(2026, 4, 14), date(2026, 5, 1),
    date(2026, 5, 28), date(2026, 6, 26), date(2026, 9, 14), date(2026, 10, 2),
    date(2026, 10, 20), date(2026, 11, 8), date(2026, 11, 10), date(2026, 11, 24),
    date(2026, 12, 25),
}

def is_trading_day(d: date) -> bool:
    if d.weekday() >= 5:
        return False
    if d.year == 2026 and d in NSE_HOLIDAYS_2026:
        return False
    return True

def session_state(now: datetime | None = None) -> str:
    now = now.astimezone(IST) if now else datetime.now(IST)
    if not is_trading_day(now.date()):
        return "MARKET_CLOSED"
    if now.time() < MARKET_OPEN:
        return "PRE_OPEN"
    if now.time() > MARKET_CLOSE:
        return "POST_CLOSE"
    return "OPEN"

def freshness_state(latest: datetime, interval_minutes: int, now: datetime | None = None) -> tuple[str, bool]:
    now = now.astimezone(IST) if now else datetime.now(IST)
    latest = latest.astimezone(IST)
    state = session_state(now)
    age = max(0.0, (now - latest).total_seconds())
    # During an open session, require a small multiple of the bar size.
    if state == "OPEN":
        limit = max(3 * interval_minutes * 60, 15 * 60)
        return ("LIVE" if age <= limit else "STALE", age <= limit)
    # Before/after a session or on a holiday/weekend, the last completed session can
    # still be valid paper-analysis input, provided it is reasonably recent.
    if state in {"PRE_OPEN", "POST_CLOSE", "MARKET_CLOSED"}:
        if age <= 4 * 24 * 3600:
            return ("MARKET_CLOSED", True)
    return ("STALE", False)
