import unittest

from kop.scoring import betting_ev, edge


class EvTests(unittest.TestCase):
    def test_formula(self):
        self.assertAlmostEqual(betting_ev(0.6, 1.0), 0.6 * 1.0 - 0.4)
        payload = edge(0.5, 0.2).as_dict()
        self.assertEqual(payload["formula"], "EV = p*b - (1-p)")
        self.assertAlmostEqual(payload["ev"], 0.5 * 0.2 - 0.5)


if __name__ == "__main__":
    unittest.main()
