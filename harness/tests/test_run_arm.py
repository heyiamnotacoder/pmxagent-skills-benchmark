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


class RunStatus(unittest.TestCase):
    """A usage-limit (HTTP 429) stop must be told apart from a real crash in the ledger (deviations §1 labels)."""
    def test_usage_limit_is_labelled_not_exit_code(self):
        midrun = {"api_error_status": 429, "total_cost_usd": 0.17, "is_error": True}
        instant = {"api_error_status": 429, "total_cost_usd": 0, "is_error": True}
        self.assertEqual(run_arm.run_status("exit1", midrun), "failed_ratelimit_midrun")
        self.assertEqual(run_arm.run_status("exit1", instant), "failed_ratelimit")
        self.assertEqual(run_arm.run_status("exit1", {}), "exit1")            # no result event: a real crash
        self.assertEqual(run_arm.run_status("ok", {"is_error": False}), "ok")
        self.assertEqual(run_arm.run_status("timeout", {}), "timeout")


class RepState(unittest.TestCase):
    """--until counts valid reps + reps still in progress; a leftover preflight (rep 0) is neither."""
    def test_preflight_folder_and_rep0_rows_do_not_count(self):
        rows = [{"arm": "A1", "task": "T1_nca", "rep": "0", "status": "ok", "is_error": "False"},
                {"arm": "A1", "task": "T1_nca", "rep": "1", "status": "ok", "is_error": "False"},
                {"arm": "A1", "task": "T1_nca", "rep": "2", "status": "failed_ratelimit_midrun", "is_error": "True"},
                {"arm": "A1", "task": "T1_nca", "rep": "3", "status": "ok", "is_error": "False"},
                {"arm": "A1", "task": "T2_case", "rep": "4", "status": "ok", "is_error": "False"}]
        live = ["A1_T1_nca_r00_20261116-222130", "A1_T1_nca_r00_20261116-222130.home",
                "A1_T1_nca_r00_20261116-222130.mcp.json", "A1_T1_nca_r04_20261117-090000",
                "A1_T1_nca_r04_20261117-090000.home", "A1_T2_case_r05_20261117-090000"]
        self.assertEqual(run_arm.rep_state("A1", "T1_nca", rows, live), (3, 4))   # 2 valid + r04 live; last rep 4


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


class CheckRunRoot(unittest.TestCase):
    def test_refuses_instruction_file_in_ancestor_and_non_private_root(self):
        with tempfile.TemporaryDirectory() as d:
            root = os.path.join(d, "shared", "runs")
            self.assertEqual(run_arm.check_run_root(root), os.path.realpath(root))
            open(os.path.join(d, "shared", "CLAUDE.md"), "w").write("injected")
            with self.assertRaises(SystemExit):
                run_arm.check_run_root(root)
            os.remove(os.path.join(d, "shared", "CLAUDE.md"))
            os.chmod(root, 0o755)
            with self.assertRaises(SystemExit):
                run_arm.check_run_root(root)


if __name__ == "__main__":
    unittest.main()
