from __future__ import annotations

from kop.market.occ import parse_occ
from kop.models import OptionQuote, UnderlyingQuote
from kop.net import get_json

CHAIN_URL = "https://cdn.cboe.com/api/global/delayed_quotes/options/{symbol}.json"
RANGE_URL = "https://cdn.cboe.com/api/global/delayed_quotes/historical_data/{symbol}.json"


def fetch_chain(symbol: str) -> tuple[UnderlyingQuote, list[OptionQuote]]:
    payload = get_json(CHAIN_URL.format(symbol=symbol.upper()))
    block = payload.get("data") or {}
    under = UnderlyingQuote(
        symbol=str(block.get("symbol") or symbol).upper(),
        last=float(block.get("current_price") or 0.0),
        bid=_opt_float(block.get("bid")),
        ask=_opt_float(block.get("ask")),
        close=float(block.get("close") or block.get("prev_day_close") or 0.0),
        asof=str(block.get("last_trade_time") or payload.get("timestamp") or ""),
        iv30=_opt_float(block.get("iv30")),
    )
    quotes: list[OptionQuote] = []
    for raw in block.get("options") or []:
        try:
            occ = parse_occ(str(raw["option"]))
        except (KeyError, ValueError):
            continue
        quotes.append(
            OptionQuote(
                occ=occ,
                bid=float(raw.get("bid") or 0.0),
                ask=float(raw.get("ask") or 0.0),
                iv=_iv_to_percent(raw.get("iv")),
                delta=_opt_float(raw.get("delta")),
                gamma=_opt_float(raw.get("gamma")),
                theta=_opt_float(raw.get("theta")),
                vega=_opt_float(raw.get("vega")),
                volume=_opt_float(raw.get("volume")),
                open_interest=_opt_float(raw.get("open_interest")),
                bid_size=_opt_float(raw.get("bid_size")),
                ask_size=_opt_float(raw.get("ask_size")),
            )
        )
    return under, quotes


def fetch_iv_range(symbol: str) -> tuple[float | None, float | None]:
    payload = get_json(RANGE_URL.format(symbol=symbol.upper()))
    block = payload.get("data") or {}
    return _opt_float(block.get("iv30_annual_high")), _opt_float(block.get("iv30_annual_low"))


def attach_iv_range(under: UnderlyingQuote, high: float | None, low: float | None) -> UnderlyingQuote:
    return UnderlyingQuote(
        symbol=under.symbol,
        last=under.last,
        bid=under.bid,
        ask=under.ask,
        close=under.close,
        asof=under.asof,
        iv30=under.iv30,
        iv30_annual_high=high,
        iv30_annual_low=low,
    )


def _opt_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _iv_to_percent(value: object) -> float | None:
    parsed = _opt_float(value)
    if parsed is None:
        return None
    # CBOE option iv is a decimal (1.00 = 100%). iv30 on the underlying is already percent.
    if parsed <= 4.0:
        return parsed * 100.0
    return parsed
