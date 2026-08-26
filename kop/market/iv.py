from __future__ import annotations

from kop.config import IV_PERCENTILE_MIN_SAMPLES
from kop.models import OptionQuote, UnderlyingQuote


def iv30_range_rank(under: UnderlyingQuote) -> float | None:
    if under.iv30 is None or under.iv30_annual_high is None or under.iv30_annual_low is None:
        return None
    span = under.iv30_annual_high - under.iv30_annual_low
    if span <= 0:
        return None
    rank = 100.0 * (under.iv30 - under.iv30_annual_low) / span
    return max(0.0, min(100.0, rank))


def iv_percentile(history: list[float], current: float) -> float | None:
    if len(history) < IV_PERCENTILE_MIN_SAMPLES:
        return None
    below = sum(1 for value in history if value < current)
    return 100.0 * below / len(history)


def atm_quotes(quotes: list[OptionQuote], expiration, spot: float) -> tuple[OptionQuote, OptionQuote] | None:
    chain = [q for q in quotes if q.occ.expiration == expiration]
    if not chain:
        return None
    strike = min({q.occ.strike for q in chain}, key=lambda k: abs(k - spot))
    call = next((q for q in chain if q.occ.right == "C" and q.occ.strike == strike), None)
    put = next((q for q in chain if q.occ.right == "P" and q.occ.strike == strike), None)
    if call is None or put is None:
        return None
    return call, put


def straddle_implied_move_pct(call: OptionQuote, put: OptionQuote, spot: float, *, side: str) -> float | None:
    """Implied move from the tradeable side. Never mid.

    side='sell' uses bids (what a short straddle would take).
    side='buy' uses asks (what a long straddle would pay).
    """
    if spot <= 0:
        return None
    if side == "sell":
        premium = call.bid + put.bid
    elif side == "buy":
        premium = call.ask + put.ask
    else:
        raise ValueError(side)
    if premium <= 0:
        return None
    return 100.0 * premium / spot
