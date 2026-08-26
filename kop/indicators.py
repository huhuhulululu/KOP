"""Live snapshot. Every number is GATE or INFO. Missing required input = closed."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

from kop.config import (
    ATM_OI_MIN,
    ATM_STRADDLE_SPREAD_MAX,
    BACK_DTE_MAX,
    BACK_DTE_MIN,
    ENTRY_DAYS_BEFORE,
    FRONT_DTE_MAX,
    HV_FAST_WINDOW,
    HV_SLOW_WINDOW,
    IC_CREDIT_OVER_WIDTH_MIN,
    IV_RANK_MIN,
    LONG_VOL_IMPLIED_OVER_HIST_MAX,
    MAX_LOSS_USD,
    PATH_HIT_MIN_EVENTS,
    PATH_HIT_RATE_MIN,
    RR_DELTA_TARGET,
    RR_DELTA_TOLERANCE,
    SHORT_VOL_IMPLIED_OVER_HIST_MIN,
    TERM_SLOPE_VOL_MIN,
    VRP_IV30_OVER_HV20_MIN,
    WING_WIDTH_USD,
)
from kop.market.iv import atm_quotes, iv30_range_rank, straddle_implied_move_pct
from kop.models import Bar, EarningsEvent, OptionQuote, TapeRow, UnderlyingQuote
from kop.paper.risk import pick_expiration, select_iron_condor
from kop.path_score import median, score_event


@dataclass(frozen=True)
class GateRow:
    name: str
    value: float | int | str | None
    threshold: str
    used_as: str
    result: str
    source: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Snapshot:
    asof: date
    under: str
    event_date: date | None
    days_before: int | None
    spot: float
    iv30: float | None
    iv_range_rank: float | None
    iv_percentile: float | None
    hv20: float | None
    hv60: float | None
    vrp_iv30_over_hv20: float | None
    implied_move_sell_pct: float | None
    implied_move_buy_pct: float | None
    hist_abs_close_median: float | None
    implied_over_hist: float | None
    term_slope_vol: float | None
    front_atm_iv: float | None
    back_atm_iv: float | None
    front_expiry: date | None
    back_expiry: date | None
    risk_reversal_25d: float | None
    atm_straddle_spread_pct: float | None
    atm_oi: float | None
    event_week_oi: float | None
    event_week_volume: float | None
    ic_net_credit: float | None
    ic_width: float | None
    ic_credit_over_width: float | None
    ic_max_loss_usd: float | None
    path_n: int
    path_hit_rate: float | None
    reverse_path_n: int
    reverse_path_hit_rate: float | None
    vix: float | None
    vix_1y_percentile: float | None
    vix9d: float | None
    vix3m: float | None
    iv_source: str
    implied_source: str
    paid_configured: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["asof"] = self.asof.isoformat()
        out["event_date"] = self.event_date.isoformat() if self.event_date else None
        out["front_expiry"] = self.front_expiry.isoformat() if self.front_expiry else None
        out["back_expiry"] = self.back_expiry.isoformat() if self.back_expiry else None
        return out

    def window_blockers(self) -> list[str]:
        low, high = ENTRY_DAYS_BEFORE
        if self.days_before is None:
            return ["days_before_unknown"]
        if self.days_before <= 1:
            return [f"stand_down_too_close_t_minus_{self.days_before}"]
        if self.days_before < low or self.days_before > high:
            return [f"outside_entry_window_{self.days_before}d"]
        return []

    def short_vol_blockers(self) -> list[str]:
        out = list(self.window_blockers())
        out.extend(_require(self.implied_over_hist, "implied_over_hist", SHORT_VOL_IMPLIED_OVER_HIST_MIN, "ge"))
        out.extend(_require(self.iv_range_rank if self.iv_percentile is None else self.iv_percentile, "iv_rank", IV_RANK_MIN, "ge"))
        out.extend(_require(self.vrp_iv30_over_hv20, "vrp_iv30_over_hv20", VRP_IV30_OVER_HV20_MIN, "ge"))
        out.extend(_require(self.term_slope_vol, "term_slope_vol", TERM_SLOPE_VOL_MIN, "ge"))
        out.extend(_require(self.atm_straddle_spread_pct, "atm_straddle_spread_pct", ATM_STRADDLE_SPREAD_MAX, "le"))
        out.extend(_require(self.ic_credit_over_width, "ic_credit_over_width", IC_CREDIT_OVER_WIDTH_MIN, "ge"))
        out.extend(_require(self.ic_max_loss_usd, "ic_max_loss_usd", MAX_LOSS_USD, "le"))
        out.extend(_require(self.atm_oi, "atm_oi", ATM_OI_MIN, "ge"))
        out.extend(self._path_blockers(self.path_n, self.path_hit_rate, "path_hit_rate"))
        return out

    def long_vol_blockers(self) -> list[str]:
        out = list(self.window_blockers())
        if self.implied_over_hist is None:
            out.append("implied_over_hist_missing")
        elif self.implied_over_hist >= LONG_VOL_IMPLIED_OVER_HIST_MAX:
            out.append(
                f"implied_over_hist_{self.implied_over_hist:.2f}_not_cheap_need_lt_{LONG_VOL_IMPLIED_OVER_HIST_MAX}"
            )
        out.extend(_require(self.atm_straddle_spread_pct, "atm_straddle_spread_pct", ATM_STRADDLE_SPREAD_MAX, "le"))
        out.extend(_require(self.atm_oi, "atm_oi", ATM_OI_MIN, "ge"))
        out.extend(self._path_blockers(self.reverse_path_n, self.reverse_path_hit_rate, "reverse_path_hit_rate"))
        return out

    def _path_blockers(self, n: int, rate: float | None, name: str) -> list[str]:
        if n < PATH_HIT_MIN_EVENTS:
            return [f"{name}_n_{n}_below_{PATH_HIT_MIN_EVENTS}"]
        return _require(rate, name, PATH_HIT_RATE_MIN, "ge")

    def gate_table(self) -> list[GateRow]:
        iv_value = self.iv_percentile if self.iv_percentile is not None else self.iv_range_rank
        iv_name = "iv_percentile" if self.iv_percentile is not None else "iv30_range_rank"
        rows = [
            GateRow("days_before", self.days_before, f"in {ENTRY_DAYS_BEFORE[0]}–{ENTRY_DAYS_BEFORE[1]}", "GATE", _window_result(self.days_before), "session calendar"),
            GateRow("implied_over_hist", _round(self.implied_over_hist), f">= {SHORT_VOL_IMPLIED_OVER_HIST_MIN} short / < {LONG_VOL_IMPLIED_OVER_HIST_MAX} long", "GATE", _cmp(self.implied_over_hist, SHORT_VOL_IMPLIED_OVER_HIST_MIN, "ge"), f"{self.implied_source} / tape |close| median"),
            GateRow(iv_name, _round(iv_value), f">= {IV_RANK_MIN}", "GATE", _cmp(iv_value, IV_RANK_MIN, "ge"), self.iv_source),
            GateRow("vrp_iv30_over_hv20", _round(self.vrp_iv30_over_hv20), f">= {VRP_IV30_OVER_HV20_MIN}", "GATE", _cmp(self.vrp_iv30_over_hv20, VRP_IV30_OVER_HV20_MIN, "ge"), "CBOE iv30 / Yahoo HV20"),
            GateRow("term_slope_vol", _round(self.term_slope_vol), f">= {TERM_SLOPE_VOL_MIN} vol pts (front−back ATM IV)", "GATE", _cmp(self.term_slope_vol, TERM_SLOPE_VOL_MIN, "ge"), "CBOE chain"),
            GateRow("atm_straddle_spread_pct", _round(self.atm_straddle_spread_pct), f"<= {ATM_STRADDLE_SPREAD_MAX}", "GATE", _cmp(self.atm_straddle_spread_pct, ATM_STRADDLE_SPREAD_MAX, "le"), "CBOE ATM bid/ask"),
            GateRow("ic_credit_over_width", _round(self.ic_credit_over_width), f">= {IC_CREDIT_OVER_WIDTH_MIN} after bid/ask+slip", "GATE", _cmp(self.ic_credit_over_width, IC_CREDIT_OVER_WIDTH_MIN, "ge"), "CBOE proposed IC"),
            GateRow("ic_max_loss_usd", _round(self.ic_max_loss_usd), f"<= {MAX_LOSS_USD}", "GATE", _cmp(self.ic_max_loss_usd, MAX_LOSS_USD, "le"), "width − credit + fees"),
            GateRow("atm_oi", self.atm_oi, f">= {ATM_OI_MIN}", "GATE", _cmp(self.atm_oi, ATM_OI_MIN, "ge"), "CBOE open interest"),
            GateRow("path_hit_rate", _round(self.path_hit_rate), f">= {PATH_HIT_RATE_MIN} on n>={PATH_HIT_MIN_EVENTS} (short IC helped)", "GATE", _path_result(self.path_n, self.path_hit_rate), f"Yahoo path + {self.path_n} events"),
            GateRow("reverse_path_hit_rate", _round(self.reverse_path_hit_rate), f">= {PATH_HIT_RATE_MIN} on n>={PATH_HIT_MIN_EVENTS} (reverse IC helped)", "GATE", _path_result(self.reverse_path_n, self.reverse_path_hit_rate), f"Yahoo path + {self.reverse_path_n} events"),
            GateRow("hv20", _round(self.hv20), "input to VRP", "INPUT", "computed" if self.hv20 is not None else "missing", "Yahoo daily log-return * sqrt(252)"),
            GateRow("hv60", _round(self.hv60), "background", "INFO", "informational", "Yahoo daily"),
            GateRow("vix", _round(self.vix), "not a single-name gate", "INFO", "informational", "CBOE delayed _VIX"),
            GateRow("vix_1y_percentile", _round(self.vix_1y_percentile), "not a single-name gate", "INFO", "informational", "FRED VIXCLS"),
            GateRow("risk_reversal_25d", _round(self.risk_reversal_25d), "put IV − call IV; not a gate", "INFO", "informational", "CBOE 25Δ"),
            GateRow("event_week_oi", self.event_week_oi, "background liquidity", "INFO", "informational", "CBOE"),
            GateRow("paid_historical_bid_ask", ",".join(self.paid_configured) or "none", "needed for dollar tape, not live gates", "INFO", "configured" if self.paid_configured else "no_key", "Polygon/Tradier env"),
        ]
        return rows


def historical_median_abs_moves(close_moves: list[float]) -> float | None:
    return median([abs(x) for x in close_moves])


def realized_vol_pct(closes: list[float], window: int) -> float | None:
    if window < 2 or len(closes) < window + 1:
        return None
    series = closes[-(window + 1) :]
    rets: list[float] = []
    for i in range(1, len(series)):
        prev, cur = series[i - 1], series[i]
        if prev <= 0 or cur <= 0:
            return None
        rets.append(math.log(cur / prev))
    if len(rets) < window:
        return None
    mean = sum(rets) / len(rets)
    var = sum((item - mean) ** 2 for item in rets) / (len(rets) - 1)
    if var < 0:
        return None
    return math.sqrt(var) * math.sqrt(252.0) * 100.0


def path_stats(rows: list[TapeRow]) -> dict[str, Any]:
    ic_n = ic_hit = rev_n = rev_hit = 0
    for row in rows:
        scored = score_event(row, rows)
        by_id = {item["recipe"]: item for item in scored["scores"]}
        ic = by_id.get("short_iron_condor") or {}
        if ic.get("status") == "path_scored" and ic.get("thesis") in {"helped", "hurt"}:
            ic_n += 1
            if ic["thesis"] == "helped":
                ic_hit += 1
        rev = by_id.get("reverse_iron_condor") or {}
        if rev.get("status") == "path_scored" and rev.get("thesis") in {"helped", "hurt"}:
            rev_n += 1
            if rev["thesis"] == "helped":
                rev_hit += 1
    moves = [row.close_move_pct for row in rows if row.close_move_pct is not None]
    return {
        "path_n": ic_n,
        "path_hit_rate": (ic_hit / ic_n) if ic_n else None,
        "reverse_path_n": rev_n,
        "reverse_path_hit_rate": (rev_hit / rev_n) if rev_n else None,
        "hist_abs_close_median": historical_median_abs_moves(moves),
        "close_moves": moves,
    }


def build_snapshot(
    *,
    asof: date,
    under: UnderlyingQuote,
    quotes: list[OptionQuote],
    bars: list[Bar],
    event: EarningsEvent | None,
    tape_rows: list[TapeRow],
    days_before: int | None,
    iv_percentile: float | None = None,
    vix: float | None = None,
    vix_1y_percentile: float | None = None,
    vix9d: float | None = None,
    vix3m: float | None = None,
    paid_configured: tuple[str, ...] = (),
) -> Snapshot:
    spot = under.spot
    range_rank = iv30_range_rank(under)
    iv_source = "cboe_iv30_range_rank"
    if iv_percentile is not None:
        iv_source = "ledger_iv30_percentile"
    closes = [bar.close for bar in bars if bar.day <= asof]
    hv20 = realized_vol_pct(closes, HV_FAST_WINDOW)
    hv60 = realized_vol_pct(closes, HV_SLOW_WINDOW)
    vrp = (under.iv30 / hv20) if under.iv30 and hv20 and hv20 > 0 else None

    front_exp = _front_expiry(quotes, asof)
    back_exp = _back_expiry(quotes, asof)
    front_pair = atm_quotes(quotes, front_exp, spot) if front_exp else None
    back_pair = atm_quotes(quotes, back_exp, spot) if back_exp else None
    sell_move = buy_move = spread_pct = atm_oi = None
    front_iv = back_iv = term = rr = None
    implied_source = "missing"
    if front_pair:
        call, put = front_pair
        sell_move = straddle_implied_move_pct(call, put, spot, side="sell")
        buy_move = straddle_implied_move_pct(call, put, spot, side="buy")
        if sell_move is not None:
            implied_source = "cboe_front_straddle_bid"
        bid = call.bid + put.bid
        ask = call.ask + put.ask
        if bid > 0:
            spread_pct = (ask - bid) / bid
        atm_oi = (call.open_interest or 0.0) + (put.open_interest or 0.0)
        if call.iv is not None and put.iv is not None:
            front_iv = (call.iv + put.iv) / 2.0
    if back_pair and back_pair[0].iv is not None and back_pair[1].iv is not None:
        back_iv = (back_pair[0].iv + back_pair[1].iv) / 2.0
    if front_iv is not None and back_iv is not None:
        term = front_iv - back_iv
    if front_exp:
        rr = _risk_reversal(quotes, front_exp)

    stats = path_stats(tape_rows)
    hist = stats["hist_abs_close_median"]
    ratio = (sell_move / hist) if sell_move is not None and hist and hist > 0 else None

    ic_credit = ic_width = ic_ratio = ic_loss = None
    if front_exp:
        try:
            fill = select_iron_condor(quotes, spot, front_exp)
            ic_credit = fill.net_premium
            ic_width = WING_WIDTH_USD
            ic_ratio = fill.net_premium / WING_WIDTH_USD if WING_WIDTH_USD else None
            ic_loss = fill.max_loss_usd
        except Exception:
            pass

    week_oi = week_vol = None
    if front_exp:
        week = [q for q in quotes if q.occ.expiration == front_exp]
        week_oi = sum(q.open_interest or 0.0 for q in week)
        week_vol = sum(q.volume or 0.0 for q in week)

    missing: list[str] = []
    for name, value in (
        ("days_before", days_before),
        ("implied_move_sell_pct", sell_move),
        ("hist_abs_close_median", hist),
        ("iv_rank", iv_percentile if iv_percentile is not None else range_rank),
        ("hv20", hv20),
        ("vrp_iv30_over_hv20", vrp),
        ("term_slope_vol", term),
        ("atm_straddle_spread_pct", spread_pct),
        ("ic_credit_over_width", ic_ratio),
        ("atm_oi", atm_oi),
        ("path_hit_rate", stats["path_hit_rate"]),
    ):
        if value is None:
            missing.append(name)

    notes = [
        "VIX / VIX percentile do not gate single-name earnings short vol",
        "path_hit_rate is path thesis, not dollar P&L",
        "implied move uses straddle bid, never mid",
    ]
    if not paid_configured:
        notes.append("no paid historical bid/ask key; tape fills stay missing_quotes")

    return Snapshot(
        asof=asof,
        under=under.symbol,
        event_date=event.announce_date if event else None,
        days_before=days_before,
        spot=spot,
        iv30=under.iv30,
        iv_range_rank=range_rank,
        iv_percentile=iv_percentile,
        hv20=hv20,
        hv60=hv60,
        vrp_iv30_over_hv20=vrp,
        implied_move_sell_pct=sell_move,
        implied_move_buy_pct=buy_move,
        hist_abs_close_median=hist,
        implied_over_hist=ratio,
        term_slope_vol=term,
        front_atm_iv=front_iv,
        back_atm_iv=back_iv,
        front_expiry=front_exp,
        back_expiry=back_exp,
        risk_reversal_25d=rr,
        atm_straddle_spread_pct=spread_pct,
        atm_oi=atm_oi,
        event_week_oi=week_oi,
        event_week_volume=week_vol,
        ic_net_credit=ic_credit,
        ic_width=ic_width,
        ic_credit_over_width=ic_ratio,
        ic_max_loss_usd=ic_loss,
        path_n=int(stats["path_n"]),
        path_hit_rate=stats["path_hit_rate"],
        reverse_path_n=int(stats["reverse_path_n"]),
        reverse_path_hit_rate=stats["reverse_path_hit_rate"],
        vix=vix,
        vix_1y_percentile=vix_1y_percentile,
        vix9d=vix9d,
        vix3m=vix3m,
        iv_source=iv_source,
        implied_source=implied_source,
        paid_configured=paid_configured,
        missing=tuple(missing),
        notes=tuple(notes),
        extra={"hist_n": len(stats["close_moves"])},
    )


def sparse_snapshot(
    *,
    asof: date,
    under: str = "NVDA",
    event_date: date | None = None,
    days_before: int | None = None,
    **kwargs: Any,
) -> Snapshot:
    """Test / fallback constructor. Unset required fields stay None (fail-closed)."""
    base = dict(
        asof=asof,
        under=under,
        event_date=event_date,
        days_before=days_before,
        spot=float(kwargs.pop("spot", 0.0)),
        iv30=kwargs.pop("iv30", None),
        iv_range_rank=kwargs.pop("iv_range_rank", None),
        iv_percentile=kwargs.pop("iv_percentile", None),
        hv20=kwargs.pop("hv20", None),
        hv60=kwargs.pop("hv60", None),
        vrp_iv30_over_hv20=kwargs.pop("vrp_iv30_over_hv20", None),
        implied_move_sell_pct=kwargs.pop("implied_move_sell_pct", None),
        implied_move_buy_pct=kwargs.pop("implied_move_buy_pct", None),
        hist_abs_close_median=kwargs.pop("hist_abs_close_median", None),
        implied_over_hist=kwargs.pop("implied_over_hist", None),
        term_slope_vol=kwargs.pop("term_slope_vol", None),
        front_atm_iv=kwargs.pop("front_atm_iv", None),
        back_atm_iv=kwargs.pop("back_atm_iv", None),
        front_expiry=kwargs.pop("front_expiry", None),
        back_expiry=kwargs.pop("back_expiry", None),
        risk_reversal_25d=kwargs.pop("risk_reversal_25d", None),
        atm_straddle_spread_pct=kwargs.pop("atm_straddle_spread_pct", None),
        atm_oi=kwargs.pop("atm_oi", None),
        event_week_oi=kwargs.pop("event_week_oi", None),
        event_week_volume=kwargs.pop("event_week_volume", None),
        ic_net_credit=kwargs.pop("ic_net_credit", None),
        ic_width=kwargs.pop("ic_width", None),
        ic_credit_over_width=kwargs.pop("ic_credit_over_width", None),
        ic_max_loss_usd=kwargs.pop("ic_max_loss_usd", None),
        path_n=int(kwargs.pop("path_n", 0)),
        path_hit_rate=kwargs.pop("path_hit_rate", None),
        reverse_path_n=int(kwargs.pop("reverse_path_n", 0)),
        reverse_path_hit_rate=kwargs.pop("reverse_path_hit_rate", None),
        vix=kwargs.pop("vix", None),
        vix_1y_percentile=kwargs.pop("vix_1y_percentile", None),
        vix9d=kwargs.pop("vix9d", None),
        vix3m=kwargs.pop("vix3m", None),
        iv_source=str(kwargs.pop("iv_source", "test")),
        implied_source=str(kwargs.pop("implied_source", "test")),
        paid_configured=tuple(kwargs.pop("paid_configured", ())),
        missing=tuple(kwargs.pop("missing", ())),
        notes=tuple(kwargs.pop("notes", ())),
        extra=dict(kwargs.pop("extra", {})),
    )
    if kwargs:
        raise TypeError(f"unknown snapshot fields: {sorted(kwargs)}")
    return Snapshot(**base)


def passing_snapshot(*, asof: date = date(2026, 5, 15), **overrides: Any) -> Snapshot:
    fields = dict(
        asof=asof,
        under="NVDA",
        event_date=date(2026, 5, 20),
        days_before=5,
        spot=135.0,
        iv30=45.0,
        iv_range_rank=62.0,
        iv_percentile=None,
        hv20=35.0,
        hv60=38.0,
        vrp_iv30_over_hv20=1.28,
        implied_move_sell_pct=4.0,
        implied_move_buy_pct=4.2,
        hist_abs_close_median=3.2,
        implied_over_hist=1.25,
        term_slope_vol=25.0,
        front_atm_iv=70.0,
        back_atm_iv=45.0,
        front_expiry=date(2026, 5, 22),
        back_expiry=date(2026, 6, 19),
        risk_reversal_25d=1.0,
        atm_straddle_spread_pct=0.03,
        atm_oi=2000.0,
        event_week_oi=50000.0,
        event_week_volume=40000.0,
        ic_net_credit=1.50,
        ic_width=5.0,
        ic_credit_over_width=0.30,
        ic_max_loss_usd=372.6,
        path_n=6,
        path_hit_rate=0.50,
        reverse_path_n=6,
        reverse_path_hit_rate=0.50,
        vix=16.0,
        vix_1y_percentile=20.0,
        vix9d=14.0,
        vix3m=17.0,
        iv_source="cboe_iv30_range_rank",
        implied_source="cboe_front_straddle_bid",
        missing=(),
        notes=("test fixture",),
    )
    fields.update(overrides)
    return Snapshot(**fields)


def _front_expiry(quotes: list[OptionQuote], asof: date) -> date | None:
    picked = pick_expiration(quotes, asof)
    if picked is None:
        return None
    if (picked - asof).days > FRONT_DTE_MAX:
        return None
    return picked


def _back_expiry(quotes: list[OptionQuote], asof: date) -> date | None:
    expiries = sorted({q.occ.expiration for q in quotes if q.occ.expiration >= asof})
    window = [exp for exp in expiries if BACK_DTE_MIN <= (exp - asof).days <= BACK_DTE_MAX]
    if not window:
        return None
    return min(window, key=lambda exp: abs((exp - asof).days - 30))


def _risk_reversal(quotes: list[OptionQuote], expiry: date) -> float | None:
    calls = [q for q in quotes if q.occ.expiration == expiry and q.occ.right == "C" and q.iv is not None and q.delta is not None]
    puts = [q for q in quotes if q.occ.expiration == expiry and q.occ.right == "P" and q.iv is not None and q.delta is not None]
    if not calls or not puts:
        return None
    call = min(calls, key=lambda q: abs((q.delta or 0.0) - RR_DELTA_TARGET))
    put = min(puts, key=lambda q: abs((q.delta or 0.0) + RR_DELTA_TARGET))
    if abs((call.delta or 0.0) - RR_DELTA_TARGET) > RR_DELTA_TOLERANCE:
        return None
    if abs((put.delta or 0.0) + RR_DELTA_TARGET) > RR_DELTA_TOLERANCE:
        return None
    return put.iv - call.iv


def _require(value: float | None, name: str, threshold: float, op: str) -> list[str]:
    if value is None:
        return [f"{name}_missing"]
    if op == "ge" and value < threshold:
        return [f"{name}_{_fmt(value)}_below_{_fmt(threshold)}"]
    if op == "le" and value > threshold:
        return [f"{name}_{_fmt(value)}_above_{_fmt(threshold)}"]
    return []


def _cmp(value: float | None, threshold: float, op: str) -> str:
    if value is None:
        return "missing"
    if op == "ge":
        return "pass" if value >= threshold else "fail"
    return "pass" if value <= threshold else "fail"


def _path_result(n: int, rate: float | None) -> str:
    if n < PATH_HIT_MIN_EVENTS:
        return "fail"
    return _cmp(rate, PATH_HIT_RATE_MIN, "ge")


def _window_result(days_before: int | None) -> str:
    if days_before is None:
        return "missing"
    low, high = ENTRY_DAYS_BEFORE
    return "pass" if low <= days_before <= high else "fail"


def _round(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 4)


def _fmt(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}"


# imported by tests / research; keep median available without a new import path
__all__ = [
    "GateRow",
    "Snapshot",
    "build_snapshot",
    "historical_median_abs_moves",
    "passing_snapshot",
    "path_stats",
    "realized_vol_pct",
    "sparse_snapshot",
    "median",
]
