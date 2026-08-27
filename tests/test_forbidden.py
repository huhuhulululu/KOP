import sys
import unittest

from kop.forbidden import assert_clean_process, imported_forbidden
from kop.ledger import Store


class ForbiddenTests(unittest.TestCase):
    def test_process_is_clean(self):
        self.assertEqual(imported_forbidden(), [])
        assert_clean_process()

    def test_loading_btchour_name_is_caught(self):
        sys.modules["btchour.tickers"] = object()
        try:
            self.assertIn("btchour.tickers", imported_forbidden())
            with self.assertRaises(RuntimeError):
                assert_clean_process()
        finally:
            sys.modules.pop("btchour.tickers", None)

    def test_refuses_btchour_sqlite(self):
        from pathlib import Path

        with self.assertRaises(RuntimeError):
            Store(Path("/tmp/btchour.sqlite"))


if __name__ == "__main__":
    unittest.main()
