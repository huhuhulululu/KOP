from __future__ import annotations

from datetime import date, datetime, timezone

from kop.models import Bar
from kop.net import get_json

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range={rng}&events=div%2Csplit"


def fetch_bars(symbol: str, rng: str = "2y") -> list[Bar]:
    payload = get_json(CHART_URL.format(symbol=symbol, rng=rng))
    results = payload.get("chart", {}).get("result") or []
    if not results:
        error = payload.get("chart", {}).get("error")
        raise RuntimeError(f"yahoo chart empty for {symbol}: {error}")
    result = results[0]
    stamps = result.get("timestamp") or []
    quote = (result.get("indicators") or {}).get("quote") or [{}]
    block = quote[0]
    opens = block.get("open") or []
    highs = block.get("high") or []
    lows = block.get("low") or []
    closes = block.get("close") or []
    volumes = block.get("volume") or []
    bars: list[Bar] = []
    for i, ts in enumerate(stamps):
        close = closes[i] if i < len(closes) else None
        open_ = opens[i] if i < len(opens) else None
        high = highs[i] if i < len(highs) else None
        low = lows[i] if i < len(lows) else None
        if None in (close, open_, high, low):
            continue
        day = datetime.fromtimestamp(int(ts), timezone.utc).date()
        volume = float(volumes[i]) if i < len(volumes) and volumes[i] is not None else None
        bars.append(Bar(day=day, open=float(open_), high=float(high), low=float(low), close=float(close), volume=volume))
    return bars


def trading_days(bars: list[Bar]) -> list[date]:
    return [bar.day for bar in bars]


def bar_map(bars: list[Bar]) -> dict[date, Bar]:
    return {bar.day: bar for bar in bars}


def offset_trading_day(days: list[date], day: date, offset: int) -> date:
    index = days.index(day)
    target = index + offset
    if target < 0 or target >= len(days):
        raise IndexError(f"{day} offset {offset} is outside the bar range")
    return days[target]
