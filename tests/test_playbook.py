import unittest
from datetime import date, timedelta

from kop.config import PLAYBOOK, SYMBOL
from kop.models import Bar, EarningsEvent, UnderlyingQuote
from kop.paper.engine import paper_once
from kop.playbook import decide
from kop.ledger import Store


def weekday_bars(start: date, n: int) -> list[Bar]:
    bars = []
    day = start
    price = 200.0
    while len(bars) < n:
        if day.weekday() < 5:
            bars.append(Bar(day, price, price + 1, price - 1, price))
            price += 0.1
        day += timedelta(days=1)
    return bars


class PlaybookTests(unittest.TestCase):
    def setUp(self):
        self.event = EarningsEvent("NVDA", date(2026, 8, 26), "amc", "FY27 Q2", "test")
        self.bars = weekday_bars(date(2026, 7, 1), 50)
        self.under = UnderlyingQuote(
            "NVDA", 209.66, 209.6, 209.7, 209.66, "2026-08-21T15:59:59",
            iv30=55.0, iv30_annual_high=60.0, iv30_annual_low=30.0,
        )

    def test_wrong_symbol(self):
        d = decide(symbol="TSLA", asof=date(2026, 8, 21), event=self.event, bars=self.bars, under=self.under, iv_history=[], countable_tape=4, auto=True)
        self.assertFalse(d.allow)
        self.assertIn("not_in_playbook", d.reason)

    def test_long_call_forbidden(self):
        d = decide(symbol=SYMBOL, asof=date(2026, 8, 21), event=self.event, bars=self.bars, under=self.under, iv_history=[], countable_tape=4, auto=True, want_structure="long_call")
        self.assertEqual(d.reason, "forbidden_long_premium_before_event")

    def test_naked_forbidden(self):
        d = decide(symbol=SYMBOL, asof=date(2026, 8, 21), event=self.event, bars=self.bars, under=self.under, iv_history=[], countable_tape=4, auto=True, want_structure="short_straddle")
        self.assertEqual(d.reason, "forbidden_naked_short")

    def test_event_day_rejected(self):
        d = decide(symbol=SYMBOL, asof=date(2026, 8, 26), event=self.event, bars=self.bars, under=self.under, iv_history=[], countable_tape=4, auto=True)
        self.assertFalse(d.allow)
        self.assertTrue(d.reason.startswith("outside_entry_window"))

    def test_low_iv_rank_rejected(self):
        cheap = UnderlyingQuote("NVDA", 210, None, None, 210, "t", iv30=35.0, iv30_annual_high=60.0, iv30_annual_low=30.0)
        d = decide(symbol=SYMBOL, asof=date(2026, 8, 21), event=self.event, bars=self.bars, under=cheap, iv_history=[], countable_tape=4, auto=True)
        self.assertFalse(d.allow)
        self.assertIn("iv30_range_rank", d.reason)

    def test_human_tape_not_required(self):
        d = decide(symbol=SYMBOL, asof=date(2026, 8, 21), event=self.event, bars=self.bars, under=self.under, iv_history=[], countable_tape=0, auto=True)
        self.assertTrue(d.allow)
        self.assertEqual(d.reason, "gates_open")

    def test_auto_disabled_still_blocks_fill(self):
        d = decide(symbol=SYMBOL, asof=date(2026, 8, 21), event=self.event, bars=self.bars, under=self.under, iv_history=[], countable_tape=4, auto=False)
        self.assertEqual(d.reason, "auto_trade_disabled")
        self.assertEqual(d.playbook, PLAYBOOK)

    def test_paper_once_does_not_fill(self):
        store = Store(path=__import__("pathlib").Path("/tmp/kop-test-paper.sqlite"))
        store.conn.execute("DELETE FROM journal")
        store.conn.commit()
        out = paper_once(store, asof=date(2026, 8, 26), event=self.event, bars=self.bars, under=self.under)
        self.assertFalse(out["allow"])
        self.assertFalse(out["filled"])
        self.assertEqual(out["selected_recipe"]["id"], "do_nothing")

    def test_sparse_t_minus_3_fail_closed_no_iron_condor(self):
        store = Store(path=__import__("pathlib").Path("/tmp/kop-test-paper-sparse.sqlite"))
        out = paper_once(
            store,
            asof=date(2026, 8, 21),
            event=self.event,
            bars=self.bars,
            under=self.under,
            implied_move_pct=6.0,
            hist_abs_median=3.0,
        )
        self.assertFalse(out["filled"])
        self.assertEqual(out["selected_recipe"]["id"], "do_nothing")
        self.assertTrue(out["select_details"]["short_vol_blockers"])


if __name__ == "__main__":
    unittest.main()
