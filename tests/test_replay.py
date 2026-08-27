import unittest
from datetime import date, timedelta

from kop.models import Bar
from kop.research import contrast_for_row, replay


def weekday_bars(start: date, end: date) -> list[Bar]:
    bars = []
    day = start
    price = 120.0
    while day <= end:
        if day.weekday() < 5:
            bars.append(Bar(day, price, price + 2, price - 2, price + 0.5))
            price += 0.25
        day += timedelta(days=1)
    return bars


class ReplayTests(unittest.TestCase):
    def test_six_events_no_fake_fills(self):
        bars = weekday_bars(date(2025, 1, 2), date(2026, 8, 26))
        rows = replay("NVDA", asof=date(2026, 8, 26), bars=bars)
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[0].announce_date, date(2025, 2, 26))
        self.assertEqual(rows[-1].announce_date, date(2026, 5, 20))
        for row in rows:
            self.assertEqual(row.fill_status, "missing_quotes")
            self.assertIsNone(row.entry_net)
            self.assertIsNone(row.pnl_usd)
            self.assertEqual(row.days_before, 3)
            self.assertIsNotNone(row.gap_pct)
            self.assertIsNotNone(row.close_move_pct)
            self.assertIsNotNone(row.entry_close)
            self.assertIsNotNone(row.event_close)

    def test_contrast_scores_only_do_nothing(self):
        bars = weekday_bars(date(2025, 1, 2), date(2026, 8, 26))
        row = replay("NVDA", asof=date(2026, 8, 26), bars=bars)[0]
        sweep = contrast_for_row(row)
        self.assertEqual(sweep["do_nothing"]["pnl_usd"], 0.0)
        self.assertIn("recipes", sweep)
        self.assertEqual(sweep["fills"], "missing_quotes")
        self.assertIn("short_iron_condor", sweep["recipes"])
        self.assertIn("long_call", sweep["recipes"])


if __name__ == "__main__":
    unittest.main()
