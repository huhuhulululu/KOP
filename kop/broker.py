"""Order port. Paper books CBOE bid/ask. Live broker stays locked.

No data subscription. A future broker account is not a market-data plan.
This module will not send an order while ALLOW_LIVE is false.
"""

from __future__ import annotations

import os
from typing import Any

from kop.config import ALLOW_LIVE, AUTO_TRADE


class LiveTradingDisabled(RuntimeError):
    pass


def broker_configured() -> bool:
    return bool(os.environ.get("TRADIER_TOKEN") or os.environ.get("BROKER_API_KEY"))


def live_blockers() -> list[str]:
    out: list[str] = []
    if not ALLOW_LIVE:
        out.append("ALLOW_LIVE=false")
    if not AUTO_TRADE:
        out.append("AUTO_TRADE=false")
    if not broker_configured():
        out.append("no_broker_credentials")
    return out


def submit_live(order: dict[str, Any]) -> dict[str, Any]:
    blockers = live_blockers()
    if blockers:
        raise LiveTradingDisabled(",".join(blockers))
    raise LiveTradingDisabled("live_broker_adapter_not_wired")


def paper_ticket(fill_name: str, legs: list[dict[str, Any]], reason: str) -> dict[str, Any]:
    return {
        "venue": "paper_cboe_bid_ask",
        "live": False,
        "structure": fill_name,
        "legs": legs,
        "reason": reason,
        "live_blockers": live_blockers(),
    }
