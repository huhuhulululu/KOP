import unittest

from kop.selector import select_recipe


class SelectorTests(unittest.TestCase):
    def test_event_day_stands_down(self):
        recipe, reason, _ = select_recipe(days_before=0, iv_rank=80, implied_move_pct=6, hist_abs_median=3)
        self.assertEqual(recipe.id, "do_nothing")
        self.assertIn("too_close", reason)

    def test_rich_implied_and_high_iv_picks_iron_condor(self):
        recipe, reason, details = select_recipe(days_before=3, iv_rank=70, implied_move_pct=6, hist_abs_median=3)
        self.assertEqual(recipe.id, "short_iron_condor")
        self.assertGreaterEqual(details["implied_over_hist"], 1.2)

    def test_low_iv_rank_does_not_sell_vol(self):
        recipe, reason, _ = select_recipe(days_before=3, iv_rank=42.7, implied_move_pct=6, hist_abs_median=3)
        self.assertEqual(recipe.id, "do_nothing")
        self.assertIn("iv_rank", reason)

    def test_cheap_implied_picks_reverse_ic(self):
        recipe, reason, _ = select_recipe(days_before=3, iv_rank=40, implied_move_pct=2, hist_abs_median=5)
        self.assertEqual(recipe.id, "reverse_iron_condor")

    def test_never_selects_naked(self):
        for iv, implied, hist in ((80, 6, 3), (40, 2, 5), (55, 3.1, 3), (None, None, None)):
            recipe, _reason, _ = select_recipe(days_before=3, iv_rank=iv, implied_move_pct=implied, hist_abs_median=hist)
            self.assertNotEqual(recipe.risk, "undefined")


if __name__ == "__main__":
    unittest.main()
