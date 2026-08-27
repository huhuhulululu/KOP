import unittest
from datetime import date
from pathlib import Path

from kop.indicators import passing_snapshot
from kop.ledger import Store
from kop.live import LiveBundle
from kop.market.occ import format_occ
from kop.models import Bar, EarningsEvent, Occ, OptionQuote, UnderlyingQuote
from kop.paper.book import _legs_from_position, close_paper, exit_reason, mark_to_close, open_paper
from kop.paper.risk import select_iron_condor
from kop.day import run_day


def quote(right, strike, bid, ask, exp=date(2026, 8, 28)):
    occ = Occ("NVDA", exp, right, strike, format_occ("NVDA", exp, right, strike))
    return OptionQuote(occ=occ, bid=bid, ask=ask, iv=40.0, delta=0.5 if right == "C" else -0.5, open_interest=2000)


def ic_quotes(exp=date(2026, 8, 28)):
    return [
        quote("C", 210, 6.15, 6.30, exp),
        quote("P", 210, 6.15, 6.30, exp),
        quote("P", 197.5, 2.10, 2.25, exp),
        quote("P", 192.5, 0.90, 1.05, exp),
        quote("C", 222.5, 2.00, 2.15, exp),
        quote("C", 227.5, 0.80, 0.95, exp),
    ]


def cheap_close_quotes(exp=date(2026, 8, 28)):
    # shorts almost worthless → 50% credit take. Bids stay > slip so sells are legal.
    return [
        quote("C", 210, 0.25, 0.35, exp),
        quote("P", 210, 0.25, 0.35, exp),
        quote("P", 197.5, 0.20, 0.30, exp),
        quote("P", 192.5, 0.20, 0.30, exp),
        quote("C", 222.5, 0.20, 0.30, exp),
        quote("C", 227.5, 0.20, 0.30, exp),
    ]


class BookTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(path=Path("/tmp/kop-test-book.sqlite"))
        self.store.conn.executescript("DELETE FROM positions; DELETE FROM fills; DELETE FROM marks; DELETE FROM journal;")
        self.store.conn.commit()
        self.event = EarningsEvent("NVDA", date(2026, 8, 26), "amc", "FY27 Q2", "test", True)
        self.fill = select_iron_condor(ic_quotes(), 210.0, date(2026, 8, 28))

    def test_open_mark_and_fifty_percent_exit(self):
        opened = open_paper(
            self.store,
            fill=self.fill,
            event=self.event,
            asof=date(2026, 8, 21),
            spot=210.0,
            reason="test_open",
        )
        self.assertTrue(opened["filled"])
        self.assertFalse(opened["live"])
        self.assertEqual(self.store.open_position_count(), 1)
        pos = self.store.open_positions()[0]
        mark = mark_to_close(cheap_close_quotes(), _legs_from_position(pos), pos["extra"]["entry_cash"])
        why = exit_reason(
            asof=date(2026, 8, 22),
            event=self.event,
            bars=None,
            entry_net=pos["extra"]["net_premium"],
            mark=mark,
            max_loss_usd=pos["max_loss_usd"],
        )
        self.assertEqual(why, "credit_take_50pct")
        closed = close_paper(self.store, position=pos, quotes=cheap_close_quotes(), asof=date(2026, 8, 22), reason=why)
        self.assertEqual(self.store.open_position_count(), 0)
        self.assertGreater(closed["pnl_usd"], 0)

    def test_day_opens_when_gates_pass_and_not_twice(self):
        bars = []
        day = date(2026, 7, 1)
        px = 200.0
        while day <= date(2026, 8, 31):
            if day.weekday() < 5:
                bars.append(Bar(day, px, px + 1, px - 1, px))
                px += 0.1
            day += __import__("datetime").timedelta(days=1)
        under = UnderlyingQuote("NVDA", 210, 209.9, 210.1, 210, "2026-08-21T20:00:00", iv30=55, iv30_annual_high=60, iv30_annual_low=30)
        snap = passing_snapshot(
            asof=date(2026, 8, 21),
            event_date=date(2026, 8, 26),
            days_before=3,
            spot=210.0,
            front_expiry=date(2026, 8, 28),
            path_hit_rate=0.50,
            path_n=6,
        )
        bundle = LiveBundle(date(2026, 8, 21), self.event, bars, under, ic_quotes(), snap)
        first = run_day(self.store, bundle=bundle, paper_fills=True)
        self.assertTrue(first["filled"])
        self.assertEqual(self.store.open_position_count(), 1)
        second = run_day(self.store, bundle=bundle, paper_fills=True)
        self.assertFalse(second["filled"])
        self.assertEqual(self.store.open_position_count(), 1)

    def test_unconfirmed_event_does_not_open(self):
        ghost = EarningsEvent("NVDA", date(2026, 11, 18), "unknown", "yahoo_next", "yahoo", False)
        under = UnderlyingQuote("NVDA", 210, None, None, 210, "t", iv30=55, iv30_annual_high=60, iv30_annual_low=30)
        snap = passing_snapshot(days_before=3, path_hit_rate=0.5, path_n=6, front_expiry=date(2026, 8, 28))
        bundle = LiveBundle(date(2026, 8, 21), ghost, [], under, ic_quotes(), snap)
        out = run_day(self.store, bundle=bundle, paper_fills=True)
        self.assertFalse(out["filled"])
        self.assertEqual(out["opened"]["reason"], "event_unconfirmed_yahoo_only")


if __name__ == "__main__":
    unittest.main()
