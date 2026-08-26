from __future__ import annotations

from datetime import date

from kop.config import PLAYBOOK, SYMBOL
from kop.ledger import Store
from kop.models import Bar, EarningsEvent, UnderlyingQuote
from kop.playbook import decide


def paper_once(
    store: Store,
    *,
    asof: date,
    event: EarningsEvent | None,
    bars: list[Bar],
    under: UnderlyingQuote | None,
) -> dict:
    """One paper pass. Does not place orders. Refuses without tape / AUTO_TRADE."""
    decision = decide(
        symbol=SYMBOL,
        asof=asof,
        event=event,
        bars=bars,
        under=under,
        iv_history=store.iv30_history(SYMBOL),
        countable_tape=store.countable_tape(),
    )
    store.journal(
        "reject" if not decision.allow else "enter",
        decision.reason,
        symbol=SYMBOL,
        event_key=event.key if event else None,
        payload=decision.details,
    )
    return {
        "playbook": PLAYBOOK,
        "allow": decision.allow,
        "reason": decision.reason,
        "details": decision.details,
        "filled": False,
    }
