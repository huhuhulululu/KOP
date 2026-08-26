from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any, Literal

Right = Literal["C", "P"]
Side = Literal["buy", "sell"]
Session = Literal["amc", "bmo", "unknown"]
FillStatus = Literal["human", "recorded_bid_ask", "missing_quotes", "blocked"]


@dataclass(frozen=True)
class Occ:
    root: str
    expiration: date
    right: Right
    strike: float
    symbol: str

    @property
    def key(self) -> str:
        return self.symbol


@dataclass(frozen=True)
class OptionQuote:
    occ: Occ
    bid: float
    ask: float
    iv: float | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    volume: float | None = None
    open_interest: float | None = None
    bid_size: float | None = None
    ask_size: float | None = None

    @property
    def spread(self) -> float:
        return max(0.0, self.ask - self.bid)

    def has_market(self) -> bool:
        return self.bid > 0 and self.ask > 0 and self.ask >= self.bid


@dataclass(frozen=True)
class UnderlyingQuote:
    symbol: str
    last: float
    bid: float | None
    ask: float | None
    close: float
    asof: str
    iv30: float | None = None
    iv30_annual_high: float | None = None
    iv30_annual_low: float | None = None

    @property
    def spot(self) -> float:
        """RTH mark. After the bell, close beats a stale/AH last."""
        return self.close if self.close > 0 else self.last


@dataclass(frozen=True)
class Bar:
    day: date
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None


@dataclass(frozen=True)
class EarningsEvent:
    symbol: str
    announce_date: date
    session: Session
    fiscal_label: str
    source: str
    confirmed: bool = True

    @property
    def key(self) -> str:
        return f"{self.symbol}:{self.announce_date.isoformat()}:{self.session}"

    def reaction_index(self, days: list[date]) -> int:
        i = days.index(self.announce_date)
        if self.session == "bmo":
            return i
        return i + 1


@dataclass(frozen=True)
class LegFill:
    occ: Occ
    side: Side
    quantity: int
    bid: float
    ask: float
    fill_price: float
    slippage: float
    fee_usd: float
    quote_kind: str = "bid_ask"

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["occ"] = asdict(self.occ)
        payload["expiration"] = self.occ.expiration.isoformat()
        return payload


@dataclass(frozen=True)
class StructureFill:
    name: str
    expiration: date
    credit: bool
    net_premium: float
    max_loss_usd: float
    max_gain_usd: float
    fees_usd: float
    slippage_usd: float
    legs: tuple[LegFill, ...]
    quote_kind: str = "bid_ask"

    @property
    def debit_or_credit(self) -> str:
        return "credit" if self.credit else "debit"


@dataclass(frozen=True)
class Decision:
    allow: bool
    reason: str
    playbook: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TapeRow:
    event_key: str
    symbol: str
    fiscal_label: str
    announce_date: date
    session: Session
    entry_date: date | None
    days_before: int | None
    entry_close: float | None
    event_close: float | None
    reaction_open: float | None
    reaction_high: float | None
    reaction_low: float | None
    reaction_close: float | None
    iv_rank: float | None
    iv_percentile: float | None
    iv_source: str
    structure: str
    strikes: dict[str, float] | None
    expiration: date | None
    entry_quote_kind: str
    entry_net: float | None
    gap_pct: float | None
    close_move_pct: float | None
    high_move_pct: float | None
    low_move_pct: float | None
    vendor_implied_move_pct: float | None
    vendor_iv_crush_pct: float | None
    vendor_source: str
    exit_rule: str
    exit_date: date | None
    exit_net: float | None
    fees_usd: float | None
    pnl_usd: float | None
    fill_status: FillStatus
    notes: str

    def as_dict(self) -> dict[str, Any]:
        out = asdict(self)
        for key in ("announce_date", "entry_date", "expiration", "exit_date"):
            value = out[key]
            out[key] = value.isoformat() if value else None
        return out
