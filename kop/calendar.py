"""Earnings calendar. Seeded confirmed NVDA AMC dates plus a live Yahoo peek."""

from __future__ import annotations

from datetime import date, datetime, timezone

from kop.models import EarningsEvent
from kop.net import get_json

# Confirmed after-close prints used for the first research tape.
# Sources: company calendar / public earnings pages. Session is AMC.
NVDA_SEEDED: tuple[EarningsEvent, ...] = (
    EarningsEvent("NVDA", date(2025, 2, 26), "amc", "FY25 Q4", "seed:public_calendar", True),
    EarningsEvent("NVDA", date(2025, 5, 28), "amc", "FY26 Q1", "seed:public_calendar", True),
    EarningsEvent("NVDA", date(2025, 8, 27), "amc", "FY26 Q2", "seed:public_calendar", True),
    EarningsEvent("NVDA", date(2025, 11, 19), "amc", "FY26 Q3", "seed:public_calendar", True),
    EarningsEvent("NVDA", date(2026, 2, 25), "amc", "FY26 Q4", "seed:public_calendar", True),
    EarningsEvent("NVDA", date(2026, 5, 20), "amc", "FY27 Q1", "seed:public_calendar", True),
    EarningsEvent("NVDA", date(2026, 8, 26), "amc", "FY27 Q2", "seed:public_calendar", True),
)

YAHOO_SUMMARY = "https://query2.finance.yahoo.com/v10/finance/quoteSummary/{symbol}?modules=calendarEvents"


def seeded_events(symbol: str) -> list[EarningsEvent]:
    return [event for event in NVDA_SEEDED if event.symbol == symbol.upper()]


def completed_for_tape(symbol: str, asof: date) -> list[EarningsEvent]:
    """Last 6 completed events (announce date strictly before asof)."""
    prior = [event for event in seeded_events(symbol) if event.announce_date < asof]
    return prior[-6:]


def last_event(symbol: str, asof: date) -> EarningsEvent | None:
    prior = [event for event in seeded_events(symbol) if event.announce_date <= asof]
    return prior[-1] if prior else None


def next_event(symbol: str, asof: date, *, allow_yahoo: bool = True) -> EarningsEvent | None:
    upcoming = [event for event in seeded_events(symbol) if event.announce_date >= asof]
    if upcoming:
        return upcoming[0]
    if not allow_yahoo:
        return None
    yahoo = fetch_yahoo_next_earnings(symbol)
    if yahoo is None or yahoo < asof:
        return None
    return EarningsEvent(symbol.upper(), yahoo, "unknown", "yahoo_next", "yahoo_calendarEvents", False)


def event_from_key(key: str) -> EarningsEvent | None:
    parts = (key or "").split(":")
    if len(parts) < 3:
        return None
    try:
        announce = date.fromisoformat(parts[1])
    except ValueError:
        return None
    session = parts[2] if parts[2] in {"amc", "bmo", "unknown"} else "unknown"
    return EarningsEvent(parts[0], announce, session, "", "event_key", True)


def fetch_yahoo_next_earnings(symbol: str) -> date | None:
    try:
        payload = get_json(YAHOO_SUMMARY.format(symbol=symbol.upper()))
    except RuntimeError:
        return None
    results = payload.get("quoteSummary", {}).get("result") or []
    if not results:
        return None
    earnings = ((results[0].get("calendarEvents") or {}).get("earnings") or {})
    raw = earnings.get("earningsDate") or []
    if not raw:
        return None
    first = raw[0]
    stamp = first.get("raw") if isinstance(first, dict) else None
    if not stamp:
        return None
    return datetime.fromtimestamp(int(stamp), timezone.utc).date()
