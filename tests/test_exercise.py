import unittest
from datetime import date

from kop.market.occ import format_occ
from kop.models import Occ, OptionQuote
from kop.paper.exercise import early_exercise_risk, intrinsic, time_value_at_bid


def q(right, strike, bid, ask):
    occ = Occ("NVDA", date(2026, 8, 28), right, strike, format_occ("NVDA", date(2026, 8, 28), right, strike))
    return OptionQuote(occ=occ, bid=bid, ask=ask)


class ExerciseTests(unittest.TestCase):
    def test_intrinsic(self):
        self.assertAlmostEqual(intrinsic("C", 200, 210), 10)
        self.assertAlmostEqual(intrinsic("P", 200, 190), 10)
        self.assertAlmostEqual(intrinsic("C", 220, 210), 0)

    def test_time_value_uses_bid_not_mid(self):
        quote = q("C", 200, 9.80, 10.40)
        self.assertAlmostEqual(time_value_at_bid(quote, 210), -0.20)
        self.assertTrue(early_exercise_risk(quote, 210))

    def test_otm_not_flagged(self):
        quote = q("C", 220, 1.10, 1.20)
        self.assertFalse(early_exercise_risk(quote, 210))


if __name__ == "__main__":
    unittest.main()
