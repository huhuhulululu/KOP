from __future__ import annotations

from datetime import date

from kop.config import PLAYBOOK, SYMBOL
from kop.ledger import Store
from kop.market.iv import iv30_range_rank
from kop.models import Bar, EarningsEvent, UnderlyingQuote
from kop.playbook import decide, trading_days_before
from kop.selector import select_recipe


def paper_once(
    store: Store,
    *,
    asof: date,
    event: EarningsEvent | None,
    bars: list[Bar],
    under: UnderlyingQuote | None,
    implied_move_pct: float | None = None,
    hist_abs_median: float | None = None,
) -> dict:
    """One paper pass. Selects a public recipe. Does not place orders."""
    decision = decide(
        symbol=SYMBOL,
        asof=asof,
        event=event,
        bars=bars,
        under=under,
        iv_history=store.iv30_history(SYMBOL),
        countable_tape=store.countable_tape(),
    )
    days_before = trading_days_before(event, asof, bars) if event else None
    iv_rank = iv30_range_rank(under) if under else None
    chosen, why, select_details = select_recipe(
        days_before=days_before,
        iv_rank=iv_rank,
        implied_move_pct=implied_move_pct,
        hist_abs_median=hist_abs_median,
    )
    store.journal(
        "reject" if not decision.allow else "propose",
        decision.reason,
        symbol=SYMBOL,
        event_key=event.key if event else None,
        payload={"decision": decision.details, "recipe": chosen.id, "select": why},
    )
    return {
        "playbook": PLAYBOOK,
        "allow": decision.allow,
        "reason": decision.reason,
        "details": decision.details,
        "filled": False,
        "selected_recipe": chosen.as_dict(),
        "select_reason": why,
        "select_details": select_details,
    }
