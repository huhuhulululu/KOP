"""Scoring helpers. Not a payout promise.

EV = p · b − (1 − p) can sit on a ticket as an expectation.
Settlement is still round-trip fills plus the path.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Edge:
    p: float
    b: float
    ev: float
    formula: str = "EV = p*b - (1-p)"

    def as_dict(self) -> dict:
        return {"p": self.p, "b": self.b, "ev": self.ev, "formula": self.formula}


def betting_ev(p: float, b: float) -> float:
    return p * b - (1.0 - p)


def edge(p: float, b: float) -> Edge:
    return Edge(p=p, b=b, ev=betting_ev(p, b))
