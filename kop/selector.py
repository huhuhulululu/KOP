"""Pick a recipe from a snapshot. No human clip. Missing gate input = stand down."""

from __future__ import annotations

from kop.config import (
    IV_RANK_MIN,
    LONG_VOL_IMPLIED_OVER_HIST_MAX,
    PATH_HIT_RATE_MIN,
    SHORT_VOL_IMPLIED_OVER_HIST_MIN,
)
from kop.indicators import Snapshot
from kop.path_score import median
from kop.recipes import Recipe, recipe


def historical_median_abs(close_moves: list[float]) -> float | None:
    return median([abs(x) for x in close_moves])


def select_recipe(snap: Snapshot) -> tuple[Recipe, str, dict]:
    details = {
        "days_before": snap.days_before,
        "iv_rank": snap.iv_percentile if snap.iv_percentile is not None else snap.iv_range_rank,
        "implied_move_pct": snap.implied_move_sell_pct,
        "hist_abs_median": snap.hist_abs_close_median,
        "implied_over_hist": snap.implied_over_hist,
        "rich_ratio": SHORT_VOL_IMPLIED_OVER_HIST_MIN,
        "cheap_ratio": LONG_VOL_IMPLIED_OVER_HIST_MAX,
        "iv_gate": IV_RANK_MIN,
        "path_hit_rate": snap.path_hit_rate,
        "path_n": snap.path_n,
        "path_hit_min": PATH_HIT_RATE_MIN,
        "short_vol_blockers": snap.short_vol_blockers(),
        "long_vol_blockers": snap.long_vol_blockers(),
        "missing": list(snap.missing),
        "implied_source": snap.implied_source,
        "iv_source": snap.iv_source,
        "vix_1y_percentile": snap.vix_1y_percentile,
        "note": "VIX percentile is informational and does not gate",
    }
    window = snap.window_blockers()
    if window:
        return recipe("do_nothing"), window[0], details
    short_blockers = details["short_vol_blockers"]
    if not short_blockers:
        ratio = snap.implied_over_hist if snap.implied_over_hist is not None else 0.0
        return recipe("short_iron_condor"), f"short_defined_vol_implied_{ratio:.2f}x_hist", details
    long_blockers = details["long_vol_blockers"]
    if not long_blockers:
        ratio = snap.implied_over_hist if snap.implied_over_hist is not None else 0.0
        return recipe("reverse_iron_condor"), f"long_defined_vol_implied_{ratio:.2f}x_hist", details
    if any(item.startswith("iv_rank") or item.startswith("iv30") for item in short_blockers):
        iv = details["iv_rank"]
        if iv is not None:
            return recipe("do_nothing"), f"stand_down_iv_rank_{iv:.1f}_below_{IV_RANK_MIN:g}", details
    if any(item.startswith("path_hit_rate") for item in short_blockers):
        rate = snap.path_hit_rate
        label = f"{rate:.2f}" if rate is not None else "missing"
        return recipe("do_nothing"), f"stand_down_path_hit_rate_{label}_below_{PATH_HIT_RATE_MIN}", details
    return recipe("do_nothing"), f"stand_down_{short_blockers[0]}", details
