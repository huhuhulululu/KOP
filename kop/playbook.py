"""Frozen playbook: nvda_earnings_defined_short_vol.

Gates are fail-closed. No long premium before the event. No naked shorts.
"""

from __future__ import annotations

from datetime import date

from kop.config import (
    AUTO_TRADE,
    DEFAULT_ENTRY_DAYS_BEFORE,
    ENTRY_DAYS_BEFORE,
    EXIT_TRADING_DAYS_AFTER,
    IV_RANK_MIN,
    IV_PERCENTILE_MIN_SAMPLES,
    MAX_LOSS_USD,
    MIN_TAPE_SAMPLES_FOR_LOOP,
    PLAYBOOK,
    SYMBOL,
    STRUCTURE,
)
from kop.market.iv import iv30_range_rank, iv_percentile
from kop.market.yahoo import offset_trading_day, trading_days
from kop.models import Bar, Decision, EarningsEvent, UnderlyingQuote


def entry_date_for(event: EarningsEvent, bars: list[Bar], days_before: int = DEFAULT_ENTRY_DAYS_BEFORE) -> date:
    days = trading_days(bars)
    return offset_trading_day(days, event.announce_date, -days_before)


def exit_date_for(event: EarningsEvent, bars: list[Bar]) -> date:
    days = trading_days(bars)
    reaction = event.reaction_index(days)
    # first trading day after the reaction session, or the reaction day itself
    # Playbook: leave 1 trading day after the report, or 50% credit, first hit.
    target = reaction + (EXIT_TRADING_DAYS_AFTER - 1)
    if target >= len(days):
        return days[-1]
    return days[target]


def trading_days_before(event: EarningsEvent, asof: date, bars: list[Bar]) -> int | None:
    days = trading_days(bars)
    if event.announce_date not in days or asof not in days:
        return None
    return days.index(event.announce_date) - days.index(asof)


def iv_gate(under: UnderlyingQuote, history: list[float]) -> tuple[bool, str, dict]:
    percentile = iv_percentile(history, under.iv30) if under.iv30 is not None else None
    range_rank = iv30_range_rank(under)
    details = {
        "iv30": under.iv30,
        "iv_percentile": percentile,
        "iv30_range_rank": range_rank,
        "threshold": IV_RANK_MIN,
        "history_n": len(history),
    }
    if percentile is not None:
        if percentile >= IV_RANK_MIN:
            return True, f"iv_percentile {percentile:.1f} >= {IV_RANK_MIN}", details
        return False, f"iv_percentile {percentile:.1f} < {IV_RANK_MIN}", details
    if range_rank is None:
        return False, "iv_rank_missing", details
    if len(history) < IV_PERCENTILE_MIN_SAMPLES:
        details["rank_kind"] = "iv30_range_rank_fallback"
        if range_rank >= IV_RANK_MIN:
            return True, f"iv30_range_rank {range_rank:.1f} >= {IV_RANK_MIN}", details
        return False, f"iv30_range_rank {range_rank:.1f} < {IV_RANK_MIN}", details
    return False, "iv_rank_missing", details


def decide(
    *,
    symbol: str,
    asof: date,
    event: EarningsEvent | None,
    bars: list[Bar],
    under: UnderlyingQuote | None,
    iv_history: list[float],
    countable_tape: int,
    want_structure: str = STRUCTURE,
    auto: bool = AUTO_TRADE,
) -> Decision:
    details: dict = {
        "playbook": PLAYBOOK,
        "asof": asof.isoformat(),
        "countable_tape": countable_tape,
        "auto": auto,
    }
    if symbol != SYMBOL:
        return Decision(False, f"symbol_{symbol}_not_in_playbook", PLAYBOOK, details)
    if want_structure in {"long_call", "long_put", "long_straddle"}:
        return Decision(False, "forbidden_long_premium_before_event", PLAYBOOK, details)
    if want_structure in {"short_straddle", "short_strangle", "naked_put", "naked_call"}:
        return Decision(False, "forbidden_naked_short", PLAYBOOK, details)
    if want_structure != STRUCTURE:
        return Decision(False, f"structure_{want_structure}_not_playbook", PLAYBOOK, details)
    if event is None:
        return Decision(False, "no_earnings_event", PLAYBOOK, details)
    if event.symbol != SYMBOL:
        return Decision(False, "event_symbol_mismatch", PLAYBOOK, details)
    details["event"] = event.key
    days_before = trading_days_before(event, asof, bars)
    details["days_before"] = days_before
    if days_before is None:
        return Decision(False, "asof_or_event_not_in_session_calendar", PLAYBOOK, details)
    low, high = ENTRY_DAYS_BEFORE
    if days_before < low or days_before > high:
        return Decision(False, f"outside_entry_window_{days_before}d", PLAYBOOK, details)
    if under is None:
        return Decision(False, "no_underlying_quote", PLAYBOOK, details)
    ok, reason, iv_details = iv_gate(under, iv_history)
    details.update(iv_details)
    if not ok:
        return Decision(False, reason, PLAYBOOK, details)
    if countable_tape < MIN_TAPE_SAMPLES_FOR_LOOP:
        return Decision(
            False,
            f"no_human_tape_{countable_tape}_of_{MIN_TAPE_SAMPLES_FOR_LOOP}",
            PLAYBOOK,
            details,
        )
    if not auto:
        return Decision(False, "auto_trade_disabled", PLAYBOOK, details)
    details["max_loss_usd"] = MAX_LOSS_USD
    return Decision(True, "gates_open", PLAYBOOK, details)
