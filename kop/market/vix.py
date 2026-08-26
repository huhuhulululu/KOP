"""Index vol. CBOE delayed spot + FRED daily history.

VIX is background. A quiet index + a rich single-name earnings premium
is a valid short-vol setup. Do not require a high VIX to sell NVDA event vol.
"""

from __future__ import annotations

import csv
import io
from datetime import date
from typing import Optional

from kop.net import get_json, get_text

CBOE_INDEX = "https://cdn.cboe.com/api/global/delayed_quotes/quotes/{symbol}.json"
FRED_VIX = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS"


def fetch_index_spot(symbol: str = "_VIX") -> Optional[float]:
    try:
        raw = get_json(CBOE_INDEX.format(symbol=symbol.upper()))
    except Exception:
        return None
    data = raw.get("data") or {}
    for key in ("current_price", "close", "prev_day_close"):
        try:
            value = float(data.get(key) or 0)
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return None


def fetch_vix_spot() -> Optional[float]:
    return fetch_index_spot("_VIX")


def fetch_vix_history() -> list[tuple[date, float]]:
    try:
        text = get_text(FRED_VIX)
    except Exception:
        return []
    out: list[tuple[date, float]] = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        raw_d = (row.get("observation_date") or row.get("DATE") or "").strip()
        raw_v = (row.get("VIXCLS") or "").strip()
        if not raw_d or raw_v in {"", "."}:
            continue
        try:
            out.append((date.fromisoformat(raw_d), float(raw_v)))
        except ValueError:
            continue
    return out


def vix_percentile(spot: float, history: list[tuple[date, float]], lookback: int = 252) -> Optional[float]:
    if spot <= 0 or not history:
        return None
    vals = [value for _, value in history[-lookback:] if value > 0]
    if len(vals) < 60:
        return None
    below = sum(1 for value in vals if value <= spot)
    return 100.0 * below / len(vals)
