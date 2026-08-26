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
from kop.path_score import score_event
from kop.playbook import entry_date_for, exit_date_for
from kop.recipes import allowed_paper
from kop.selector import historical_median_abs
from kop.selector import select_recipe


def _px(value: float | None) -> str:
    return f"{value:.2f}" if value is not None else "—"

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
        entry_close=path["entry_close"],
        event_close=path["event_close"],
        reaction_open=path["reaction_open"],
        reaction_high=path["reaction_high"],
        reaction_low=path["reaction_low"],
        reaction_close=path["reaction_close"],
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


def contrast_for_row(row: TapeRow, peers: list[TapeRow] | None = None) -> dict:
    """Same event, every paper-allowed recipe. Dollar P&L stays empty without quotes."""
    peers = peers or [row]
    scored = score_event(row, peers)
    by_id = {item["recipe"]: item for item in scored["scores"]}
    return {
        "event": row.event_key,
        "implied_pct": scored["implied_pct"],
        "implied_source": scored["implied_source"],
        "fills": "missing_quotes",
        "recipes": by_id,
        "do_nothing": {"variant": "do_nothing", "pnl_usd": 0.0, "status": "scored"},
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
    contrast = [contrast_for_row(row, rows) for row in rows]
    moves = [row.close_move_pct for row in rows if row.close_move_pct is not None]
    hist_med = historical_median_abs(moves)
    implieds = [c["implied_pct"] for c in contrast if c["implied_pct"] is not None]
    live_implied = implieds[-1] if implieds else None
    chosen, why, select_details = select_recipe(
        days_before=3,
        iv_rank=None,
        implied_move_pct=live_implied,
        hist_abs_median=hist_med,
    )
    payload = {
        "playbook": PLAYBOOK,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "countable_for_loop": store.countable_tape(),
        "credit_take_fraction": CREDIT_TAKE_FRACTION,
        "hist_abs_median": hist_med,
        "selector_on_tape": {"recipe": chosen.id, "reason": why, "details": select_details},
        "rows": [row.as_dict() for row in rows],
        "contrast": contrast,
    }
    json_path = RESEARCH_DIR / "nvda_earnings_tape.json"
    md_path = CATALOG_RESEARCH / "nvda_earnings_tape.md"
    sweep_path = CATALOG_RESEARCH / "nvda_recipe_sweep.md"
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(rows, payload["contrast"], store.countable_tape()), encoding="utf-8")
    sweep_path.write_text(render_recipe_sweep(rows, contrast, hist_med), encoding="utf-8")
    store.journal("research", "replay_written", symbol=SYMBOL, payload={"n": len(rows)})
    return {
        "json": str(json_path),
        "markdown": str(md_path),
        "sweep": str(sweep_path),
        "countable_tape": store.countable_tape(),
        "n": len(rows),
    }


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
        ic = (note.get("recipes") or {}).get("short_iron_condor") or {}
        breached = ic.get("path_outcome", "n/a")
        implied = f"±{note.get('implied_pct')}% ({note.get('implied_source')})" if note.get("implied_pct") is not None else "missing"
        # recover reaction prints from notes is ugly; keep implied/breach only here
        lines.append(
            f"| {row.fiscal_label} {row.announce_date} "
            f"| {_px(row.entry_close)} "
            f"| {_px(row.event_close)} "
            f"| O {_px(row.reaction_open)} / H {_px(row.reaction_high)} / "
            f"L {_px(row.reaction_low)} / C {_px(row.reaction_close)} "
            f"(gap {row.gap_pct:+.2f}% · close {row.close_move_pct:+.2f}%) "
            f"| {implied} "
            f"| {breached} |"
        )
    lines.extend(
        [
            "",
            "## 对照 sweep（同一段历史，公开配方）",
            "",
            "单腿 / 多腿必须和短铁秃鹰跑同一 6 次事件。没有买卖价就没有权利金数字。",
            "这里打的是**路径是否帮论文**，不是费后盈亏。完整表见 `nvda_recipe_sweep.md`。",
            "",
            "| 事件 | 短铁秃鹰 | 反向铁秃鹰 | 买跨 | 买 call | 什么都不做 |",
            "| --- | --- | --- | --- | --- | ---: |",
        ]
    )
    for item in contrast:
        rec = item.get("recipes") or {}
        lines.append(
            f"| {item['event']} "
            f"| {_thesis(rec.get('short_iron_condor'))} "
            f"| {_thesis(rec.get('reverse_iron_condor'))} "
            f"| {_thesis(rec.get('long_straddle'))} "
            f"| {_thesis(rec.get('long_call'))} "
            f"| 0 |"
        )
    lines.extend(
        [
            "",
            "## 这一轮不能说的话",
            "",
            "- 不能说「每笔赚 20%」。连一笔费后往返都还没记上。",
            "- 不能把路径「帮到论文」当成已验证成交。",
            "- 不要等人贴单。公开配方 + 回放就是带子。",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def _thesis(score: dict | None) -> str:
    if not score:
        return "—"
    return score.get("thesis") or score.get("path_outcome") or score.get("status") or "—"


def render_recipe_sweep(rows: list[TapeRow], contrast: list[dict], hist_med: float | None) -> str:
    names = [item.id for item in allowed_paper()]
    lines = [
        "# NVDA 公开配方路径 sweep",
        "",
        "不等人。同一 6 次财报，每条公开配方看反应日高低有没有打到理论短边。",
        "权利金仍空着。`helped` / `hurt` 是论文，不是美元。",
        f"历史 |收盘变动| 中位数：{hist_med:.2f}%。" if hist_med is not None else "历史中位数：missing",
        "",
        "| 事件 | implied | " + " | ".join(names) + " |",
        "| --- | --- | " + " | ".join(["---"] * len(names)) + " |",
    ]
    for item in contrast:
        rec = item.get("recipes") or {}
        cells = [_thesis(rec.get(name)) for name in names]
        implied = item.get("implied_pct")
        src = item.get("implied_source")
        lines.append(f"| {item['event']} | {implied} ({src}) | " + " | ".join(cells) + " |")
    lines.extend(["", "配方目录：`catalog/public/structures.md`。", ""])
    return "\n".join(lines) + "\n"