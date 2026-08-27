"""Paper book. Open / mark / close on CBOE bid/ask. Never mid. Never a broker."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from kop.broker import paper_ticket
from kop.config import CREDIT_TAKE_FRACTION, MAX_LOSS_USD, MULTIPLIER, PLAYBOOK
from kop.ledger import Store
from kop.models import EarningsEvent, LegFill, OptionQuote, StructureFill
from kop.paper.fills import cash_effect, fill_buy, fill_sell, structure_fees
from kop.playbook import exit_date_for


def _json_leg(leg: LegFill) -> dict[str, Any]:
    payload = leg.as_dict()
    payload["occ"]["expiration"] = leg.occ.expiration.isoformat()
    return payload


def quote_by_occ(quotes: list[OptionQuote], occ_symbol: str) -> OptionQuote | None:
    compact = occ_symbol.replace(" ", "").upper()
    return next((q for q in quotes if q.occ.symbol == compact), None)


def close_fills(quotes: list[OptionQuote], open_legs: list[LegFill]) -> list[LegFill]:
    out: list[LegFill] = []
    for leg in open_legs:
        quote = quote_by_occ(quotes, leg.occ.symbol)
        if quote is None:
            raise ValueError(f"missing_quote_{leg.occ.symbol}")
        if leg.side == "sell":
            out.append(fill_buy(quote, leg.quantity))
        else:
            out.append(fill_sell(quote, leg.quantity))
    return out


def close_debit_per_share(exit_legs: list[LegFill], open_legs: list[LegFill]) -> float:
    """Debit to flatten, per share, before fees."""
    by_occ = {leg.occ.symbol: leg for leg in open_legs}
    debit = 0.0
    for leg in exit_legs:
        opened = by_occ[leg.occ.symbol]
        if opened.side == "sell":
            debit += leg.fill_price
        else:
            debit -= leg.fill_price
    return debit


def mark_to_close(quotes: list[OptionQuote], open_legs: list[LegFill], entry_cash: float) -> dict[str, Any]:
    exits = close_fills(quotes, open_legs)
    exit_cash = sum(cash_effect(leg) for leg in exits)
    fees = structure_fees(exits)
    return {
        "close_debit": close_debit_per_share(exits, open_legs),
        "exit_cash": exit_cash,
        "exit_fees_usd": fees,
        "mark_pnl_usd": entry_cash + exit_cash,
        "legs": [leg.as_dict() for leg in exits],
    }


def exit_reason(
    *,
    asof: date,
    event: EarningsEvent | None,
    bars,
    entry_net: float,
    mark: dict[str, Any],
    max_loss_usd: float,
) -> str | None:
    if mark["mark_pnl_usd"] <= -max_loss_usd + 1e-9:
        return "max_loss"
    if entry_net > 0 and mark["close_debit"] <= CREDIT_TAKE_FRACTION * entry_net + 1e-9:
        return "credit_take_50pct"
    if event is not None and bars:
        try:
            leave = exit_date_for(event, bars)
        except Exception:
            leave = None
        if leave is not None and asof >= leave:
            return "time_stop_t_plus_1"
    return None


def open_paper(
    store: Store,
    *,
    fill: StructureFill,
    event: EarningsEvent | None,
    asof: date,
    spot: float,
    reason: str,
) -> dict[str, Any]:
    if store.open_position_count() >= 1:
        raise RuntimeError("max_open_positions")
    if fill.max_loss_usd > MAX_LOSS_USD + 1e-9:
        raise RuntimeError(f"max_loss_{fill.max_loss_usd:.2f}")
    entry_cash = sum(cash_effect(leg) for leg in fill.legs)
    legs_payload = [_json_leg(leg) for leg in fill.legs]
    position_id = store.insert_position(
        playbook=PLAYBOOK,
        symbol=event.symbol if event else fill.legs[0].occ.root,
        event_key=event.key if event else None,
        structure=fill.name,
        expiration=fill.expiration.isoformat(),
        max_loss_usd=fill.max_loss_usd,
        credit_usd=fill.max_gain_usd,
        status="open",
        entry_reason=reason,
        legs_json=json.dumps(legs_payload),
        extra={
            "asof": asof.isoformat(),
            "spot": spot,
            "net_premium": fill.net_premium,
            "entry_cash": entry_cash,
            "fees_usd": fill.fees_usd,
        },
    )
    for leg in fill.legs:
        store.insert_fill(position_id, leg, reason="paper_open")
    if event is not None:
        store.record_event(event.symbol, event.announce_date.isoformat(), event.session, event.fiscal_label, "paper_book")
    store.journal(
        "paper_open",
        reason,
        symbol=event.symbol if event else None,
        event_key=event.key if event else None,
        payload={"position_id": position_id, "entry_cash": entry_cash, "max_loss_usd": fill.max_loss_usd},
    )
    ticket = paper_ticket(fill.name, legs_payload, reason)
    return {
        "position_id": position_id,
        "entry_cash": entry_cash,
        "max_loss_usd": fill.max_loss_usd,
        "max_gain_usd": fill.max_gain_usd,
        "net_premium": fill.net_premium,
        "ticket": ticket,
        "filled": True,
        "live": False,
    }


def close_paper(
    store: Store,
    *,
    position: dict[str, Any],
    quotes: list[OptionQuote],
    asof: date,
    reason: str,
) -> dict[str, Any]:
    open_legs = _legs_from_position(position)
    extra = position.get("extra") or {}
    entry_cash = float(extra.get("entry_cash") or 0.0)
    mark = mark_to_close(quotes, open_legs, entry_cash)
    mark["asof"] = asof.isoformat()
    exits = close_fills(quotes, open_legs)
    for leg in exits:
        store.insert_fill(int(position["id"]), leg, reason=f"paper_close:{reason}")
    store.close_position(int(position["id"]), reason, mark["mark_pnl_usd"], mark)
    store.journal(
        "paper_close",
        reason,
        symbol=position.get("symbol"),
        event_key=position.get("event_key"),
        payload={"position_id": position["id"], "pnl_usd": mark["mark_pnl_usd"], "asof": asof.isoformat()},
    )
    return {"position_id": position["id"], "reason": reason, "pnl_usd": mark["mark_pnl_usd"], "mark": mark}


def _legs_from_position(position: dict[str, Any]) -> list[LegFill]:
    from datetime import date as date_cls

    from kop.models import Occ

    raw = position.get("legs") or []
    out: list[LegFill] = []
    for item in raw:
        occ_raw = item["occ"]
        exp = occ_raw["expiration"]
        if isinstance(exp, str):
            exp = date_cls.fromisoformat(exp)
        occ = Occ(
            root=occ_raw["root"],
            expiration=exp,
            right=occ_raw["right"],
            strike=float(occ_raw["strike"]),
            symbol=occ_raw["symbol"],
        )
        out.append(
            LegFill(
                occ=occ,
                side=item["side"],
                quantity=int(item["quantity"]),
                bid=float(item["bid"]),
                ask=float(item["ask"]),
                fill_price=float(item["fill_price"]),
                slippage=float(item["slippage"]),
                fee_usd=float(item["fee_usd"]),
                quote_kind=item.get("quote_kind", "bid_ask"),
            )
        )
    return out
