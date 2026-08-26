import unittest
from datetime import date

from kop.models import TapeRow
from kop.path_score import score_recipe
from kop.recipes import recipe


def row(**kwargs) -> TapeRow:
    base = dict(
        event_key="NVDA:2026-02-25:amc",
        symbol="NVDA",
        fiscal_label="FY26 Q4",
        announce_date=date(2026, 2, 25),
        session="amc",
        entry_date=date(2026, 2, 20),
        days_before=3,
        entry_close=189.82,
        event_close=195.56,
        reaction_open=194.27,
        reaction_high=194.29,
        reaction_low=184.32,
        reaction_close=184.89,
        iv_rank=None,
        iv_percentile=None,
        iv_source="missing",
        structure="short_iron_condor",
        strikes=None,
        expiration=None,
        entry_quote_kind="missing",
        entry_net=None,
        gap_pct=-0.66,
        close_move_pct=-5.46,
        high_move_pct=-0.65,
        low_move_pct=-5.75,
        vendor_implied_move_pct=3.0,
        vendor_iv_crush_pct=26.0,
        vendor_source="test",
        exit_rule="x",
        exit_date=date(2026, 2, 26),
        exit_net=None,
        fees_usd=None,
        pnl_usd=None,
        fill_status="missing_quotes",
        notes="",
    )
    base.update(kwargs)
    return TapeRow(**base)


class PathScoreTests(unittest.TestCase):
    def test_feb_2026_breaks_three_percent_iron_condor(self):
        scored = score_recipe(recipe("short_iron_condor"), row(), implied_pct=3.0)
        self.assertEqual(scored["path_outcome"], "beyond_wing")
        self.assertEqual(scored["thesis"], "hurt")

    def test_small_move_helps_iron_condor(self):
        calm = row(
            event_close=181.60,
            reaction_high=184.47,
            reaction_low=176.41,
            reaction_close=180.17,
            close_move_pct=-0.79,
            high_move_pct=1.58,
            low_move_pct=-2.86,
        )
        scored = score_recipe(recipe("short_iron_condor"), calm, implied_pct=3.0)
        self.assertEqual(scored["thesis"], "helped")

    def test_long_straddle_helped_only_if_realized_beats_implied(self):
        scored = score_recipe(recipe("long_straddle"), row(), implied_pct=3.0)
        self.assertEqual(scored["thesis"], "helped")
        calm = row(close_move_pct=-0.79, event_close=181.6, reaction_high=182, reaction_low=180, reaction_close=180.2)
        self.assertEqual(score_recipe(recipe("long_straddle"), calm, implied_pct=3.0)["thesis"], "hurt")

    def test_do_nothing_is_zero(self):
        scored = score_recipe(recipe("do_nothing"), row(), implied_pct=3.0)
        self.assertEqual(scored["pnl_usd"], 0.0)

    def test_naked_stays_forbidden(self):
        scored = score_recipe(recipe("short_strangle"), row(), implied_pct=3.0)
        self.assertEqual(scored["status"], "forbidden")


if __name__ == "__main__":
    unittest.main()
