"""Optional paid history. Only talks to a vendor when a key is actually set.

Live gates use CBOE + Yahoo + FRED. These clients exist so a key can fill
historical bid/ask on the tape. No key → no pretend quotes.
"""

from __future__ import annotations

import os
from datetime import date
from typing import Any
from urllib.parse import urlencode

from kop.net import get_json


def configured_sources() -> tuple[str, ...]:
    found: list[str] = []
    if os.environ.get("POLYGON_API_KEY"):
        found.append("polygon")
    if os.environ.get("TRADIER_TOKEN"):
        found.append("tradier")
    if os.environ.get("ORATS_API_KEY"):
        found.append("orats")
    return tuple(found)


def polygon_option_daily(occ_symbol: str, day: date) -> dict[str, Any] | None:
    """EOD open/close for one OCC contract. Needs POLYGON_API_KEY.

    Endpoint: GET /v1/open-close/O:{OCC}/{date}
    Returns bid/ask only if the vendor stored them; otherwise None.
    """
    key = os.environ.get("POLYGON_API_KEY")
    if not key:
        return None
    ticker = occ_symbol if occ_symbol.startswith("O:") else f"O:{occ_symbol}"
    url = f"https://api.polygon.io/v1/open-close/{ticker}/{day.isoformat()}?{urlencode({'apiKey': key, 'adjusted': 'true'})}"
    raw = get_json(url)
    if not isinstance(raw, dict):
        return None
    bid = raw.get("bid") or raw.get("low")
    ask = raw.get("ask") or raw.get("high")
    try:
        bid_f = float(bid) if bid is not None else None
        ask_f = float(ask) if ask is not None else None
    except (TypeError, ValueError):
        return None
    if not bid_f or not ask_f or bid_f <= 0 or ask_f <= 0:
        return None
    return {"bid": bid_f, "ask": ask_f, "source": "polygon_open_close", "raw_status": raw.get("status")}


def tradier_option_quote(occ_symbol: str) -> dict[str, Any] | None:
    """Delayed quote. Needs TRADIER_TOKEN. Sandbox host if TRADIER_SANDBOX=1."""
    token = os.environ.get("TRADIER_TOKEN")
    if not token:
        return None
    host = "https://sandbox.tradier.com" if os.environ.get("TRADIER_SANDBOX") == "1" else "https://api.tradier.com"
    url = f"{host}/v1/markets/quotes?{urlencode({'symbols': occ_symbol, 'greeks': 'true'})}"
    raw = get_json(url, extra_headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    quotes = ((raw or {}).get("quotes") or {}).get("quote")
    if quotes is None:
        return None
    if isinstance(quotes, list):
        quotes = quotes[0] if quotes else None
    if not isinstance(quotes, dict):
        return None
    try:
        bid = float(quotes.get("bid") or 0)
        ask = float(quotes.get("ask") or 0)
    except (TypeError, ValueError):
        return None
    if bid <= 0 or ask <= 0:
        return None
    return {"bid": bid, "ask": ask, "source": "tradier_quote"}
