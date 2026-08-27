from __future__ import annotations

from datetime import date, datetime

from kop.models import Occ, Right


def parse_occ(symbol: str) -> Occ:
    compact = symbol.replace(" ", "").upper()
    if len(compact) < 16:
        raise ValueError(f"not an OCC symbol: {symbol}")
    root, rest = compact[:-15], compact[-15:]
    if rest[6] not in {"C", "P"}:
        raise ValueError(f"bad OCC right: {symbol}")
    expiration = datetime.strptime(rest[:6], "%y%m%d").date()
    strike = int(rest[7:]) / 1000.0
    return Occ(root=root, expiration=expiration, right=rest[6], strike=strike, symbol=compact)


def format_occ(root: str, expiration: date, right: Right, strike: float) -> str:
    yymmdd = expiration.strftime("%y%m%d")
    strike_int = int(round(strike * 1000))
    return f"{root.upper()}{yymmdd}{right}{strike_int:08d}"
