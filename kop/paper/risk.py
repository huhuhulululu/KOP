from __future__ import annotations

from datetime import date

from kop.config import (
    CONTRACTS,
    MAX_LEG_SPREAD_USD,
    MAX_LOSS_USD,
    MULTIPLIER,
    WING_WIDTH_USD,
)
from kop.market.iv import atm_quotes, straddle_implied_move_pct
from kop.models import OptionQuote, StructureFill
from kop.paper.fills import cash_effect, fill_buy, fill_sell, structure_fees


class UndefinedRisk(ValueError):
    pass


def defined_risk(width_usd: float, net_credit: float, fees_usd: float, contracts: int = CONTRACTS) -> tuple[float, float]:
    """Return (max_loss_usd, max_gain_usd) for a short iron condor / credit wing.

    Max loss is the wing width minus credit, plus fees. Naked shorts are rejected
    by the caller — this function will not invent unlimited risk.
    """
    if width_usd <= 0:
        raise UndefinedRisk("width must be positive")
    width_cash = width_usd * MULTIPLIER * contracts
    credit_cash = net_credit * MULTIPLIER * contracts
    max_gain = credit_cash - fees_usd
    max_loss = width_cash - credit_cash + fees_usd
    if max_loss <= 0:
        raise UndefinedRisk("computed max loss is not positive; check credit vs width")
    return max_loss, max_gain


def pick_expiration(quotes: list[OptionQuote], after: date) -> date | None:
    expiries = sorted({q.occ.expiration for q in quotes if q.occ.expiration >= after})
    return expiries[0] if expiries else None


def _quote_at(quotes: list[OptionQuote], expiration: date, right: str, strike: float) -> OptionQuote | None:
    return next(
        (q for q in quotes if q.occ.expiration == expiration and q.occ.right == right and q.occ.strike == strike),
        None,
    )


def listed_strikes(quotes: list[OptionQuote], expiration: date, right: str) -> list[float]:
    return sorted({q.occ.strike for q in quotes if q.occ.expiration == expiration and q.occ.right == right})


def nearest_strike(strikes: list[float], target: float) -> float | None:
    if not strikes:
        return None
    return min(strikes, key=lambda strike: (abs(strike - target), strike))


def select_iron_condor(
    quotes: list[OptionQuote],
    spot: float,
    expiration: date,
    *,
    width: float = WING_WIDTH_USD,
    contracts: int = CONTRACTS,
) -> StructureFill:
    pair = atm_quotes(quotes, expiration, spot)
    if pair is None:
        raise ValueError("no ATM pair on expiry")
    call, put = pair
    move = straddle_implied_move_pct(call, put, spot, side="sell")
    if move is None:
        raise ValueError("ATM straddle has no sellable bids")
    short_put_k = nearest_strike(listed_strikes(quotes, expiration, "P"), spot * (1.0 - move / 100.0))
    short_call_k = nearest_strike(listed_strikes(quotes, expiration, "C"), spot * (1.0 + move / 100.0))
    if short_put_k is None or short_call_k is None:
        raise ValueError("missing short strikes")
    long_put_k = nearest_strike([k for k in listed_strikes(quotes, expiration, "P") if k <= short_put_k - width + 1e-9], short_put_k - width)
    long_call_k = nearest_strike([k for k in listed_strikes(quotes, expiration, "C") if k >= short_call_k + width - 1e-9], short_call_k + width)
    if long_put_k is None or long_call_k is None:
        raise ValueError("missing wing strikes")
    legs = {
        "short_put": _quote_at(quotes, expiration, "P", short_put_k),
        "long_put": _quote_at(quotes, expiration, "P", long_put_k),
        "short_call": _quote_at(quotes, expiration, "C", short_call_k),
        "long_call": _quote_at(quotes, expiration, "C", long_call_k),
    }
    if any(leg is None for leg in legs.values()):
        raise ValueError("incomplete iron condor quotes")
    for name, quote in legs.items():
        assert quote is not None
        if quote.spread > MAX_LEG_SPREAD_USD:
            raise ValueError(f"{name} spread {quote.spread:.2f} > {MAX_LEG_SPREAD_USD}")
    fills = [
        fill_sell(legs["short_put"], contracts),
        fill_buy(legs["long_put"], contracts),
        fill_sell(legs["short_call"], contracts),
        fill_buy(legs["long_call"], contracts),
    ]
    net_cash = sum(cash_effect(fill) for fill in fills)
    fees = structure_fees(fills)
    # net_premium is per-share credit (positive) before fees
    short_prem = fills[0].fill_price + fills[2].fill_price
    long_prem = fills[1].fill_price + fills[3].fill_price
    net_premium = short_prem - long_prem
    if net_premium <= 0:
        raise ValueError("iron condor is a debit after bid/ask+slip; refuse")
    call_width = long_call_k - short_call_k
    put_width = short_put_k - long_put_k
    wing = max(call_width, put_width)
    max_loss, max_gain = defined_risk(wing, net_premium, fees, contracts)
    if max_loss > MAX_LOSS_USD + 1e-9:
        raise UndefinedRisk(f"max loss {max_loss:.2f} exceeds cap {MAX_LOSS_USD}")
    return StructureFill(
        name="short_iron_condor",
        expiration=expiration,
        credit=True,
        net_premium=net_premium,
        max_loss_usd=max_loss,
        max_gain_usd=max_gain,
        fees_usd=fees,
        slippage_usd=sum(fill.slippage * fill.quantity * MULTIPLIER for fill in fills),
        legs=tuple(fills),
        quote_kind="bid_ask",
    )


def long_straddle_fill(quotes: list[OptionQuote], spot: float, expiration: date, contracts: int = CONTRACTS) -> StructureFill:
    pair = atm_quotes(quotes, expiration, spot)
    if pair is None:
        raise ValueError("no ATM pair")
    call, put = pair
    fills = [fill_buy(call, contracts), fill_buy(put, contracts)]
    debit = fills[0].fill_price + fills[1].fill_price
    fees = structure_fees(fills)
    max_loss = debit * MULTIPLIER * contracts + fees
    return StructureFill(
        name="long_straddle",
        expiration=expiration,
        credit=False,
        net_premium=debit,
        max_loss_usd=max_loss,
        max_gain_usd=float("inf"),
        fees_usd=fees,
        slippage_usd=sum(f.slippage for f in fills),
        legs=tuple(fills),
    )


def long_call_fill(quotes: list[OptionQuote], spot: float, expiration: date, contracts: int = CONTRACTS) -> StructureFill:
    pair = atm_quotes(quotes, expiration, spot)
    if pair is None:
        raise ValueError("no ATM pair")
    call, _put = pair
    fills = [fill_buy(call, contracts)]
    debit = fills[0].fill_price
    fees = structure_fees(fills)
    return StructureFill(
        name="long_call",
        expiration=expiration,
        credit=False,
        net_premium=debit,
        max_loss_usd=debit * MULTIPLIER * contracts + fees,
        max_gain_usd=float("inf"),
        fees_usd=fees,
        slippage_usd=fills[0].slippage,
        legs=tuple(fills),
    )
