import math
import unittest
from datetime import date, timedelta

from kop.indicators import build_snapshot, passing_snapshot, path_stats, realized_vol_pct
from kop.market.occ import format_occ
from kop.market.vix import vix_percentile
from kop.models import Bar, EarningsEvent, Occ, OptionQuote, TapeRow, UnderlyingQuote


def _quote(exp, right, strike, bid, ask, iv, delta, oi=1000.0, volume=500.0):
    occ = Occ("NVDA", exp, right, strike, format_occ("NVDA", exp, right, strike))
    return OptionQuote(
        occ=occ,
        bid=bid,
        ask=ask,
        iv=iv,
        delta=delta,
        volume=volume,
        open_interest=oi,
    )


def _tape(announce, close_move, high_move, low_move, implied=3.0) -> TapeRow:
    event_close = 100.0
    return TapeRow(
        event_key=f"NVDA:{announce.isoformat()}:amc",
        symbol="NVDA",
        fiscal_label="t",
        announce_date=announce,
        session="amc",
        entry_date=announce - timedelta(days=5),
        days_before=3,
        entry_close=event_close,
        event_close=event_close,
        reaction_open=event_close * (1 + close_move / 200.0),
        reaction_high=event_close * (1 + high_move / 100.0),
        reaction_low=event_close * (1 + low_move / 100.0),
        reaction_close=event_close * (1 + close_move / 100.0),
        iv_rank=None,
        iv_percentile=None,
        iv_source="test",
        structure="short_iron_condor",
        strikes=None,
        expiration=None,
        entry_quote_kind="missing",
        entry_net=None,
        gap_pct=close_move / 2.0,
        close_move_pct=close_move,
        high_move_pct=high_move,
        low_move_pct=low_move,
        vendor_implied_move_pct=implied,
        vendor_iv_crush_pct=None,
        vendor_source="test",
        exit_rule="test",
        exit_date=announce + timedelta(days=1),
        exit_net=None,
        fees_usd=None,
        pnl_usd=None,
        fill_status="missing_quotes",
        notes="test",
    )


class IndicatorTests(unittest.TestCase):
    def test_realized_vol_two_returns(self):
        closes = [100.0, 100.0 * math.exp(0.01), 100.0]
        hv = realized_vol_pct(closes, 2)
        var = (0.01**2 + 0.01**2) / 1
        expected = math.sqrt(var) * math.sqrt(252.0) * 100.0
        self.assertAlmostEqual(hv, expected, places=6)

    def test_realized_vol_needs_window(self):
        self.assertIsNone(realized_vol_pct([100.0, 101.0], 20))

    def test_vix_percentile_is_rank_in_history(self):
        hist = [(date(2026, 1, 1) + timedelta(days=i), 10.0 + i * 0.05) for i in range(100)]
        self.assertAlmostEqual(vix_percentile(12.0, hist, lookback=100), 100.0 * 41 / 100)
        self.assertIsNone(vix_percentile(12.0, hist[:10], lookback=252))

    def test_path_stats_counts_helped_hurt(self):
        # inside ±3% → short IC helped; beyond → hurt / reverse helped
        rows = [
            _tape(date(2025, 2, 26), -8.5, 3.0, -9.0),
            _tape(date(2025, 5, 28), 3.3, 6.4, -1.0),
            _tape(date(2025, 8, 27), -0.8, 1.2, -1.5),
            _tape(date(2025, 11, 19), -3.2, 5.1, -4.0),
            _tape(date(2026, 2, 25), -5.5, 1.0, -6.0),
            _tape(date(2026, 5, 20), -1.8, 1.5, -2.2),
        ]
        stats = path_stats(rows)
        self.assertEqual(stats["path_n"], 6)
        self.assertAlmostEqual(stats["path_hit_rate"], 2 / 6)
        self.assertEqual(stats["reverse_path_n"], 6)
        self.assertAlmostEqual(stats["reverse_path_hit_rate"], 4 / 6)

    def test_build_snapshot_term_vrp_and_credit(self):
        asof = date(2026, 8, 21)
        front = date(2026, 8, 28)
        back = date(2026, 9, 18)
        quotes = [
            _quote(front, "C", 210, 6.15, 6.30, 100.0, 0.50, oi=12000),
            _quote(front, "P", 210, 6.15, 6.30, 100.0, -0.50, oi=12000),
            _quote(front, "C", 222.5, 2.00, 2.15, 102.7, 0.23, oi=3000),
            _quote(front, "P", 200.0, 2.10, 2.25, 97.8, -0.25, oi=3000),
            _quote(front, "P", 197.5, 2.10, 2.25, 98.0, -0.28, oi=2000),
            _quote(front, "P", 192.5, 0.90, 1.05, 99.0, -0.18, oi=1500),
            _quote(front, "C", 227.5, 0.80, 0.95, 103.0, 0.16, oi=1500),
            _quote(back, "C", 210, 8.00, 8.20, 41.5, 0.51, oi=800),
            _quote(back, "P", 210, 8.00, 8.20, 41.5, -0.49, oi=800),
        ]
        under = UnderlyingQuote(
            "NVDA", 209.66, 209.6, 209.7, 209.66, "2026-08-21T20:00:00",
            iv30=41.467, iv30_annual_high=54.61, iv30_annual_low=31.66,
        )
        closes = [200.0]
        for i in range(30):
            closes.append(closes[-1] * math.exp(0.01 if i % 2 == 0 else -0.008))
        bars = [Bar(date(2026, 7, 1) + timedelta(days=i), c, c, c, c) for i, c in enumerate(closes)]
        event = EarningsEvent("NVDA", date(2026, 8, 26), "amc", "FY27 Q2", "test")
        snap = build_snapshot(
            asof=asof,
            under=under,
            quotes=quotes,
            bars=bars,
            event=event,
            tape_rows=[],
            days_before=3,
            vix=15.21,
            vix_1y_percentile=14.0,
        )
        self.assertGreater(snap.term_slope_vol, 50.0)
        self.assertIsNotNone(snap.hv20)
        self.assertIsNotNone(snap.vrp_iv30_over_hv20)
        self.assertLess(snap.atm_straddle_spread_pct, 0.05)
        self.assertGreaterEqual(snap.atm_oi, 24000)
        self.assertAlmostEqual(snap.risk_reversal_25d, 97.8 - 102.7, places=4)
        self.assertIsNotNone(snap.ic_credit_over_width)
        self.assertGreaterEqual(snap.ic_credit_over_width, 0.20)
        self.assertIn("path_hit_rate", snap.missing)
        self.assertEqual(snap.gate_table()[0].used_as, "GATE")
        vix_row = next(row for row in snap.gate_table() if row.name == "vix")
        self.assertEqual(vix_row.used_as, "INFO")

    def test_passing_fixture_has_no_short_blockers(self):
        self.assertEqual(passing_snapshot().short_vol_blockers(), [])


if __name__ == "__main__":
    unittest.main()
