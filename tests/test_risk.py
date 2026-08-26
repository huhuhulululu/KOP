import unittest
from datetime import date

from kop.market.occ import format_occ
from kop.models import Occ, OptionQuote
from kop.paper.risk import UndefinedRisk, defined_risk, select_iron_condor


def quote(right: str, strike: float, bid: float, ask: float, exp=date(2026, 8, 28)) -> OptionQuote:
    occ = Occ("NVDA", exp, right, strike, format_occ("NVDA", exp, right, strike))
    return OptionQuote(occ=occ, bid=bid, ask=ask, iv=40.0, delta=0.5 if right == "C" else -0.5)


class RiskTests(unittest.TestCase):
    def test_defined_risk_is_width_minus_credit_plus_fees(self):
        max_loss, max_gain = defined_risk(width_usd=5.0, net_credit=1.50, fees_usd=2.60)
        self.assertAlmostEqual(max_loss, 500 - 150 + 2.60)
        self.assertAlmostEqual(max_gain, 150 - 2.60)

    def test_zero_width_is_undefined(self):
        with self.assertRaises(UndefinedRisk):
            defined_risk(0.0, 1.0, 0.0)

    def test_iron_condor_uses_bid_ask_and_caps_loss(self):
        exp = date(2026, 8, 28)
        spot = 210.0
        quotes = [
            quote("C", 210, 6.15, 6.30, exp),
            quote("P", 210, 6.15, 6.30, exp),
            quote("P", 197.5, 2.10, 2.25, exp),
            quote("P", 192.5, 0.90, 1.05, exp),
            quote("C", 222.5, 2.00, 2.15, exp),
            quote("C", 227.5, 0.80, 0.95, exp),
        ]
        fill = select_iron_condor(quotes, spot, exp)
        self.assertEqual(fill.name, "short_iron_condor")
        self.assertTrue(fill.credit)
        self.assertLessEqual(fill.max_loss_usd, 500.0)
        self.assertEqual(len(fill.legs), 4)
        for leg in fill.legs:
            mid = (leg.bid + leg.ask) / 2.0
            self.assertNotAlmostEqual(leg.fill_price, mid)
            if leg.side == "sell":
                self.assertLess(leg.fill_price, leg.bid + 1e-9)
            else:
                self.assertGreater(leg.fill_price, leg.ask - 1e-9)


if __name__ == "__main__":
    unittest.main()
