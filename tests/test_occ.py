import unittest
from datetime import date

from kop.market.occ import format_occ, parse_occ


class OccTests(unittest.TestCase):
    def test_roundtrip(self):
        symbol = format_occ("NVDA", date(2026, 8, 28), "C", 210.0)
        self.assertEqual(symbol, "NVDA260828C00210000")
        occ = parse_occ(symbol)
        self.assertEqual(occ.root, "NVDA")
        self.assertEqual(occ.expiration, date(2026, 8, 28))
        self.assertEqual(occ.right, "C")
        self.assertEqual(occ.strike, 210.0)


if __name__ == "__main__":
    unittest.main()
