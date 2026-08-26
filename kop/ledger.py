from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kop.config import LEDGER_PATH
from kop.models import TapeRow

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    event_type TEXT NOT NULL,
    announce_date TEXT NOT NULL,
    session TEXT NOT NULL,
    fiscal_label TEXT,
    source TEXT NOT NULL,
    UNIQUE(symbol, event_type, announce_date)
);
CREATE TABLE IF NOT EXISTS tape_rows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    event_key TEXT NOT NULL,
    symbol TEXT NOT NULL,
    fiscal_label TEXT,
    announce_date TEXT NOT NULL,
    session TEXT NOT NULL,
    entry_date TEXT,
    days_before INTEGER,
    iv_rank REAL,
    iv_percentile REAL,
    iv_source TEXT,
    structure TEXT,
    strikes_json TEXT,
    expiration TEXT,
    entry_quote_kind TEXT,
    entry_net REAL,
    gap_pct REAL,
    close_move_pct REAL,
    high_move_pct REAL,
    low_move_pct REAL,
    vendor_implied_move_pct REAL,
    vendor_iv_crush_pct REAL,
    vendor_source TEXT,
    exit_rule TEXT,
    exit_date TEXT,
    exit_net REAL,
    fees_usd REAL,
    pnl_usd REAL,
    fill_status TEXT NOT NULL,
    notes TEXT,
    UNIQUE(event_key, structure, fill_status)
);
CREATE TABLE IF NOT EXISTS journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    kind TEXT NOT NULL,
    symbol TEXT,
    event_key TEXT,
    reason TEXT NOT NULL,
    payload TEXT
);
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    playbook TEXT NOT NULL,
    symbol TEXT NOT NULL,
    event_key TEXT,
    structure TEXT NOT NULL,
    expiration TEXT,
    max_loss_usd REAL NOT NULL,
    credit_usd REAL,
    status TEXT NOT NULL,
    entry_reason TEXT,
    exit_reason TEXT,
    pnl_usd REAL,
    legs_json TEXT
);
CREATE TABLE IF NOT EXISTS fills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id INTEGER,
    created_at TEXT NOT NULL,
    occ_symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    bid REAL NOT NULL,
    ask REAL NOT NULL,
    fill_price REAL NOT NULL,
    slippage REAL NOT NULL,
    fee_usd REAL NOT NULL,
    multiplier INTEGER NOT NULL,
    quote_kind TEXT NOT NULL,
    reason TEXT
);
CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    symbol TEXT NOT NULL,
    spot REAL,
    iv30 REAL,
    payload TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: Path | None = None):
        self.path = path or LEDGER_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.name.lower() == "btchour.sqlite":
            raise RuntimeError("refusing to open BTCHOUR sqlite")
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def record_event(self, symbol: str, announce_date: str, session: str, fiscal_label: str, source: str) -> None:
        self.conn.execute(
            """
            INSERT OR IGNORE INTO events (symbol, event_type, announce_date, session, fiscal_label, source)
            VALUES (?, 'earnings', ?, ?, ?, ?)
            """,
            (symbol, announce_date, session, fiscal_label, source),
        )
        self.conn.commit()

    def upsert_tape(self, row: TapeRow) -> None:
        payload = row.as_dict()
        self.conn.execute(
            """
            INSERT INTO tape_rows (
                created_at, event_key, symbol, fiscal_label, announce_date, session,
                entry_date, days_before, iv_rank, iv_percentile, iv_source, structure,
                strikes_json, expiration, entry_quote_kind, entry_net, gap_pct,
                close_move_pct, high_move_pct, low_move_pct, vendor_implied_move_pct,
                vendor_iv_crush_pct, vendor_source, exit_rule, exit_date, exit_net,
                fees_usd, pnl_usd, fill_status, notes
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(event_key, structure, fill_status) DO UPDATE SET
                notes=excluded.notes,
                gap_pct=excluded.gap_pct,
                close_move_pct=excluded.close_move_pct,
                high_move_pct=excluded.high_move_pct,
                low_move_pct=excluded.low_move_pct,
                vendor_implied_move_pct=excluded.vendor_implied_move_pct,
                vendor_iv_crush_pct=excluded.vendor_iv_crush_pct
            """,
            (
                _now(),
                payload["event_key"],
                payload["symbol"],
                payload["fiscal_label"],
                payload["announce_date"],
                payload["session"],
                payload["entry_date"],
                payload["days_before"],
                payload["iv_rank"],
                payload["iv_percentile"],
                payload["iv_source"],
                payload["structure"],
                json.dumps(payload["strikes"]),
                payload["expiration"],
                payload["entry_quote_kind"],
                payload["entry_net"],
                payload["gap_pct"],
                payload["close_move_pct"],
                payload["high_move_pct"],
                payload["low_move_pct"],
                payload["vendor_implied_move_pct"],
                payload["vendor_iv_crush_pct"],
                payload["vendor_source"],
                payload["exit_rule"],
                payload["exit_date"],
                payload["exit_net"],
                payload["fees_usd"],
                payload["pnl_usd"],
                payload["fill_status"],
                payload["notes"],
            ),
        )
        self.conn.commit()

    def tape_rows(self) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM tape_rows ORDER BY announce_date, id"))

    def countable_tape(self) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) FROM tape_rows WHERE fill_status IN ('human', 'recorded_bid_ask')"
        ).fetchone()
        return int(row[0])

    def journal(self, kind: str, reason: str, symbol: str | None = None, event_key: str | None = None, payload: dict[str, Any] | None = None) -> None:
        self.conn.execute(
            "INSERT INTO journal (created_at, kind, symbol, event_key, reason, payload) VALUES (?,?,?,?,?,?)",
            (_now(), kind, symbol, event_key, reason, json.dumps(payload or {})),
        )
        self.conn.commit()

    def recent_journal(self, limit: int = 20) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM journal ORDER BY id DESC LIMIT ?", (limit,)))

    def record_observation(self, symbol: str, spot: float | None, iv30: float | None, payload: dict[str, Any]) -> None:
        self.conn.execute(
            "INSERT INTO observations (created_at, symbol, spot, iv30, payload) VALUES (?,?,?,?,?)",
            (_now(), symbol, spot, iv30, json.dumps(payload)),
        )
        self.conn.commit()

    def iv30_history(self, symbol: str) -> list[float]:
        rows = self.conn.execute(
            "SELECT iv30 FROM observations WHERE symbol = ? AND iv30 IS NOT NULL ORDER BY id",
            (symbol,),
        ).fetchall()
        return [float(row["iv30"]) for row in rows]

    def summary(self) -> dict[str, Any]:
        tape_n = self.conn.execute("SELECT COUNT(*) FROM tape_rows").fetchone()[0]
        countable = self.countable_tape()
        journal_n = self.conn.execute("SELECT COUNT(*) FROM journal").fetchone()[0]
        obs_n = self.conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
        return {
            "ledger": str(self.path),
            "tape_rows": tape_n,
            "countable_tape": countable,
            "journal": journal_n,
            "observations": obs_n,
        }
