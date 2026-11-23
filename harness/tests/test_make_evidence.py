"""Tests for the evidence bundle's provenance (make_evidence.py, paper/SPEC.md slice S12, issue #14).
Run: python3 -m unittest discover -s harness/tests"""
import os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import make_evidence as me, run_arm


def rep(runid, task, version, status="ok", n="1", arm="A0"):
    """A ledger row (results/runs.csv); rep "0" is a preflight."""
    return {"runid": runid, "arm": arm, "task": task, "rep": n, "status": status, "is_error": "False",
            "claude_version": version, "api_error_status": "", "cost_usd": "0.1", "tool_calls": "3",
            "model_seen": "claude-sonnet-4-6"}


VERSIONS_TXT = """claude-code: 2.1.283 (Claude Code)
claude-code-pin T1_nca: 2.1.283
claude-code-pin default: 2.1.310
"""


class ClaudeCodeByTask(unittest.TestCase):
    """Per task: the pin, and the Claude Code versions of the runs that are scored (valid runs only)."""
    def setUp(self):
        d = tempfile.mkdtemp()
        self.vt = os.path.join(d, "versions.txt")
        with open(self.vt, "w") as f:
            f.write(VERSIONS_TXT)

    def test_pins_read_from_versions_txt(self):   # one reader, shared with the harness's version gate
        self.assertEqual(run_arm.read_pins(self.vt), {"T1_nca": "2.1.283", "default": "2.1.310"})

    def test_scored_runs_on_the_pin(self):
        rows = [rep("a", "T1_nca", "2.1.283"), rep("b", "T2_case", "2.1.310"),
                # not scored: a usage-limit stop and a preflight on another version
                rep("c", "T1_nca", "2.1.310", status="failed_ratelimit"), rep("d", "T1_nca", "2.1.310", n="0")]
        got = me.claude_code_by_task(rows, frozenset(), run_arm.read_pins(self.vt))
        self.assertEqual(got["T1_nca"], {"pin": "2.1.283", "scored_versions": ["2.1.283"], "n_scored": 1,
                                         "single_version_on_pin": True})
        self.assertEqual(got["T2_case"]["pin"], "2.1.310")   # default pin
        self.assertTrue(got["T2_case"]["single_version_on_pin"])

    def test_drift_is_reported(self):
        rows = [rep("a", "T2_case", "2.1.310"), rep("b", "T2_case", "2.1.283")]
        got = me.claude_code_by_task(rows, frozenset(), run_arm.read_pins(self.vt))
        self.assertEqual(got["T2_case"]["scored_versions"], ["2.1.283", "2.1.310"])
        self.assertFalse(got["T2_case"]["single_version_on_pin"])

    def test_excluded_run_is_not_scored(self):
        rows = [rep("a", "T2_case", "2.1.310"), rep("b", "T2_case", "2.1.283")]
        got = me.claude_code_by_task(rows, frozenset({"b"}), run_arm.read_pins(self.vt))
        self.assertEqual(got["T2_case"]["scored_versions"], ["2.1.310"])


if __name__ == "__main__":
    unittest.main()
