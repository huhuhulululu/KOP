"""Phase-1 income target. Arithmetic, not a promise.

$500/month is the scoreboard. The current NVDA earnings iron condor
cannot hit it: 4 prints a year, ~$129 max credit, path hit 2/6, breakeven
win rate ~74%. Scaling contracts into negative EV is refused.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from kop.config import (
    ALLOW_LIVE,
    AUTO_TRADE,
    CONTRACTS,
    EVENTS_PER_YEAR,
    MAX_LOSS_USD,
    MIN_COUNTABLE_TAPE_FOR_LIVE,
    MONTHLY_INCOME_TARGET_USD,
    PATH_HIT_MIN_EVENTS,
    PATH_HIT_RATE_MIN,
)
from kop.indicators import Snapshot


# Last live proposed IC on 2026-08-26 (bid/ask+$0.05, 1 lot). Not a fill.
DEFAULT_CREDIT_USD = 126.40  # max_gain after fees on that chain
DEFAULT_MAX_LOSS_USD = 373.60


@dataclass(frozen=True)
class Phase1:
    monthly_target_usd: float
    events_per_year: int
    contracts: int
    credit_usd: float
    max_loss_usd: float
    path_n: int
    path_hit_rate: float | None
    countable_tape: int
    realized_month_usd: float
    realized_all_usd: float

    @property
    def shots_per_month(self) -> float:
        return self.events_per_year / 12.0

    @property
    def breakeven_win_rate(self) -> float | None:
        denom = self.max_loss_usd + self.credit_usd
        if denom <= 0:
            return None
        return self.max_loss_usd / denom

    @property
    def ev_per_trade_usd(self) -> float | None:
        if self.path_hit_rate is None:
            return None
        return self.path_hit_rate * self.credit_usd - (1.0 - self.path_hit_rate) * self.max_loss_usd

    @property
    def ev_per_month_usd(self) -> float | None:
        ev = self.ev_per_trade_usd
        if ev is None:
            return None
        return ev * self.shots_per_month

    @property
    def max_month_if_never_lose_usd(self) -> float:
        return self.credit_usd * self.shots_per_month

    @property
    def contracts_to_hit_target_if_never_lose(self) -> float | None:
        per = self.max_month_if_never_lose_usd
        if per <= 0:
            return None
        return self.monthly_target_usd / per

    def scale_blockers(self) -> list[str]:
        out: list[str] = []
        if self.path_n < PATH_HIT_MIN_EVENTS:
            out.append(f"path_n_{self.path_n}_below_{PATH_HIT_MIN_EVENTS}")
        be = self.breakeven_win_rate
        if self.path_hit_rate is None:
            out.append("path_hit_rate_missing")
        elif be is not None and self.path_hit_rate < be:
            out.append(f"path_hit_{self.path_hit_rate:.2f}_below_breakeven_{be:.2f}")
        ev = self.ev_per_trade_usd
        if ev is not None and ev <= 0:
            out.append(f"ev_per_trade_{ev:.2f}_not_positive")
        if self.max_month_if_never_lose_usd + 1e-9 < self.monthly_target_usd:
            out.append(
                f"even_never_lose_{self.max_month_if_never_lose_usd:.2f}_below_target_{self.monthly_target_usd:.0f}"
            )
        return out

    def live_blockers(self) -> list[str]:
        out: list[str] = []
        if not ALLOW_LIVE:
            out.append("ALLOW_LIVE=false")
        if not AUTO_TRADE:
            out.append("AUTO_TRADE=false")
        if self.countable_tape < MIN_COUNTABLE_TAPE_FOR_LIVE:
            out.append(f"countable_tape_{self.countable_tape}_below_{MIN_COUNTABLE_TAPE_FOR_LIVE}")
        out.extend(self.scale_blockers())
        return out

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.update(
            {
                "shots_per_month": self.shots_per_month,
                "breakeven_win_rate": self.breakeven_win_rate,
                "ev_per_trade_usd": self.ev_per_trade_usd,
                "ev_per_month_usd": self.ev_per_month_usd,
                "max_month_if_never_lose_usd": self.max_month_if_never_lose_usd,
                "contracts_to_hit_target_if_never_lose": self.contracts_to_hit_target_if_never_lose,
                "month_gap_usd": self.monthly_target_usd - self.realized_month_usd,
                "can_hit_target_if_never_lose": self.max_month_if_never_lose_usd >= self.monthly_target_usd,
                "scale_blockers": self.scale_blockers(),
                "live_blockers": self.live_blockers(),
                "broker_orders": False,
                "note": (
                    "path_hit is path thesis, not dollar wins. "
                    "$500/month is the scoreboard, not a payout."
                ),
            }
        )
        return payload


def evaluate_phase1(
    *,
    snapshot: Snapshot | None = None,
    countable_tape: int = 0,
    realized_month_usd: float = 0.0,
    realized_all_usd: float = 0.0,
    credit_usd: float | None = None,
    max_loss_usd: float | None = None,
) -> Phase1:
    credit = credit_usd
    loss = max_loss_usd
    path_n = 0
    path_hit = None
    if snapshot is not None:
        path_n = snapshot.path_n
        path_hit = snapshot.path_hit_rate
        if snapshot.ic_max_loss_usd is not None:
            loss = snapshot.ic_max_loss_usd
        if snapshot.ic_net_credit is not None:
            # cash credit after the same fee convention as defined_risk max_gain
            credit = snapshot.ic_net_credit * 100.0 * CONTRACTS
            if snapshot.ic_max_loss_usd is not None and snapshot.ic_width:
                # max_gain = credit_cash - fees; recover from width identity if present
                credit = max(0.0, snapshot.ic_width * 100.0 * CONTRACTS - snapshot.ic_max_loss_usd)
    if credit is None:
        credit = DEFAULT_CREDIT_USD
    if loss is None:
        loss = DEFAULT_MAX_LOSS_USD
    return Phase1(
        monthly_target_usd=MONTHLY_INCOME_TARGET_USD,
        events_per_year=EVENTS_PER_YEAR,
        contracts=CONTRACTS,
        credit_usd=credit,
        max_loss_usd=min(loss, MAX_LOSS_USD) if loss else MAX_LOSS_USD,
        path_n=path_n,
        path_hit_rate=path_hit,
        countable_tape=countable_tape,
        realized_month_usd=realized_month_usd,
        realized_all_usd=realized_all_usd,
    )


def refuse_scale(phase: Phase1, want_contracts: int) -> str | None:
    if want_contracts <= CONTRACTS:
        return None
    blockers = phase.scale_blockers()
    if blockers:
        return "refuse_scale:" + ",".join(blockers)
    if PATH_HIT_RATE_MIN and (phase.path_hit_rate or 0) < PATH_HIT_RATE_MIN:
        return "refuse_scale:path_hit_below_gate"
    return None
