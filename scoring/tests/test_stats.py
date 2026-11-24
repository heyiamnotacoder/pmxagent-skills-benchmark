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


class CharacterOrderSensitivity(unittest.TestCase):
    """Post hoc (logs/deviations.md §29): runs scored by row order, re-scored in character order of subject number."""

    def test_recomputes_only_arms_with_a_replaced_run_and_their_pairs(self):
        rows = [{"runid": "a", "task": "T1_nca", "arm": "A1b", "overall": "16.5"},
                {"runid": "b", "task": "T1_nca", "arm": "A1b", "overall": "98.0"},
                {"runid": "c", "task": "T1_nca", "arm": "A3", "overall": "98.6"},
                {"runid": "d", "task": "T1_nca", "arm": "A3", "overall": "98.6"}]
        arms, pairs = stats.with_replacements(rows, {"a": 98.0}, [("A3", "A1b"), ("A3", "A2")], b=200, seed=1)
        self.assertEqual([(r["task"], r["arm"], r["n"], r["n_replaced"], r["mean"]) for r in arms],
                         [("T1_nca", "A1b", 2, 1, 98.0)])
        self.assertEqual([r["comparison"] for r in pairs], ["A3 - A1b"])
        self.assertAlmostEqual(pairs[0]["diff"], 0.6)

    def test_no_replacement_gives_nothing(self):
        rows = [{"runid": "a", "task": "T1_nca", "arm": "A1", "overall": "98"}]
        self.assertEqual(stats.with_replacements(rows, {}, [("A2", "A1")], b=200, seed=1), ([], []))


class TerminalPoints(unittest.TestCase):
    """Per-arm pooling of score_nca.terminal_point_breakdown (descriptive; logs/deviations.md §26)."""

    def test_pools_subjects_over_reporting_runs_only(self):
        b1 = {"subjects": 10, "match": 9, "lz_match_n": 36, "lz_match_err": 0, "lz_differ_n": 4, "lz_differ_err": 2,
              "lz_none_n": 0, "lz_none_err": 0}
        b2 = {"subjects": 10, "match": 8, "lz_match_n": 32, "lz_match_err": 1, "lz_differ_n": 4, "lz_differ_err": 3,
              "lz_none_n": 4, "lz_none_err": 4}
        self.assertEqual(stats.terminal_points([b1, None, b2]),
                         {"npts_runs": 2, "npts_match_pct": 85.0, "lz_errors": 10, "lz_errors_npts_differ": 5,
                          "lz_errors_npts_none": 4, "lz_errors_npts_match": 1})

    def test_no_run_reported_points_is_na(self):
        na = {"npts_runs": 0, "npts_match_pct": "n/a", "lz_errors": "n/a", "lz_errors_npts_differ": "n/a",
              "lz_errors_npts_none": "n/a", "lz_errors_npts_match": "n/a"}
        self.assertEqual(stats.terminal_points([None, None]), na)
        empty = dict.fromkeys(stats.sn.BREAKDOWN_KEYS, 0)
        self.assertEqual(stats.terminal_points([empty])["npts_match_pct"], "n/a")


class WriteCsv(unittest.TestCase):
    def test_header_covers_keys_that_only_later_rows_have(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            old, stats.RES = stats.RES, d
            try:
                stats.write_csv("x.csv", [{"task": "T2_case"}, {"task": "T1_nca", "npts_runs": 3}], ["task"])
                self.assertEqual(open(os.path.join(d, "x.csv")).read().splitlines(), ["task,npts_runs", "T2_case,", "T1_nca,3"])
            finally:
                stats.RES = old


class ValueSetHash(unittest.TestCase):
    """Distinct value sets are counted on the scored table, as Methods 2.5 says: the seven scored parameters, no
    R2adj or terminal-point columns, no empty cells (peer review S3; logs/deviations.md §29)."""

    BASE = {("s1", "Cmax"): 10.0, ("s1", "HL"): 5.0}

    def test_unscored_columns_and_empty_cells_do_not_change_the_hash(self):
        extra = {**self.BASE, ("s1", "R2ADJ"): 0.9512, ("s1", "NPTS"): 3.0, ("s1", "Vz"): float("nan")}
        self.assertEqual(stats.value_set_hash(self.BASE), stats.value_set_hash(extra))

    def test_a_scored_value_beyond_six_significant_digits_does_not_count(self):
        self.assertEqual(stats.value_set_hash(self.BASE),
                         stats.value_set_hash({**self.BASE, ("s1", "Cmax"): 10.0000001}))
        self.assertNotEqual(stats.value_set_hash(self.BASE), stats.value_set_hash({**self.BASE, ("s1", "Cmax"): 10.01}))


class SecondaryPairs(unittest.TestCase):
    def test_a1b_secondary_pairs_are_defined(self):
        self.assertIn(("A1b", "A1"), stats.SECONDARY_PAIRS)
        self.assertIn(("A3", "A1b"), stats.SECONDARY_PAIRS)


if __name__ == "__main__":
    unittest.main()
