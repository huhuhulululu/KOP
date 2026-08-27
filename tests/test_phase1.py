import unittest

from kop.broker import LiveTradingDisabled, submit_live
from kop.indicators import passing_snapshot
from kop.phase1 import evaluate_phase1, refuse_scale


class Phase1Tests(unittest.TestCase):
    def test_current_ic_cannot_hit_500_a_month(self):
        phase = evaluate_phase1(
            snapshot=passing_snapshot(path_hit_rate=2 / 6, path_n=6, ic_net_credit=1.29, ic_width=5.0, ic_max_loss_usd=373.60),
        )
        self.assertLess(phase.max_month_if_never_lose_usd, 500.0)
        self.assertAlmostEqual(phase.shots_per_month, 4 / 12)
        self.assertGreater(phase.breakeven_win_rate, 0.70)
        self.assertLess(phase.path_hit_rate, phase.breakeven_win_rate)
        self.assertLess(phase.ev_per_trade_usd, 0.0)
        blockers = phase.scale_blockers()
        self.assertTrue(any("even_never_lose" in item for item in blockers))
        self.assertTrue(any("ev_per_trade" in item for item in blockers))
        self.assertIsNotNone(refuse_scale(phase, 12))
        self.assertIn("ALLOW_LIVE=false", phase.live_blockers())

    def test_live_submit_stays_locked(self):
        with self.assertRaises(LiveTradingDisabled):
            submit_live({"structure": "short_iron_condor"})


if __name__ == "__main__":
    unittest.main()
