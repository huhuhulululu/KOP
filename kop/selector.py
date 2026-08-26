"""Pick a recipe from public rules. No human clip required.

Rules (written down, not tuned after the fact):
- Strong event + no directional edge → never guess call/put.
- IV rank / range-rank < 50 → do not sell vol.
- Implied ≥ 1.2 × median |realized| of the tape window → short defined vol.
- Implied < 1.0 × median |realized| → defined long vol (reverse IC), not a naked long call.
- Implied near fair → stand down.
- Event day or T−1 → do not open a hold-through structure.
- Undefined risk (strangle, jade lizard) is never selected.
"""

from __future__ import annotations

from kop.config import IV_RANK_MIN
from kop.path_score import median
from kop.recipes import Recipe, recipe

RICH_IMPLIED_RATIO = 1.2
CHEAP_IMPLIED_RATIO = 1.0


def historical_median_abs(close_moves: list[float]) -> float | None:
    return median([abs(x) for x in close_moves])


def select_recipe(
    *,
    days_before: int | None,
    iv_rank: float | None,
    implied_move_pct: float | None,
    hist_abs_median: float | None,
    hold_through: bool = True,
) -> tuple[Recipe, str, dict]:
    details = {
        "days_before": days_before,
        "iv_rank": iv_rank,
        "implied_move_pct": implied_move_pct,
        "hist_abs_median": hist_abs_median,
        "rich_ratio": RICH_IMPLIED_RATIO,
        "iv_gate": IV_RANK_MIN,
    }
    if days_before is not None and days_before <= 1:
        chosen = recipe("do_nothing")
        return chosen, f"stand_down_too_close_t_minus_{days_before}", details
    ratio = None
    if implied_move_pct is not None and hist_abs_median and hist_abs_median > 0:
        ratio = implied_move_pct / hist_abs_median
    details["implied_over_hist"] = ratio

    if iv_rank is not None and iv_rank < IV_RANK_MIN:
        if ratio is not None and ratio < CHEAP_IMPLIED_RATIO and hold_through:
            chosen = recipe("reverse_iron_condor")
            return chosen, "implied_cheap_and_iv_not_rich_long_defined_vol", details
        chosen = recipe("do_nothing")
        return chosen, f"stand_down_iv_rank_{iv_rank:.1f}_below_{IV_RANK_MIN}", details

    if ratio is not None and ratio >= RICH_IMPLIED_RATIO:
        chosen = recipe("short_iron_condor")
        return chosen, f"short_defined_vol_implied_{ratio:.2f}x_hist", details
    if ratio is not None and ratio < CHEAP_IMPLIED_RATIO:
        chosen = recipe("reverse_iron_condor")
        return chosen, f"long_defined_vol_implied_{ratio:.2f}x_hist", details
    if ratio is None:
        chosen = recipe("do_nothing")
        return chosen, "stand_down_missing_implied_or_history", details
    chosen = recipe("do_nothing")
    return chosen, "stand_down_implied_near_fair", details
