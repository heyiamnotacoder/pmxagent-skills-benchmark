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


class PostHocUnscorable(unittest.TestCase):
    """Post-hoc sensitivity (logs/deviations.md §17): drop completed runs with no scorable individual file."""

    def test_recomputed_only_for_tasks_where_a_run_is_dropped(self):
        rows = [{"task": "T1_nca", "arm": "A1", "overall": "0.0", "note": "no scorable individual file"},
                {"task": "T1_nca", "arm": "A1", "overall": "98.0", "note": ""},
                {"task": "T1_nca", "arm": "A1", "overall": "98.4", "note": ""},
                {"task": "T1_nca", "arm": "A2", "overall": "98.7", "note": ""},
                {"task": "T1_nca", "arm": "A2", "overall": "98.6", "note": ""},
                {"task": "T3c_units", "arm": "A1", "overall": "97.0", "note": ""},
                {"task": "T3c_units", "arm": "A2", "overall": "98.0", "note": ""}]
        arms, pairs = stats.posthoc_unscorable(rows, [("A2", "A1"), ("A3", "A1")], b=200, seed=1)
        self.assertEqual([(r["task"], r["arm"], r["n"], r["n_dropped"]) for r in arms],
                         [("T1_nca", "A1", 2, 1), ("T1_nca", "A2", 2, 0)])
        self.assertEqual([(r["task"], r["comparison"], r["n_x"], r["n_y"]) for r in pairs], [("T1_nca", "A2 - A1", 2, 2)])
        self.assertAlmostEqual(pairs[0]["diff"], 0.45)

    def test_nothing_dropped_gives_nothing(self):
        rows = [{"task": "T1_nca", "arm": a, "overall": "98", "note": ""} for a in ("A1", "A2")]
        self.assertEqual(stats.posthoc_unscorable(rows, [("A2", "A1")], b=200, seed=1), ([], []))


class SecondaryPairs(unittest.TestCase):
    def test_a1b_secondary_pairs_are_defined(self):
        self.assertIn(("A1b", "A1"), stats.SECONDARY_PAIRS)
        self.assertIn(("A3", "A1b"), stats.SECONDARY_PAIRS)


if __name__ == "__main__":
    unittest.main()
