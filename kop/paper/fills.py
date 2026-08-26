"""Bid/ask fills. Mid is never a fill price."""

from __future__ import annotations

from kop.config import FEE_PER_CONTRACT, MULTIPLIER, SLIPPAGE_PER_LEG_USD
from kop.models import LegFill, OptionQuote, Side


class MidPriceForbidden(ValueError):
    pass


def fill_sell(quote: OptionQuote, quantity: int = 1, slippage: float = SLIPPAGE_PER_LEG_USD) -> LegFill:
    if not quote.has_market():
        raise ValueError(f"no market to sell {quote.occ.symbol}")
    price = _tick(quote.bid - slippage)
    if price <= 0:
        raise ValueError(f"sell fill non-positive after slippage for {quote.occ.symbol}")
    return _leg(quote, "sell", quantity, price, slippage)


def fill_buy(quote: OptionQuote, quantity: int = 1, slippage: float = SLIPPAGE_PER_LEG_USD) -> LegFill:
    if not quote.has_market():
        raise ValueError(f"no market to buy {quote.occ.symbol}")
    price = _tick(quote.ask + slippage)
    return _leg(quote, "buy", quantity, price, slippage)


def _leg(quote: OptionQuote, side: Side, quantity: int, price: float, slippage: float) -> LegFill:
    if abs(price - (quote.bid + quote.ask) / 2.0) < 1e-12:
        raise MidPriceForbidden("fill equals mid; refuse")
    fee = FEE_PER_CONTRACT * quantity
    return LegFill(
        occ=quote.occ,
        side=side,
        quantity=quantity,
        bid=quote.bid,
        ask=quote.ask,
        fill_price=price,
        slippage=slippage,
        fee_usd=fee,
        quote_kind="bid_ask",
    )


def cash_effect(fill: LegFill, multiplier: int = MULTIPLIER) -> float:
    notional = fill.fill_price * fill.quantity * multiplier
    if fill.side == "sell":
        return notional - fill.fee_usd
    return -(notional + fill.fee_usd)


def structure_fees(fills: list[LegFill]) -> float:
    return sum(fill.fee_usd for fill in fills)


def _tick(price: float) -> float:
    return round(price + 0.0, 2)
