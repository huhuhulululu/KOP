import unittest
from datetime import date

from kop.indicators import passing_snapshot, sparse_snapshot
from kop.selector import select_recipe


class SelectorTests(unittest.TestCase):
    def test_event_day_stands_down(self):
        snap = passing_snapshot(days_before=0, asof=date(2026, 8, 26), event_date=date(2026, 8, 26))
        recipe, reason, _ = select_recipe(snap)
        self.assertEqual(recipe.id, "do_nothing")
        self.assertIn("too_close", reason)

    def test_all_gates_open_picks_iron_condor(self):
        recipe, reason, details = select_recipe(passing_snapshot())
        self.assertEqual(recipe.id, "short_iron_condor")
        self.assertGreaterEqual(details["implied_over_hist"], 1.2)
        self.assertEqual(details["short_vol_blockers"], [])

    def test_low_iv_rank_does_not_sell_vol(self):
        snap = passing_snapshot(iv_range_rank=42.7, implied_over_hist=1.83)
        recipe, reason, details = select_recipe(snap)
        self.assertEqual(recipe.id, "do_nothing")
        self.assertIn("iv_rank", reason)
        self.assertTrue(any(item.startswith("iv_rank") for item in details["short_vol_blockers"]))

    def test_path_hit_two_of_six_blocks_short_vol(self):
        snap = passing_snapshot(path_hit_rate=2.0 / 6.0, path_n=6, implied_over_hist=1.83, iv_range_rank=62.0)
        recipe, reason, details = select_recipe(snap)
        self.assertEqual(recipe.id, "do_nothing")
        self.assertIn("path_hit_rate", reason)
        self.assertTrue(any("path_hit_rate" in item for item in details["short_vol_blockers"]))

    def test_cheap_implied_picks_reverse_ic_when_long_gates_clear(self):
        snap = passing_snapshot(
            iv_range_rank=40.0,
            implied_move_sell_pct=2.0,
            hist_abs_close_median=5.0,
            implied_over_hist=0.40,
            path_hit_rate=0.33,
            reverse_path_hit_rate=0.67,
        )
        recipe, reason, _ = select_recipe(snap)
        self.assertEqual(recipe.id, "reverse_iron_condor")
        self.assertIn("long_defined_vol", reason)

    def test_low_vix_does_not_block_short_vol(self):
        snap = passing_snapshot(vix=15.2, vix_1y_percentile=14.0)
        recipe, _reason, details = select_recipe(snap)
        self.assertEqual(recipe.id, "short_iron_condor")
        self.assertEqual(details["vix_1y_percentile"], 14.0)

    def test_missing_term_slope_fail_closed(self):
        snap = passing_snapshot(term_slope_vol=None)
        recipe, reason, details = select_recipe(snap)
        self.assertEqual(recipe.id, "do_nothing")
        self.assertIn("term_slope_vol_missing", details["short_vol_blockers"])
        self.assertIn("term_slope", reason)

    def test_never_selects_naked(self):
        cases = (
            passing_snapshot(),
            passing_snapshot(iv_range_rank=40.0, implied_over_hist=0.4, reverse_path_hit_rate=0.67),
            passing_snapshot(implied_over_hist=1.05, path_hit_rate=0.33),
            sparse_snapshot(asof=date(2026, 5, 15), days_before=3),
        )
        for snap in cases:
            recipe, _reason, _ = select_recipe(snap)
            self.assertNotEqual(recipe.risk, "undefined")


if __name__ == "__main__":
    unittest.main()
