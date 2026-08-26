"""NVDA earnings research tape.

Spot path comes from Yahoo daily bars (real).
Option entry/exit stay missing until a bid/ask chain exists for that day.
Vendor implied-move / crush numbers are annotations, not fills.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

from kop.calendar import completed_for_tape
from kop.config import (
    CATALOG_RESEARCH,
    CREDIT_TAKE_FRACTION,
    DEFAULT_ENTRY_DAYS_BEFORE,
    EXIT_TRADING_DAYS_AFTER,
    PLAYBOOK,
    RESEARCH_DIR,
    STRUCTURE,
    SYMBOL,
)
from kop.ledger import Store
from kop.market.yahoo import bar_map, fetch_bars, trading_days
from kop.models import Bar, EarningsEvent, TapeRow
from kop.playbook import entry_date_for, exit_date_for

# ORATS-via-VolRadar 10-day ATM proxy. Not a fill. Not front-expiry IV.
VENDOR_NOTES: dict[str, dict] = {
    "2025-08-27": {
        "implied_move_pct": 3.0,
        "iv_crush_pct": 50.0,
        "source": "volradar/ORATS 10-day ATM proxy",
    },
    "2025-11-19": {
        "implied_move_pct": 3.4,
        "iv_crush_pct": 20.0,
        "source": "volradar/ORATS 10-day ATM proxy",
    },
    "2026-02-25": {
        "implied_move_pct": 3.0,
        "iv_crush_pct": 26.0,
        "source": "volradar/ORATS 10-day ATM proxy",
    },
    "2026-05-20": {
        "implied_move_pct": 2.8,
        "iv_crush_pct": 34.0,
        "source": "volradar/ORATS 10-day ATM proxy",
    },
}


def _pct(new: float, old: float) -> float:
    return 100.0 * (new - old) / old


def path_for_event(event: EarningsEvent, bars: list[Bar]) -> dict:
    days = trading_days(bars)
    by = bar_map(bars)
    entry = entry_date_for(event, bars)
    react = days[event.reaction_index(days)]
    event_bar = by[event.announce_date]
    react_bar = by[react]
    entry_bar = by[entry]
    exit_day = exit_date_for(event, bars)
    return {
        "entry_date": entry,
        "entry_close": entry_bar.close,
        "event_close": event_bar.close,
        "reaction_date": react,
        "reaction_open": react_bar.open,
        "reaction_high": react_bar.high,
        "reaction_low": react_bar.low,
        "reaction_close": react_bar.close,
        "exit_date": exit_day,
        "gap_pct": _pct(react_bar.open, event_bar.close),
        "close_move_pct": _pct(react_bar.close, event_bar.close),
        "high_move_pct": _pct(react_bar.high, event_bar.close),
        "low_move_pct": _pct(react_bar.low, event_bar.close),
        "days_before": DEFAULT_ENTRY_DAYS_BEFORE,
    }


def build_row(event: EarningsEvent, bars: list[Bar]) -> TapeRow:
    path = path_for_event(event, bars)
    note = VENDOR_NOTES.get(event.announce_date.isoformat(), {})
    implied = note.get("implied_move_pct")
    breach = None
    if implied is not None:
        breach = abs(path["close_move_pct"]) > implied
    notes = [
        "option_quotes_missing: no historical bid/ask chain, so no fill and no fee P&L",
        f"entry_close={path['entry_close']:.2f} event_close={path['event_close']:.2f}",
        f"reaction {path['reaction_date']} O={path['reaction_open']:.2f} H={path['reaction_high']:.2f} "
        f"L={path['reaction_low']:.2f} C={path['reaction_close']:.2f}",
    ]
    if implied is not None:
        notes.append(
            f"vendor_implied_move=±{implied}% close_move={path['close_move_pct']:+.2f}% "
            f"breached={breach} (path stress, not P&L)"
        )
    else:
        notes.append("vendor_implied_move=missing")
    return TapeRow(
        event_key=event.key,
        symbol=event.symbol,
        fiscal_label=event.fiscal_label,
        announce_date=event.announce_date,
        session=event.session,
        entry_date=path["entry_date"],
        days_before=path["days_before"],
        iv_rank=None,
        iv_percentile=None,
        iv_source="missing_no_daily_iv_series",
        structure=STRUCTURE,
        strikes=None,
        expiration=None,
        entry_quote_kind="missing",
        entry_net=None,
        gap_pct=path["gap_pct"],
        close_move_pct=path["close_move_pct"],
        high_move_pct=path["high_move_pct"],
        low_move_pct=path["low_move_pct"],
        vendor_implied_move_pct=implied,
        vendor_iv_crush_pct=note.get("iv_crush_pct"),
        vendor_source=note.get("source", ""),
        exit_rule=f"50% credit or T+{EXIT_TRADING_DAYS_AFTER}, first; not filled",
        exit_date=path["exit_date"],
        exit_net=None,
        fees_usd=None,
        pnl_usd=None,
        fill_status="missing_quotes",
        notes="; ".join(notes),
    )


def contrast_for_row(row: TapeRow) -> dict:
    """Same event, four variants. Option variants stay unscored without quotes."""
    do_nothing = {"variant": "do_nothing", "pnl_usd": 0.0, "status": "scored"}
    missing = {
        "status": "unscored_missing_quotes",
        "pnl_usd": None,
        "note": "need bid/ask chain on entry and exit dates",
    }
    path_note = None
    if row.vendor_implied_move_pct is not None and row.close_move_pct is not None:
        path_note = {
            "close_move_pct": row.close_move_pct,
            "vendor_implied_move_pct": row.vendor_implied_move_pct,
            "close_beyond_implied": abs(row.close_move_pct) > row.vendor_implied_move_pct,
        }
    return {
        "event": row.event_key,
        "short_iron_condor": {**missing, "variant": "short_iron_condor", "path": path_note},
        "long_straddle": {**missing, "variant": "long_straddle"},
        "long_call": {**missing, "variant": "long_call"},
        "do_nothing": do_nothing,
    }


def replay(symbol: str = SYMBOL, asof: date | None = None, bars: list[Bar] | None = None) -> list[TapeRow]:
    asof = asof or datetime.now(timezone.utc).date()
    events = completed_for_tape(symbol, asof)
    if bars is None:
        bars = fetch_bars(symbol)
    return [build_row(event, bars) for event in events]


def persist(rows: list[TapeRow], store: Store | None = None) -> dict:
    store = store or Store()
    for row in rows:
        store.record_event(row.symbol, row.announce_date.isoformat(), row.session, row.fiscal_label, "research_replay")
        store.upsert_tape(row)
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    CATALOG_RESEARCH.mkdir(parents=True, exist_ok=True)
    payload = {
        "playbook": PLAYBOOK,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "countable_for_loop": store.countable_tape(),
        "credit_take_fraction": CREDIT_TAKE_FRACTION,
        "rows": [row.as_dict() for row in rows],
        "contrast": [contrast_for_row(row) for row in rows],
    }
    json_path = RESEARCH_DIR / "nvda_earnings_tape.json"
    md_path = CATALOG_RESEARCH / "nvda_earnings_tape.md"
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(rows, payload["contrast"], store.countable_tape()), encoding="utf-8")
    store.journal("research", "replay_written", symbol=SYMBOL, payload={"n": len(rows)})
    return {"json": str(json_path), "markdown": str(md_path), "countable_tape": store.countable_tape(), "n": len(rows)}


def render_markdown(rows: list[TapeRow], contrast: list[dict], countable: int) -> str:
    lines = [
        "# NVDA 财报金带子（研究，不是成交）",
        "",
        f"Playbook：`{PLAYBOOK}`。进场默认 T−{DEFAULT_ENTRY_DAYS_BEFORE} 个交易日。",
        "现货路径来自 Yahoo 日线。权利金进/出没有历史买卖价，所以 **往返盈亏空着**。",
        "Vendor implied / crush 是 VolRadar 引用的 ORATS 10 日 ATM 代理，**不是** 当时链上的买卖价，不能当 fill。",
        f"可计入循环的样本（human / recorded_bid_ask）：**{countable}**。不到 4 笔就不许开策略循环。",
        "",
        "| 事件 | 进场日 | IV rank | 结构 | 进场价 | 跳空 | 收盘路径 | 出场 | 往返 | 状态 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        iv = "missing"
        entry = "—"
        pnl = "—"
        gap = f"{row.gap_pct:+.2f}%" if row.gap_pct is not None else "—"
        move = f"{row.close_move_pct:+.2f}%" if row.close_move_pct is not None else "—"
        lines.append(
            f"| {row.symbol} {row.fiscal_label} {row.announce_date} AMC "
            f"| {row.entry_date} (T−{row.days_before}) "
            f"| {iv} "
            f"| {row.structure} "
            f"| {entry} "
            f"| {gap} "
            f"| {move} "
            f"| {row.exit_rule} "
            f"| {pnl} "
            f"| `{row.fill_status}` |"
        )
    lines.extend(
        [
            "",
            "## 路径，不是盈亏",
            "",
            "跳空只是开盘。有的日子开盘不远，当天走出更大的幅度（例如 2025-02-26 跳空 +2.8%，收盘 −8.5%）。",
            "短波动能不能拿住，要看整天高低，不是只看开盘缺口。",
            "",
            "| 事件 | 进场收盘 | 事件收盘 | 反应开/高/低/收 | vendor implied | 收盘是否超出 implied |",
            "| --- | ---: | ---: | --- | ---: | --- |",
        ]
    )
    for row in rows:
        note = next((c for c in contrast if c["event"] == row.event_key), {})
        path = (note.get("short_iron_condor") or {}).get("path")
        breached = path["close_beyond_implied"] if path else "n/a"
        implied = f"±{row.vendor_implied_move_pct}%" if row.vendor_implied_move_pct is not None else "missing"
        # recover reaction prints from notes is ugly; keep implied/breach only here
        lines.append(
            f"| {row.fiscal_label} {row.announce_date} "
            f"| — "
            f"| — "
            f"| gap {row.gap_pct:+.2f}% · close {row.close_move_pct:+.2f}% · "
            f"H {row.high_move_pct:+.2f}% / L {row.low_move_pct:+.2f}% "
            f"| {implied} "
            f"| {breached} |"
        )
    lines.extend(
        [
            "",
            "## 对照 sweep（同一段历史）",
            "",
            "买跨、买 call、什么都不做，必须和短铁秃鹰跑同一 6 次事件。",
            "没有买卖价就没有权利金数字。不要用中间价补。",
            "",
            "| 事件 | 短铁秃鹰 | 买跨 | 买 call | 什么都不做 |",
            "| --- | --- | --- | --- | ---: |",
        ]
    )
    for item in contrast:
        lines.append(
            f"| {item['event']} "
            f"| {item['short_iron_condor']['status']} "
            f"| {item['long_straddle']['status']} "
            f"| {item['long_call']['status']} "
            f"| {item['do_nothing']['pnl_usd']} |"
        )
    lines.extend(
        [
            "",
            "## 这一轮不能说的话",
            "",
            "- 不能说「每笔赚 20%」。连一笔费后往返都还没记上。",
            "- 不能把 vendor crush 赢率当成 playbook 已验证。",
            "- 不能把 BTCHOUR 小时盘 clip 达成标准搬过来。",
            "",
            "下一步：有人把当时链上的买卖价记进账本，状态变成 `human` 或 `recorded_bid_ask` 之后，才写循环。",
            "",
        ]
    )
    return "\n".join(lines) + "\n"