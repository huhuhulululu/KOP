"""One live-paper session. Mark, exit, maybe open. Broker door stays locked."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from kop.broker import LiveTradingDisabled, live_blockers, submit_live
from kop.calendar import event_from_key, last_event
from kop.config import PAPER_FILLS, PLAYBOOK, SYMBOL
from kop.ledger import Store
from kop.live import LiveBundle, collect_live
from kop.paper.book import close_paper, exit_reason, mark_to_close, open_paper
from kop.paper.risk import pick_expiration, select_iron_condor
from kop.phase1 import evaluate_phase1
from kop.selector import select_recipe


def run_day(
    store: Store | None = None,
    *,
    bundle: LiveBundle | None = None,
    paper_fills: bool = PAPER_FILLS,
) -> dict[str, Any]:
    store = store or Store()
    live = bundle or collect_live(store)
    chosen, why, select_details = select_recipe(live.snapshot)
    month = live.asof.isoformat()[:7]
    phase = evaluate_phase1(
        snapshot=live.snapshot,
        countable_tape=store.countable_tape(),
        realized_month_usd=store.realized_pnl(month),
        realized_all_usd=store.realized_pnl(),
    )
    actions: list[dict[str, Any]] = []
    for position in store.open_positions():
        actions.append(_manage(store, position, live))

    opened = None
    if store.open_position_count() == 0:
        opened = _maybe_open(store, live, chosen.id, why, paper_fills)
        if opened:
            actions.append({"open": opened})

    broker = {"submitted": False, "blockers": live_blockers()}
    try:
        submit_live({"structure": chosen.id, "asof": live.asof.isoformat()})
    except LiveTradingDisabled as exc:
        broker["refused"] = str(exc)

    payload = {
        "playbook": PLAYBOOK,
        "asof": live.asof.isoformat(),
        "symbol": SYMBOL,
        "last_event": (last_event(SYMBOL, live.asof).key if last_event(SYMBOL, live.asof) else None),
        "next_event": live.event.key if live.event else None,
        "next_event_confirmed": bool(live.event and live.event.confirmed),
        "days_before": live.snapshot.days_before,
        "selected": chosen.as_dict(),
        "select_reason": why,
        "select_details": select_details,
        "snapshot": live.snapshot.as_dict(),
        "gates": [row.as_dict() for row in live.snapshot.gate_table()],
        "phase1": phase.as_dict(),
        "open_positions": store.open_positions(),
        "actions": actions,
        "opened": opened,
        "filled": bool(opened and opened.get("filled")),
        "live": False,
        "broker": broker,
    }
    store.record_snapshot(
        asof=live.asof.isoformat(),
        symbol=SYMBOL,
        event_key=live.event.key if live.event else None,
        selected_recipe=chosen.id,
        select_reason=why,
        payload=payload,
    )
    kinds = []
    for item in actions:
        if item.get("open"):
            kinds.append("open")
        elif item.get("close"):
            kinds.append("close")
        else:
            kinds.append("stand")
    store.journal("day", why, symbol=SYMBOL, event_key=live.event.key if live.event else None, payload={"actions": kinds})
    return payload


def _manage(store: Store, position: dict[str, Any], live: LiveBundle) -> dict[str, Any]:
    extra = position.get("extra") or {}
    entry_cash = float(extra.get("entry_cash") or 0.0)
    entry_net = float(extra.get("net_premium") or 0.0)
    try:
        mark = mark_to_close(live.quotes, _book_legs(position), entry_cash)
    except Exception as exc:
        return {"position_id": position["id"], "mark_error": str(exc)}
    mark["asof"] = live.asof.isoformat()
    store.record_mark(int(position["id"]), live.asof.isoformat(), mark)
    event = event_from_key(position.get("event_key") or "") or live.event
    reason = exit_reason(
        asof=live.asof,
        event=event,
        bars=live.bars,
        entry_net=entry_net,
        mark=mark,
        max_loss_usd=float(position["max_loss_usd"]),
    )
    if reason:
        closed = close_paper(store, position=position, quotes=live.quotes, asof=live.asof, reason=reason)
        return {"close": closed}
    return {"mark": {"position_id": position["id"], "mark_pnl_usd": mark["mark_pnl_usd"], "close_debit": mark["close_debit"]}}


def _maybe_open(store: Store, live: LiveBundle, recipe_id: str, why: str, paper_fills: bool) -> dict[str, Any] | None:
    blockers = live.snapshot.short_vol_blockers()
    if not paper_fills:
        return {"filled": False, "reason": "paper_fills_disabled"}
    if recipe_id != "short_iron_condor":
        return {"filled": False, "reason": why, "short_vol_blockers": blockers}
    if blockers:
        return {"filled": False, "reason": blockers[0], "short_vol_blockers": blockers}
    if live.event is None:
        return {"filled": False, "reason": "no_earnings_event"}
    if not live.event.confirmed:
        return {"filled": False, "reason": "event_unconfirmed_yahoo_only"}
    expiry = live.snapshot.front_expiry or pick_expiration(live.quotes, live.asof)
    if expiry is None:
        return {"filled": False, "reason": "no_front_expiry"}
    try:
        fill = select_iron_condor(live.quotes, live.under.spot, expiry)
    except Exception as exc:
        return {"filled": False, "reason": f"structure_refused:{exc}"}
    return open_paper(store, fill=fill, event=live.event, asof=live.asof, spot=live.under.spot, reason=why)


def _book_legs(position: dict[str, Any]):
    from kop.paper.book import _legs_from_position

    return _legs_from_position(position)
