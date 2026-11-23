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


if __name__ == "__main__":
    unittest.main()
