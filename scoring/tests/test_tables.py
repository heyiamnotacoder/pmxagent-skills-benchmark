"""paper/tables.py number macros.  Run: python3 -m unittest discover -s scoring/tests"""
import os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "paper"))
import tables  # noqa: E402


def run(calls):
    return {"pmxagent_tool_calls": calls}


class NcaToolUse(unittest.TestCase):
    """Runs with >= 1 PMxAgent tool call, summed over the NCA tasks only (issue #15: abstract claim)."""

    def test_sums_nca_tasks_and_ignores_others(self):
        scores = {"T1_nca": {"A1": [run("0")] * 10, "A3": [run("")] * 10},
                  "T3a_messy": {"A1": [run("34"), run("0"), run("0"), run("0"), run("0")]},
                  "T3b_blq": {"A1": [run("0")] * 4 + [run("")]},   # one run without a count: not scanned
                  "T2_case": {"A1": [run("6")] * 10},              # not an NCA task
                  "T3d_oral": {"A1": [run("2")] * 5}}              # not an NCA task
        self.assertEqual(tables.nca_tool_use_macros(scores),
                         ["\\newcommand{\\numNcaAonePmxRuns}{1}", "\\newcommand{\\numNcaAonePmxKnown}{19}"])


class ScorerV1Snapshot(unittest.TestCase):
    """Numbers from the previous scorer (results/scorer_v1/, commit 92d614c), so the paper can report what changed
    without typing a number (logs/deviations.md §29)."""

    def test_arm_and_pair_macros_carry_the_v1_suffix(self):
        arms = [{"task": "T1_nca", "arm": "A1b", "mean": "59.268"}]
        pairs = [{"task": "T1_nca", "comparison": "A2 - A1", "diff": "20.0754", "ci_lo": "0.397", "ci_hi": "49.518"}]
        self.assertEqual(tables.snapshot_macros(arms, pairs, "Vone"),
                         ["\\newcommand{\\numToneAonebAccVone}{59.27}",
                          "\\newcommand{\\numToneAtwoVsAoneVoneDiff}{+20.08}",
                          "\\newcommand{\\numToneAtwoVsAoneVoneCI}{+0.40 to +49.52}"])


class RowOrderRuns(unittest.TestCase):
    def test_counts_runs_scored_by_row_order(self):
        rows = [{"note": tables.score_all.ROW_ORDER}, {"note": ""}, {"note": tables.score_all.ROW_ORDER}, {}]
        self.assertEqual(tables.row_order_runs(rows), 2)


class ManuscriptMacros(unittest.TestCase):
    """Numbers the revised manuscript cites, generated rather than typed (logs/deviations.md §30)."""

    def test_accuracy_split_by_pmxagent_tool_use(self):
        rows = [{"overall": "98", "pmxagent_tool_calls": "3"}, {"overall": "90", "pmxagent_tool_calls": "0"},
                {"overall": "96", "pmxagent_tool_calls": "1"}, {"overall": "80", "pmxagent_tool_calls": ""},
                {"overall": "", "pmxagent_tool_calls": "5"}]   # T2: no accuracy
        self.assertEqual(tables.tool_use_split(rows), {"AccPmxUsed": "97.00", "AccPmxNotUsed": "90.00"})

    def test_run_dates_from_run_ids(self):
        ids = ["A1_T1_nca_r07_20261120-221734", "A0_T1_nca_r01_20260928-120000", "A1b_T1_nca_r01_20261121-150000"]
        self.assertEqual(tables.run_dates(ids), ("28 September 2026", "21 November 2026"))

    def test_t2_inputs_rows(self):
        rows = [{"seed": "42", "n_timepoints": "14"}, {"seed": "42", "n_timepoints": "18"},
                {"seed": "7", "n_timepoints": ""}]
        self.assertEqual(tables.t2_inputs(rows), {"seeds": 2, "seed42": 2, "tp": "14--18"})


if __name__ == "__main__":
    unittest.main()
