"""Refuse BTCHOUR / Kalshi / binary-contract leftovers.

This package must stay a listed-options book. Importing those names is a bug.
"""

from __future__ import annotations

import sys

FORBIDDEN_PREFIXES = (
    "btchour",
    "kalshi",
    "kxbtcd",
    "kxbtc",
    "polymarket",
)

FORBIDDEN_NAMES = {
    "impulse",
    "lock_wait",
    "dump_gap",
    "flex",
}


def imported_forbidden() -> list[str]:
    hits: list[str] = []
    for name in sys.modules:
        lowered = name.lower()
        if any(lowered == p or lowered.startswith(p + ".") for p in FORBIDDEN_PREFIXES):
            hits.append(name)
    return sorted(hits)


def assert_clean_process() -> None:
    hits = imported_forbidden()
    if hits:
        raise RuntimeError("forbidden modules loaded: " + ", ".join(hits))
