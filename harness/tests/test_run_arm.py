"""Ledger writes must never misalign the committed results/runs.csv.  Run: python3 -m unittest discover -s harness/tests"""
import csv, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import run_arm


class AppendLedger(unittest.TestCase):
    def test_new_column_rewrites_header_and_keeps_old_rows(self):
        with tempfile.TemporaryDirectory() as d:
            run_arm.LEDGER = os.path.join(d, "runs.csv")
            run_arm.append_ledger({"runid": "t1", "cost_usd": "0.2"})
            run_arm.append_ledger({"runid": "t2", "cost_usd": "0.3", "claude_config": "isolated"})
            run_arm.append_ledger({"runid": "t3", "cost_usd": "0.4", "claude_config": "isolated"})
            with open(run_arm.LEDGER, newline="") as f:
                rows = list(csv.DictReader(f))
        self.assertEqual([r["runid"] for r in rows], ["t1", "t2", "t3"])
        self.assertEqual([r["claude_config"] for r in rows], ["", "isolated", "isolated"])
        self.assertEqual(rows[0]["cost_usd"], "0.2")



class RunEnv(unittest.TestCase):
    def test_isolated_env_drops_host_session_variables(self):
        with tempfile.TemporaryDirectory() as d:
            tok = os.path.join(d, "tok"); open(tok, "w").write("x\n")
            run_arm.TOKEN_FILE = tok
            os.environ.update(ANTHROPIC_BASE_URL="http://host-proxy", CLAUDE_CODE_CHILD_SESSION="1")
            env, mode = run_arm.run_env(os.path.join(d, "wt"))
        self.assertEqual(mode, "isolated")
        self.assertFalse([k for k in env if k.startswith("ANTHROPIC") or k == "CLAUDE_CODE_CHILD_SESSION"])
        self.assertEqual(env["HOME"], os.path.join(d, "wt.home"))
        self.assertEqual(env["CLAUDE_CODE_OAUTH_TOKEN"], "x")
        self.assertIn("PATH", env)


if __name__ == "__main__":
    unittest.main()
