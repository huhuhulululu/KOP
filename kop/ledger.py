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
    entry_close REAL,
    event_close REAL,
    reaction_open REAL,
    reaction_high REAL,
    reaction_low REAL,
    reaction_close REAL,
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
    legs_json TEXT,
    extra_json TEXT
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
CREATE TABLE IF NOT EXISTS marks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    position_id INTEGER NOT NULL,
    asof TEXT NOT NULL,
    close_debit REAL,
    mark_pnl_usd REAL,
    payload TEXT
);
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    asof TEXT NOT NULL,
    symbol TEXT NOT NULL,
    event_key TEXT,
    selected_recipe TEXT,
    select_reason TEXT,
    payload TEXT NOT NULL
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
        self._migrate()

    def _migrate(self) -> None:
        existing = {row[1] for row in self.conn.execute("PRAGMA table_info(tape_rows)")}
        extras = {
            "entry_close": "REAL",
            "event_close": "REAL",
            "reaction_open": "REAL",
            "reaction_high": "REAL",
            "reaction_low": "REAL",
            "reaction_close": "REAL",
        }
        for name, typ in extras.items():
            if name not in existing:
                self.conn.execute(f"ALTER TABLE tape_rows ADD COLUMN {name} {typ}")
        pos_cols = {row[1] for row in self.conn.execute("PRAGMA table_info(positions)")}
        if "extra_json" not in pos_cols:
            self.conn.execute("ALTER TABLE positions ADD COLUMN extra_json TEXT")
        self.conn.commit()

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
                entry_date, days_before, entry_close, event_close,
                reaction_open, reaction_high, reaction_low, reaction_close,
                iv_rank, iv_percentile, iv_source, structure,
                strikes_json, expiration, entry_quote_kind, entry_net, gap_pct,
                close_move_pct, high_move_pct, low_move_pct, vendor_implied_move_pct,
                vendor_iv_crush_pct, vendor_source, exit_rule, exit_date, exit_net,
                fees_usd, pnl_usd, fill_status, notes
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(event_key, structure, fill_status) DO UPDATE SET
                notes=excluded.notes,
                gap_pct=excluded.gap_pct,
                close_move_pct=excluded.close_move_pct,
                high_move_pct=excluded.high_move_pct,
                low_move_pct=excluded.low_move_pct,
                entry_close=excluded.entry_close,
                event_close=excluded.event_close,
                reaction_open=excluded.reaction_open,
                reaction_high=excluded.reaction_high,
                reaction_low=excluded.reaction_low,
                reaction_close=excluded.reaction_close,
                vendor_implied_move_pct=excluded.vendor_implied_move_pct,
                vendor_iv_crush_pct=excluded.vendor_iv_crush_pct,
                exit_date=excluded.exit_date,
                exit_net=excluded.exit_net,
                fees_usd=excluded.fees_usd,
                pnl_usd=excluded.pnl_usd
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
                payload["entry_close"],
                payload["event_close"],
                payload["reaction_open"],
                payload["reaction_high"],
                payload["reaction_low"],
                payload["reaction_close"],
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

    def record_snapshot(
        self,
        *,
        asof: str,
        symbol: str,
        event_key: str | None,
        selected_recipe: str | None,
        select_reason: str | None,
        payload: dict[str, Any],
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO snapshots (created_at, asof, symbol, event_key, selected_recipe, select_reason, payload)
            VALUES (?,?,?,?,?,?,?)
            """,
            (_now(), asof, symbol, event_key, selected_recipe, select_reason, json.dumps(payload, default=str)),
        )
        self.conn.commit()

    def latest_snapshot(self, symbol: str | None = None) -> sqlite3.Row | None:
        if symbol:
            return self.conn.execute(
                "SELECT * FROM snapshots WHERE symbol = ? ORDER BY id DESC LIMIT 1",
                (symbol,),
            ).fetchone()
        return self.conn.execute("SELECT * FROM snapshots ORDER BY id DESC LIMIT 1").fetchone()

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
        snap_n = self.conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
        return {
            "ledger": str(self.path),
            "tape_rows": tape_n,
            "countable_tape": countable,
            "journal": journal_n,
            "observations": obs_n,
            "snapshots": snap_n,
            "open_positions": self.open_position_count(),
            "realized_pnl_usd": self.realized_pnl(),
        }

    def insert_position(
        self,
        *,
        playbook: str,
        symbol: str,
        event_key: str | None,
        structure: str,
        expiration: str | None,
        max_loss_usd: float,
        credit_usd: float | None,
        status: str,
        entry_reason: str,
        legs_json: str,
        extra: dict[str, Any] | None = None,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO positions (
                created_at, playbook, symbol, event_key, structure, expiration,
                max_loss_usd, credit_usd, status, entry_reason, legs_json, extra_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                _now(),
                playbook,
                symbol,
                event_key,
                structure,
                expiration,
                max_loss_usd,
                credit_usd,
                status,
                entry_reason,
                legs_json,
                json.dumps(extra or {}),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def insert_fill(self, position_id: int, leg: Any, reason: str) -> None:
        self.conn.execute(
            """
            INSERT INTO fills (
                position_id, created_at, occ_symbol, side, quantity, bid, ask,
                fill_price, slippage, fee_usd, multiplier, quote_kind, reason
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                position_id,
                _now(),
                leg.occ.symbol,
                leg.side,
                leg.quantity,
                leg.bid,
                leg.ask,
                leg.fill_price,
                leg.slippage,
                leg.fee_usd,
                100,
                leg.quote_kind,
                reason,
            ),
        )
        self.conn.commit()

    def open_positions(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM positions WHERE status = 'open' ORDER BY id").fetchall()
        return [self._position_dict(row) for row in rows]

    def open_position_count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) FROM positions WHERE status = 'open'").fetchone()
        return int(row[0])

    def close_position(self, position_id: int, reason: str, pnl_usd: float, mark: dict[str, Any]) -> None:
        self.conn.execute(
            "UPDATE positions SET status = 'closed', exit_reason = ?, pnl_usd = ? WHERE id = ?",
            (reason, pnl_usd, position_id),
        )
        self.record_mark(position_id, mark.get("asof") or _now()[:10], mark)
        self.conn.commit()

    def record_mark(self, position_id: int, asof: str, mark: dict[str, Any]) -> None:
        self.conn.execute(
            "INSERT INTO marks (created_at, position_id, asof, close_debit, mark_pnl_usd, payload) VALUES (?,?,?,?,?,?)",
            (_now(), position_id, asof, mark.get("close_debit"), mark.get("mark_pnl_usd"), json.dumps(mark, default=str)),
        )
        self.conn.commit()

    def realized_pnl(self, month: str | None = None) -> float:
        if month:
            row = self.conn.execute(
                "SELECT COALESCE(SUM(pnl_usd), 0) FROM positions WHERE status = 'closed' AND created_at LIKE ?",
                (f"{month}%",),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT COALESCE(SUM(pnl_usd), 0) FROM positions WHERE status = 'closed'"
            ).fetchone()
        return float(row[0])

    def _position_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        extra = json.loads(row["extra_json"] or "{}")
        legs = json.loads(row["legs_json"] or "[]")
        return {
            "id": row["id"],
            "created_at": row["created_at"],
            "playbook": row["playbook"],
            "symbol": row["symbol"],
            "event_key": row["event_key"],
            "structure": row["structure"],
            "expiration": row["expiration"],
            "max_loss_usd": row["max_loss_usd"],
            "credit_usd": row["credit_usd"],
            "status": row["status"],
            "entry_reason": row["entry_reason"],
            "exit_reason": row["exit_reason"],
            "pnl_usd": row["pnl_usd"],
            "legs": legs,
            "extra": extra,
        }
