import unittest
from datetime import date
from unittest.mock import patch

from kop.market import paid


class PaidClientTests(unittest.TestCase):
    def test_no_key_returns_none(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(paid.configured_sources(), ())
            self.assertIsNone(paid.polygon_option_daily("NVDA260828C00210000", date(2026, 5, 15)))
            self.assertIsNone(paid.tradier_option_quote("NVDA260828C00210000"))

    def test_polygon_maps_bid_ask_when_key_set(self):
        payload = {"status": "OK", "bid": 1.2, "ask": 1.4, "from": "2026-05-15"}
        with patch.dict("os.environ", {"POLYGON_API_KEY": "test-key"}):
            with patch("kop.market.paid.get_json", return_value=payload) as fetch:
                out = paid.polygon_option_daily("NVDA260828C00210000", date(2026, 5, 15))
        self.assertEqual(out["bid"], 1.2)
        self.assertEqual(out["ask"], 1.4)
        self.assertIn("api.polygon.io/v1/open-close/O:NVDA260828C00210000/2026-05-15", fetch.call_args[0][0])

    def test_polygon_refuses_empty_print(self):
        with patch.dict("os.environ", {"POLYGON_API_KEY": "test-key"}):
            with patch("kop.market.paid.get_json", return_value={"status": "OK"}):
                self.assertIsNone(paid.polygon_option_daily("NVDA260828C00210000", date(2026, 5, 15)))


if __name__ == "__main__":
    unittest.main()
