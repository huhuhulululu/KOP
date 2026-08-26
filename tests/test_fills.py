import unittest

from kop.market.occ import format_occ
from kop.models import Occ, OptionQuote
from kop.paper.fills import MidPriceForbidden, cash_effect, fill_buy, fill_sell


def q(right: str, strike: float, bid: float, ask: float) -> OptionQuote:
    occ = Occ("NVDA", __import__("datetime").date(2026, 8, 28), right, strike, format_occ("NVDA", __import__("datetime").date(2026, 8, 28), right, strike))
    return OptionQuote(occ=occ, bid=bid, ask=ask)


class FillTests(unittest.TestCase):
    def test_sell_hits_bid_minus_slip(self):
        fill = fill_sell(q("C", 210, 2.00, 2.20), slippage=0.05)
        self.assertEqual(fill.fill_price, 1.95)
        self.assertEqual(fill.quote_kind, "bid_ask")
        self.assertNotAlmostEqual(fill.fill_price, (2.00 + 2.20) / 2.0)

    def test_buy_hits_ask_plus_slip(self):
        fill = fill_buy(q("P", 200, 0.80, 1.00), slippage=0.05)
        self.assertEqual(fill.fill_price, 1.05)
        self.assertNotAlmostEqual(fill.fill_price, 0.90)

    def test_mid_is_rejected_if_someone_passes_it(self):
        quote = q("C", 210, 2.00, 2.00)
        with self.assertRaises(MidPriceForbidden):
            fill_sell(quote, slippage=0.0)

    def test_cash_effect_includes_fee_and_multiplier(self):
        sold = fill_sell(q("C", 210, 2.00, 2.20), slippage=0.05)
        self.assertEqual(sold.fee_usd, 0.65)
        self.assertAlmostEqual(cash_effect(sold), 1.95 * 100 - 0.65)


if __name__ == "__main__":
    unittest.main()
