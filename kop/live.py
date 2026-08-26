"""One live pull. Chain + bars + VIX + tape + snapshot. No second CBOE fetch."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from kop.calendar import next_event
from kop.config import SYMBOL
from kop.indicators import Snapshot, build_snapshot
from kop.ledger import Store
from kop.market.cboe import attach_iv_range, fetch_chain, fetch_iv_range
from kop.market.iv import iv_percentile
from kop.market.paid import configured_sources
from kop.market.vix import fetch_index_spot, fetch_vix_history, fetch_vix_spot, vix_percentile
from kop.market.yahoo import fetch_bars
from kop.models import Bar, EarningsEvent, OptionQuote, UnderlyingQuote
from kop.playbook import trading_days_before
from kop.research import replay


@dataclass(frozen=True)
class LiveBundle:
    asof: date
    event: EarningsEvent | None
    bars: list[Bar]
    under: UnderlyingQuote
    quotes: list[OptionQuote]
    snapshot: Snapshot


def collect_live(store: Store | None = None, *, symbol: str = SYMBOL, asof: date | None = None) -> LiveBundle:
    store = store or Store()
    calendar_day = asof or datetime.now(timezone.utc).date()
    bars = fetch_bars(symbol)
    under, quotes = fetch_chain(symbol)
    high, low = fetch_iv_range(symbol)
    under = attach_iv_range(under, high, low)
    market_day = _asof(under, calendar_day)
    event = next_event(symbol, market_day)
    days_before = _days_before(event, market_day, bars)
    tape = replay(symbol, asof=market_day, bars=bars)
    iv_hist = store.iv30_history(symbol)
    pct = iv_percentile(iv_hist, under.iv30) if under.iv30 is not None else None
    vix = fetch_vix_spot()
    vix_hist = fetch_vix_history()
    vix_pct = vix_percentile(vix, vix_hist) if vix is not None else None
    snap = build_snapshot(
        asof=market_day,
        under=under,
        quotes=quotes,
        bars=bars,
        event=event,
        tape_rows=tape,
        days_before=days_before,
        iv_percentile=pct,
        vix=vix,
        vix_1y_percentile=vix_pct,
        vix9d=fetch_index_spot("_VIX9D"),
        vix3m=fetch_index_spot("_VIX3M"),
        paid_configured=configured_sources(),
    )
    return LiveBundle(asof=market_day, event=event, bars=bars, under=under, quotes=quotes, snapshot=snap)


def _asof(under: UnderlyingQuote, fallback: date) -> date:
    raw = (under.asof or "")[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return fallback


def _days_before(event: EarningsEvent | None, asof: date, bars: list[Bar]) -> int | None:
    if event is None:
        return None
    days = trading_days_before(event, asof, bars)
    if days is not None:
        return days
    if asof == event.announce_date:
        return 0
    if bars:
        last = bars[-1].day
        if asof > last:
            return trading_days_before(event, last, bars)
    return None
