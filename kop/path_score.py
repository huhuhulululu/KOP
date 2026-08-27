"""Score recipes on the spot path. Not a fill. Not a dollar P&L.

Public method: place theoretical shorts at ±k × implied move from the
pre-event close, then ask whether the reaction high/low stayed inside.
When a vendor implied is missing, use the leave-one-out median of the
other events' absolute close moves and label the strike source.
"""

from __future__ import annotations

from kop.config import WING_WIDTH_USD
from kop.models import TapeRow
from kop.recipes import Recipe, allowed_paper


def median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def implied_for_row(row: TapeRow, peers: list[TapeRow]) -> tuple[float | None, str]:
    if row.vendor_implied_move_pct is not None:
        return row.vendor_implied_move_pct, "vendor_orats_proxy"
    others = [abs(peer.close_move_pct) for peer in peers if peer.close_move_pct is not None and peer.event_key != row.event_key]
    fallback = median(others)
    if fallback is None:
        return None, "missing"
    return fallback, "loo_realized_median"


def _range(event_close: float, implied_pct: float, k: float, width_usd: float) -> tuple[float, float, float, float]:
    short_put = event_close * (1.0 - k * implied_pct / 100.0)
    short_call = event_close * (1.0 + k * implied_pct / 100.0)
    return short_put - width_usd, short_put, short_call, short_call + width_usd


def _band(low: float, high: float, long_put: float, short_put: float, short_call: float, long_call: float) -> str:
    if low >= short_put and high <= short_call:
        return "inside"
    if low <= long_put or high >= long_call:
        return "beyond_wing"
    return "in_wing"


def score_recipe(
    recipe: Recipe,
    row: TapeRow,
    *,
    implied_pct: float | None,
    k: float = 1.0,
    width_usd: float = WING_WIDTH_USD,
) -> dict:
    if row.event_close is None or row.reaction_high is None or row.reaction_low is None or row.reaction_close is None:
        return {"recipe": recipe.id, "status": "unscored_missing_path"}
    close_move = row.close_move_pct
    gap = row.gap_pct
    if recipe.id == "do_nothing":
        return {"recipe": recipe.id, "status": "scored", "path_outcome": "flat", "thesis": "control", "pnl_usd": 0.0}
    if recipe.risk == "undefined" or not recipe.paper_allowed:
        return {"recipe": recipe.id, "status": "forbidden", "path_outcome": None}
    if recipe.hold_through_event is False:
        return {
            "recipe": recipe.id,
            "status": "unscored_needs_iv_path",
            "note": "expansion recipes exit before the print; daily bars cannot score them",
        }
    if implied_pct is None and recipe.family in {"vol", "vertical", "calendar"}:
        return {"recipe": recipe.id, "status": "unscored_missing_implied"}

    event_close = row.event_close
    high, low = row.reaction_high, row.reaction_low
    if recipe.id == "short_iron_condor":
        long_put, short_put, short_call, long_call = _range(event_close, implied_pct or 0.0, k, width_usd)
        band = _band(low, high, long_put, short_put, short_call, long_call)
        return {
            "recipe": recipe.id,
            "status": "path_scored",
            "path_outcome": band,
            "thesis": "helped" if band == "inside" else "hurt",
            "shorts": {"put": short_put, "call": short_call},
            "wings": {"put": long_put, "call": long_call},
        }
    if recipe.id == "short_iron_fly":
        width = (implied_pct or 0.0) / 100.0 * event_close
        long_put, long_call = event_close - width, event_close + width
        if low <= long_put or high >= long_call:
            band = "beyond_wing"
            thesis = "hurt"
        elif close_move is not None and implied_pct and abs(close_move) < 0.25 * implied_pct:
            band = "pin"
            thesis = "helped"
        else:
            band = "tested_atm_shorts"
            thesis = "hurt"
        return {"recipe": recipe.id, "status": "path_scored", "path_outcome": band, "thesis": thesis}
    if recipe.id == "put_credit_spread":
        short_put = event_close * (1.0 - (implied_pct or 0.0) / 100.0)
        long_put = short_put - width_usd
        if low >= short_put:
            band = "inside"
        elif low <= long_put:
            band = "beyond_wing"
        else:
            band = "in_wing"
        return {"recipe": recipe.id, "status": "path_scored", "path_outcome": band, "thesis": "helped" if band == "inside" else "hurt"}
    if recipe.id == "call_credit_spread":
        short_call = event_close * (1.0 + (implied_pct or 0.0) / 100.0)
        long_call = short_call + width_usd
        if high <= short_call:
            band = "inside"
        elif high >= long_call:
            band = "beyond_wing"
        else:
            band = "in_wing"
        return {"recipe": recipe.id, "status": "path_scored", "path_outcome": band, "thesis": "helped" if band == "inside" else "hurt"}
    if recipe.id == "reverse_iron_condor":
        long_put, short_put, short_call, long_call = _range(event_close, implied_pct or 0.0, k, width_usd)
        band = _band(low, high, long_put, short_put, short_call, long_call)
        helped = band != "inside"
        return {"recipe": recipe.id, "status": "path_scored", "path_outcome": band, "thesis": "helped" if helped else "hurt"}
    if recipe.id in {"long_straddle", "long_strangle"}:
        beat = close_move is not None and implied_pct is not None and abs(close_move) > implied_pct
        return {
            "recipe": recipe.id,
            "status": "path_scored",
            "path_outcome": "realized_gt_implied" if beat else "realized_le_implied",
            "thesis": "helped" if beat else "hurt",
            "close_move_pct": close_move,
            "implied_pct": implied_pct,
        }
    if recipe.id == "long_call":
        up = close_move is not None and close_move > 0
        return {
            "recipe": recipe.id,
            "status": "path_scored",
            "path_outcome": "up_close" if up else "down_or_flat",
            "thesis": "direction_right_crush_unknown" if up else "direction_wrong",
            "note": "direction is not P&L; crush can still erase a correct call",
        }
    if recipe.id == "long_put":
        down = close_move is not None and close_move < 0
        return {
            "recipe": recipe.id,
            "status": "path_scored",
            "path_outcome": "down_close" if down else "up_or_flat",
            "thesis": "direction_right_crush_unknown" if down else "direction_wrong",
        }
    if recipe.id == "calendar_short_front":
        # calendars want the pin; a large gap is the known failure
        moved = close_move is not None and implied_pct is not None and abs(close_move) > 0.5 * implied_pct
        return {
            "recipe": recipe.id,
            "status": "path_scored",
            "path_outcome": "away_from_strike" if moved else "near_strike",
            "thesis": "hurt" if moved else "helped",
            "note": "proxy only; true calendar P&L needs two expiries",
        }
    if recipe.id == "broken_wing_butterfly":
        long_put, short_put, short_call, long_call = _range(event_close, implied_pct or 0.0, k, width_usd)
        band = _band(low, high, long_put, short_put, short_call, long_call)
        return {"recipe": recipe.id, "status": "path_scored", "path_outcome": band, "thesis": "helped" if band == "inside" else "hurt"}
    return {"recipe": recipe.id, "status": "unscored", "gap_pct": gap}


def score_event(row: TapeRow, peers: list[TapeRow], recipes: tuple[Recipe, ...] | None = None) -> dict:
    recipes = recipes or allowed_paper()
    implied, source = implied_for_row(row, peers)
    scores = [score_recipe(item, row, implied_pct=implied) for item in recipes]
    return {
        "event": row.event_key,
        "implied_pct": implied,
        "implied_source": source,
        "close_move_pct": row.close_move_pct,
        "gap_pct": row.gap_pct,
        "scores": scores,
    }
