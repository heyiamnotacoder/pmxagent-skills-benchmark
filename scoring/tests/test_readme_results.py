"""README results block (readme_results.py, issue #14): tables projected from results/summary.csv, spliced between
markers so the rest of README.md is untouched.  Run: python3 -m unittest discover -s scoring/tests"""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import readme_results as rr


def row(arm, task, **kw):
    base = {"arm": arm, "task": task, "model": "claude-sonnet-4-6", "n_runs": "5", "accuracy_overall": "",
            "n_distinct_outputs": "5", "cost_usd_total": "1.0", "t2_completed": "",
            "t2_summary_consistent_pct": ""}
    return {**base, **kw}


ROWS = [row("A0", "T1_nca", n_runs="10", accuracy_overall="93.21 ± 1.13", n_distinct_outputs="10",
            cost_usd_total="3.808"),
        row("A3", "T3b_blq", accuracy_overall="98.64 ± 0.00", n_distinct_outputs="3"),
        row("A3", "T2_case", n_runs="10", n_distinct_outputs="4", t2_completed="9",
            t2_summary_consistent_pct="95.0 ± 15.8")]


# results/stats_arms.csv (scoring/stats.py): distinct parameter-value sets per arm x NCA task
ARM_STATS = [{"task": "T1_nca", "arm": "A0", "n": "10", "distinct_value_sets": "7"},
             {"task": "T3b_blq", "arm": "A3", "n": "5", "distinct_value_sets": "1"},
             {"task": "T3d_oral", "arm": "A3", "n": "5", "distinct_value_sets": "n/a"}]


class Render(unittest.TestCase):
    def setUp(self):
        self.md = rr.render(ROWS, ARM_STATS)

    def test_accuracy_cell_is_mean_sd_and_n_and_missing_is_a_dash(self):
        acc = self.md.split("### Accuracy")[1].split("###")[0]
        a0 = next(l for l in acc.splitlines() if l.startswith("| A0 "))
        self.assertIn("| 93.21 ± 1.13 (10) |", a0)
        self.assertIn("| – |", a0)   # A0 has no T3b row here
        a3 = next(l for l in acc.splitlines() if l.startswith("| A3 "))
        self.assertIn("| 98.64 ± 0.00 (5) |", a3)

    def test_reproducibility_is_distinct_value_sets_not_file_hashes(self):
        rep = self.md.split("### Reproducibility")[1].split("###")[0]
        self.assertIn("| 7/10 |", next(l for l in rep.splitlines() if l.startswith("| A0 ")))
        a3 = next(l for l in rep.splitlines() if l.startswith("| A3 "))
        self.assertIn("| 1/5 |", a3)          # T3b: from stats_arms, not summary's n_distinct_outputs
        self.assertNotIn("T2", rep.splitlines()[3])   # T2 has no parameter-value sets (its own table below)

    def test_cost_is_mean_only(self):
        cost = self.md.split("### Cost")[1].split("###")[0]
        self.assertIn("| 0.38 |", next(l for l in cost.splitlines() if l.startswith("| A0 ")))

    def test_t2_case_study(self):
        t2 = self.md.split("### Simulation case study")[1]
        self.assertIn("| A3 | 10 | 9 | 95.0 ± 15.8 |", t2)


class Splice(unittest.TestCase):
    def test_replaces_only_between_markers(self):
        text = f"intro\n{rr.START}\nold table\n{rr.END}\nafter\n"
        self.assertEqual(rr.splice(text, "new"), f"intro\n{rr.START}\nnew\n{rr.END}\nafter\n")

    def test_missing_markers_is_an_error(self):
        with self.assertRaises(ValueError):
            rr.splice("no markers here", "new")


if __name__ == "__main__":
    unittest.main()
