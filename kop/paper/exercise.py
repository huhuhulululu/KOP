"""American early-exercise flag. Uses bid as the short mark, never mid."""

from __future__ import annotations

from kop.models import OptionQuote, UnderlyingQuote


def intrinsic(right: str, strike: float, spot: float) -> float:
    if right == "C":
        return max(0.0, spot - strike)
    return max(0.0, strike - spot)


def time_value_at_bid(quote: OptionQuote, spot: float) -> float:
    return quote.bid - intrinsic(quote.occ.right, quote.occ.strike, spot)


def early_exercise_risk(short: OptionQuote, spot: float, *, threshold: float = 0.05) -> bool:
    """True when the short option's bid is at or inside intrinsic + threshold."""
    if not short.has_market():
        return False
    value = time_value_at_bid(short, spot)
    in_the_money = intrinsic(short.occ.right, short.occ.strike, spot) > 0
    return in_the_money and value <= threshold


def assignment_notes(shorts: list[OptionQuote], under: UnderlyingQuote) -> list[str]:
    notes: list[str] = []
    for quote in shorts:
        if early_exercise_risk(quote, under.spot):
            notes.append(
                f"early_exercise_risk {quote.occ.symbol} bid={quote.bid:.2f} "
                f"intrinsic={intrinsic(quote.occ.right, quote.occ.strike, under.spot):.2f}"
            )
    return notes
