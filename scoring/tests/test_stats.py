"""stats.py isolation-regime sensitivity (paper/SPEC.md; logs/deviations.md §15). Run: python3 -m unittest discover -s scoring/tests"""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import stats


class Regime(unittest.TestCase):
    def test_empty_config_is_the_T1_user_config_regime(self):
        self.assertEqual(stats.regime({"claude_config": ""}), "user")
        self.assertEqual(stats.regime({}), "user")
        self.assertEqual(stats.regime({"claude_config": "isolated"}), "isolated")

    def test_sensitivity_only_for_arms_with_more_than_one_regime(self):
        by = {"T1_nca": {"A1": {"user": [98.0, 98.2, 98.3], "isolated": [98.1] * 7},
                         "A3": {"user": [98.64] * 10}}}
        arms, pairs = stats.sensitivity(by, [("A3", "A1"), ("A3", "A2")], b=200, seed=1)
        self.assertEqual({(r["arm"], r["regime"]) for r in arms}, {("A1", "user"), ("A1", "isolated")})
        self.assertEqual({(r["comparison"], r["split_arm"], r["regime"]) for r in pairs},
                         {("A3 - A1", "A1", "user"), ("A3 - A1", "A1", "isolated")})
        iso = next(r for r in pairs if r["regime"] == "isolated")
        self.assertEqual((iso["n_x"], iso["n_y"]), (10, 7))
        self.assertAlmostEqual(iso["diff"], 0.54)


if __name__ == "__main__":
    unittest.main()
