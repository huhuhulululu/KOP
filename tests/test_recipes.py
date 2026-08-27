import unittest

from kop.recipes import RECIPES, allowed_paper, forbidden, recipe


class RecipeTests(unittest.TestCase):
    def test_catalog_covers_single_and_multi(self):
        legs = {item.legs for item in RECIPES}
        self.assertTrue({0, 1, 2, 4}.issubset(legs))
        families = {item.family for item in RECIPES}
        self.assertTrue({"single", "vertical", "vol", "calendar"}.issubset(families))

    def test_undefined_never_paper(self):
        for item in RECIPES:
            if item.risk == "undefined":
                self.assertFalse(item.paper_allowed)
                self.assertEqual(item.role, "forbidden")
        self.assertGreaterEqual(len(forbidden()), 3)

    def test_default_is_defined_short_vol(self):
        ic = recipe("short_iron_condor")
        self.assertTrue(ic.paper_allowed)
        self.assertEqual(ic.risk, "defined")
        self.assertEqual(ic.role, "default")

    def test_allowed_excludes_jade_and_naked(self):
        ids = {item.id for item in allowed_paper()}
        self.assertNotIn("jade_lizard", ids)
        self.assertNotIn("short_strangle", ids)
        self.assertIn("do_nothing", ids)
        self.assertIn("reverse_iron_condor", ids)
        self.assertIn("iv_expansion_exit_before", ids)


if __name__ == "__main__":
    unittest.main()
