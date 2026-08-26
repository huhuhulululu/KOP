from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone

from kop.calendar import completed_for_tape, fetch_yahoo_next_earnings, next_event, seeded_events
from kop.config import PLAYBOOK, SYMBOL, WATCHLIST_OBSERVE_ONLY
from kop.forbidden import assert_clean_process
from kop.ledger import Store
from kop.market.cboe import attach_iv_range, fetch_chain, fetch_iv_range
from kop.market.iv import atm_quotes, iv30_range_rank, straddle_implied_move_pct
from kop.market.yahoo import fetch_bars
from kop.paper.engine import paper_once
from kop.paper.exercise import assignment_notes
from kop.paper.risk import long_call_fill, long_straddle_fill, pick_expiration, select_iron_condor
from kop.playbook import decide, trading_days_before
from kop.research import persist, replay
from kop.recipes import RECIPES, allowed_paper, forbidden
from kop.scoring import edge
from kop.selector import historical_median_abs, select_recipe


def main(argv: list[str] | None = None) -> int:
    assert_clean_process()
    parser = argparse.ArgumentParser(prog="kop", description="KOP listed-options paper tape. Not Kalshi.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("calendar", help="print seeded NVDA earnings")
    sub.add_parser("chain", help="pull CBOE delayed chain summary")
    sub.add_parser("observe", help="record a live observation; no order")
    sub.add_parser("replay", help="replay last 6 completed NVDA earnings")
    sub.add_parser("tape", help="print research tape")
    sub.add_parser("sweep", help="path-score public recipes on the same events")
    sub.add_parser("recipes", help="print the public recipe catalog")
    sub.add_parser("select", help="pick a recipe from public rules; no order")
    sub.add_parser("status", help="ledger + gate status")
    sub.add_parser("paper-once", help="select a recipe; refuse to fill unless AUTO_TRADE")
    args = parser.parse_args(argv)
    handlers = {
        "calendar": cmd_calendar,
        "chain": cmd_chain,
        "observe": cmd_observe,
        "replay": cmd_replay,
        "tape": cmd_tape,
        "sweep": cmd_sweep,
        "recipes": cmd_recipes,
        "select": cmd_select,
        "status": cmd_status,
        "paper-once": cmd_paper_once,
    }
    return handlers[args.cmd]()


def cmd_calendar() -> int:
    today = datetime.now(timezone.utc).date()
    print(f"symbol={SYMBOL} asof={today} playbook={PLAYBOOK}")
    print("watchlist_observe_only", ",".join(WATCHLIST_OBSERVE_ONLY))
    print("seeded:")
    for event in seeded_events(SYMBOL):
        mark = "NEXT" if next_event(SYMBOL, today) and event.key == next_event(SYMBOL, today).key else ""
        print(f"  {event.announce_date} {event.session} {event.fiscal_label} {mark}")
    print("tape_window:")
    for event in completed_for_tape(SYMBOL, today):
        print(f"  {event.announce_date} {event.fiscal_label}")
    yahoo = fetch_yahoo_next_earnings(SYMBOL)
    print(f"yahoo_next_earnings={yahoo}")
    return 0


def _live_under_chain():
    under, quotes = fetch_chain(SYMBOL)
    high, low = fetch_iv_range(SYMBOL)
    under = attach_iv_range(under, high, low)
    return under, quotes


def cmd_chain() -> int:
    under, quotes = _live_under_chain()
    expiry = pick_expiration(quotes, date.fromisoformat(under.asof[:10]) if under.asof else datetime.now(timezone.utc).date())
    print(json.dumps(_chain_summary(under, quotes, expiry), indent=2))
    return 0


def _chain_summary(under, quotes, expiry) -> dict:
    pair = atm_quotes(quotes, expiry, under.spot) if expiry else None
    sell_move = buy_move = None
    atm = None
    if pair:
        call, put = pair
        sell_move = straddle_implied_move_pct(call, put, under.spot, side="sell")
        buy_move = straddle_implied_move_pct(call, put, under.spot, side="buy")
        atm = {
            "strike": call.occ.strike,
            "call": {"bid": call.bid, "ask": call.ask, "iv": call.iv, "delta": call.delta},
            "put": {"bid": put.bid, "ask": put.ask, "iv": put.iv, "delta": put.delta},
            "straddle_bid": call.bid + put.bid,
            "straddle_ask": call.ask + put.ask,
        }
    return {
        "symbol": under.symbol,
        "spot_rth_close": under.close,
        "last": under.last,
        "asof": under.asof,
        "iv30": under.iv30,
        "iv30_annual_high": under.iv30_annual_high,
        "iv30_annual_low": under.iv30_annual_low,
        "iv30_range_rank": iv30_range_rank(under),
        "contracts": len(quotes),
        "front_expiry": expiry.isoformat() if expiry else None,
        "atm": atm,
        "implied_move_sell_bid_pct": sell_move,
        "implied_move_buy_ask_pct": buy_move,
        "note": "implied move uses bid or ask, never mid",
    }


def cmd_observe() -> int:
    store = Store()
    under, quotes = _live_under_chain()
    asof = date.fromisoformat(under.asof[:10]) if under.asof else datetime.now(timezone.utc).date()
    expiry = pick_expiration(quotes, asof)
    summary = _chain_summary(under, quotes, expiry)
    structure = None
    long_s = long_c = None
    err = None
    try:
        if expiry:
            structure = select_iron_condor(quotes, under.spot, expiry)
            long_s = long_straddle_fill(quotes, under.spot, expiry)
            long_c = long_call_fill(quotes, under.spot, expiry)
    except Exception as exc:
        err = str(exc)
    pair = atm_quotes(quotes, expiry, under.spot) if expiry else None
    shorts = [pair[0], pair[1]] if pair else []
    bars = fetch_bars(SYMBOL)
    event = next_event(SYMBOL, asof)
    decision = decide(
        symbol=SYMBOL,
        asof=asof,
        event=event,
        bars=bars,
        under=under,
        iv_history=store.iv30_history(SYMBOL),
        countable_tape=store.countable_tape(),
    )
    payload = {
        "summary": summary,
        "decision": {"allow": decision.allow, "reason": decision.reason, "details": decision.details},
        "proposed_iron_condor": _structure_view(structure) if structure else None,
        "contrast_live": {
            "long_straddle": _structure_view(long_s) if long_s else None,
            "long_call": _structure_view(long_c) if long_c else None,
            "do_nothing": {"max_loss_usd": 0.0, "note": "control"},
        },
        "early_exercise": assignment_notes(shorts, under) if shorts else [],
        "structure_error": err,
        "scoring_example": edge(0.55, 0.4).as_dict(),
    }
    store.record_observation(SYMBOL, under.spot, under.iv30, payload)
    store.journal("observe", decision.reason, symbol=SYMBOL, event_key=event.key if event else None, payload=payload["decision"])
    print(json.dumps(payload, indent=2, default=str))
    return 0


def _structure_view(fill) -> dict:
    return {
        "name": fill.name,
        "expiration": fill.expiration.isoformat(),
        "debit_or_credit": fill.debit_or_credit,
        "net_premium": fill.net_premium,
        "max_loss_usd": fill.max_loss_usd if fill.max_loss_usd != float("inf") else "unlimited_upside_debit_is_defined",
        "max_gain_usd": fill.max_gain_usd if fill.max_gain_usd != float("inf") else "unlimited",
        "fees_usd": fill.fees_usd,
        "quote_kind": fill.quote_kind,
        "legs": [
            {
                "occ": leg.occ.symbol,
                "side": leg.side,
                "bid": leg.bid,
                "ask": leg.ask,
                "fill": leg.fill_price,
                "fee": leg.fee_usd,
            }
            for leg in fill.legs
        ],
    }


def cmd_replay() -> int:
    rows = replay()
    result = persist(rows)
    print(json.dumps({"n": result["n"], "countable_tape": result["countable_tape"], "json": result["json"], "markdown": result["markdown"]}, indent=2))
    return 0


def cmd_tape() -> int:
    store = Store()
    rows = [dict(row) for row in store.tape_rows()]
    print(json.dumps({"countable": store.countable_tape(), "rows": rows}, indent=2, default=str))
    return 0


def cmd_sweep() -> int:
    from kop.research import contrast_for_row

    store = Store()
    rows = store.tape_rows()
    if not rows:
        rows_model = replay()
        persist(rows_model, store)
        rows = store.tape_rows()
    from kop.models import TapeRow
    from datetime import date as date_cls

    models = []
    for row in rows:
        model = TapeRow(
            event_key=row["event_key"],
            symbol=row["symbol"],
            fiscal_label=row["fiscal_label"],
            announce_date=date_cls.fromisoformat(row["announce_date"]),
            session=row["session"],
            entry_date=date_cls.fromisoformat(row["entry_date"]) if row["entry_date"] else None,
            days_before=row["days_before"],
            entry_close=row["entry_close"] if "entry_close" in row.keys() else None,
            event_close=row["event_close"] if "event_close" in row.keys() else None,
            reaction_open=row["reaction_open"] if "reaction_open" in row.keys() else None,
            reaction_high=row["reaction_high"] if "reaction_high" in row.keys() else None,
            reaction_low=row["reaction_low"] if "reaction_low" in row.keys() else None,
            reaction_close=row["reaction_close"] if "reaction_close" in row.keys() else None,
            iv_rank=row["iv_rank"],
            iv_percentile=row["iv_percentile"],
            iv_source=row["iv_source"],
            structure=row["structure"],
            strikes=json_loads(row["strikes_json"]),
            expiration=date_cls.fromisoformat(row["expiration"]) if row["expiration"] else None,
            entry_quote_kind=row["entry_quote_kind"],
            entry_net=row["entry_net"],
            gap_pct=row["gap_pct"],
            close_move_pct=row["close_move_pct"],
            high_move_pct=row["high_move_pct"],
            low_move_pct=row["low_move_pct"],
            vendor_implied_move_pct=row["vendor_implied_move_pct"],
            vendor_iv_crush_pct=row["vendor_iv_crush_pct"],
            vendor_source=row["vendor_source"],
            exit_rule=row["exit_rule"],
            exit_date=date_cls.fromisoformat(row["exit_date"]) if row["exit_date"] else None,
            exit_net=row["exit_net"],
            fees_usd=row["fees_usd"],
            pnl_usd=row["pnl_usd"],
            fill_status=row["fill_status"],
            notes=row["notes"],
        )
        models.append(model)
    sweep = [contrast_for_row(model, models) for model in models]
    print(json.dumps(sweep, indent=2))
    return 0


def cmd_recipes() -> int:
    print(
        json.dumps(
            {
                "allowed": [item.as_dict() for item in allowed_paper()],
                "forbidden": [item.as_dict() for item in forbidden()],
                "all": [item.as_dict() for item in RECIPES],
            },
            indent=2,
        )
    )
    return 0


def _hist_and_implied(under=None, quotes=None) -> tuple[float | None, float | None, str | None]:
    rows = replay()
    hist = historical_median_abs([row.close_move_pct for row in rows if row.close_move_pct is not None])
    implied = None
    source = None
    if under is not None and quotes is not None:
        expiry = pick_expiration(quotes, date.fromisoformat(under.asof[:10]) if under.asof else datetime.now(timezone.utc).date())
        pair = atm_quotes(quotes, expiry, under.spot) if expiry else None
        if pair:
            implied = straddle_implied_move_pct(pair[0], pair[1], under.spot, side="sell")
            source = "cboe_atm_straddle_bid"
    return hist, implied, source


def cmd_select() -> int:
    today = datetime.now(timezone.utc).date()
    bars = fetch_bars(SYMBOL)
    event = next_event(SYMBOL, today)
    try:
        under, quotes = _live_under_chain()
    except RuntimeError as exc:
        print(json.dumps({"error": str(exc)}))
        return 1
    hist, implied, source = _hist_and_implied(under, quotes)
    days_before = trading_days_before(event, today, bars) if event else None
    iv_rank = iv30_range_rank(under)
    chosen, why, details = select_recipe(
        days_before=days_before,
        iv_rank=iv_rank,
        implied_move_pct=implied,
        hist_abs_median=hist,
    )
    details["implied_source"] = source
    print(
        json.dumps(
            {
                "selected": chosen.as_dict(),
                "reason": why,
                "details": details,
                "filled": False,
            },
            indent=2,
        )
    )
    return 0


def json_loads(raw):
    if not raw:
        return None
    import json

    return json.loads(raw)


def cmd_status() -> int:
    store = Store()
    today = datetime.now(timezone.utc).date()
    bars = fetch_bars(SYMBOL)
    event = next_event(SYMBOL, today)
    try:
        under, _quotes = _live_under_chain()
    except RuntimeError as exc:
        under = None
        live_error = str(exc)
    else:
        live_error = None
    days_before = trading_days_before(event, today, bars) if event else None
    decision = decide(
        symbol=SYMBOL,
        asof=today,
        event=event,
        bars=bars,
        under=under,
        iv_history=store.iv30_history(SYMBOL),
        countable_tape=store.countable_tape(),
    )
    print(
        json.dumps(
            {
                "ledger": store.summary(),
                "next_event": event.key if event else None,
                "days_before": days_before,
                "live_error": live_error,
                "decision": {"allow": decision.allow, "reason": decision.reason, "details": decision.details},
                "loop": "closed",
            },
            indent=2,
        )
    )
    return 0


def cmd_paper_once() -> int:
    store = Store()
    today = datetime.now(timezone.utc).date()
    bars = fetch_bars(SYMBOL)
    event = next_event(SYMBOL, today)
    try:
        under, _quotes = _live_under_chain()
    except RuntimeError:
        under = None
    hist = implied = None
    if under is not None:
        try:
            _u, quotes = _live_under_chain()
            hist, implied, _src = _hist_and_implied(_u, quotes)
        except RuntimeError:
            hist, implied, _src = _hist_and_implied()
    result = paper_once(
        store,
        asof=today,
        event=event,
        bars=bars,
        under=under,
        implied_move_pct=implied,
        hist_abs_median=hist,
    )
    print(json.dumps(result, indent=2))
    return 0 if not result["allow"] or not result["filled"] else 0
