"""Ledger writes must never misalign the committed results/runs.csv.  Run: python3 -m unittest discover -s harness/tests"""
import csv, json, os, sys, tempfile, unittest

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
        # the agent's own Bash/R/Python subprocesses must not inherit the token (it would reach published transcripts)
        self.assertEqual(env["CLAUDE_CODE_SUBPROCESS_ENV_SCRUB"], "1")
        self.assertIn("PATH", env)


class ToolPermissions(unittest.TestCase):
    """CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1 forces Claude Code's permission mode to `default`, which ignores
    --permission-mode bypassPermissions and denies every tool in a headless run. Every arm must therefore carry an
    explicit allow-list that covers every tool the agent is shown (logs/deviations.md §16)."""
    INIT_TOOLS = ["Bash", "Edit", "Read", "Write", "Skill", "Task", "ToolSearch", "NotebookEdit"]
    MCP = ["ListMcpResourcesTool", "ReadMcpResourceTool", "ReadMcpResourceDirTool",
           "mcp__pmxagent__health", "mcp__pmxagent__r_Noncompartmental_analysis_NCA"]

    def flag_values(self, cmd, flag):
        i = cmd.index(flag) + 1
        out = []
        while i < len(cmd) and not cmd[i].startswith("--"):
            out.append(cmd[i]); i += 1
        return out

    def test_every_arm_has_explicit_allow_list_and_keeps_git_web_denied(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "wt"))   # a rep's worktree exists before claude_cmd writes the A1 MCP config
            for arm in run_arm.ARMS:
                cmd = run_arm.claude_cmd(arm, "m", os.path.join(d, "wt"))
                self.assertNotIn("bypassPermissions", cmd)
                allowed = self.flag_values(cmd, "--allowedTools")
                self.assertEqual(allowed, list(run_arm.allowed_tools(arm)))
                self.assertEqual(run_arm.uncovered_tools(self.INIT_TOOLS, allowed), [])
                self.assertEqual(self.flag_values(cmd, "--disallowedTools"),
                                 ["WebSearch", "WebFetch", "Bash(git:*)", "Bash(gh:*)"])

    def test_mcp_tools_allowed_only_for_A1(self):
        self.assertEqual(run_arm.uncovered_tools(self.INIT_TOOLS + self.MCP, run_arm.allowed_tools("A1")), [])
        self.assertEqual(run_arm.uncovered_tools(self.MCP, run_arm.allowed_tools("A0")), self.MCP)

    def test_uncovered_tools_matches_names_and_server_prefixes_exactly(self):
        allowed = ("Bash", "mcp__pmxagent")
        self.assertEqual(run_arm.uncovered_tools(["Bash", "BashOutput", "mcp__pmxagent__nca", "mcp__other__x"],
                                                 allowed), ["BashOutput", "mcp__other__x"])


class ParseTranscript(unittest.TestCase):
    def test_counts_tools_errors_denials_and_reads_init(self):
        lines = [{"type": "system", "subtype": "init", "permissionMode": "default", "tools": ["Bash", "Write"]},
                 {"type": "assistant", "message": {"content": [{"type": "tool_use"}, {"type": "text"}]}},
                 {"type": "user", "message": {"content": [{"type": "tool_result", "is_error": True}]}},
                 {"type": "result", "is_error": False, "permission_denials": [{"tool_name": "Bash"}]}]
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "t.jsonl")
            open(p, "w").write("\n".join(json.dumps(x) for x in lines) + "\nnot json\n")
            t = run_arm.parse_transcript(p)
        self.assertEqual((t["tool_calls"], t["tool_errors"], t["permission_denials"]), (1, 1, 1))
        self.assertEqual(t["init"]["permissionMode"], "default")
        self.assertEqual(t["result"]["is_error"], False)


class PreflightGate(unittest.TestCase):
    """A preflight must prove a tool actually runs, not only list what is in context."""
    INIT = {"permissionMode": "default", "tools": ["Bash", "Read", "Write"]}

    def test_clean_probe_passes(self):
        self.assertEqual(run_arm.preflight_problems("A0", self.INIT, 0, "", True), [])

    def test_each_failure_is_reported(self):
        self.assertTrue(run_arm.preflight_problems("A0", self.INIT, 1, "", True))               # a denial
        self.assertTrue(run_arm.preflight_problems("A0", self.INIT, 0, "", False))              # probe file missing
        self.assertTrue(run_arm.preflight_problems(
            "A0", self.INIT, 0, "⚠ Permission mode forced to default — CLAUDE_CODE_SUBPROCESS_ENV_SCRUB", True))
        self.assertTrue(run_arm.preflight_problems(
            "A0", {"tools": ["Bash", "mcp__pmxagent__health"]}, 0, "", True))                  # tool not allowed
        self.assertTrue(run_arm.preflight_problems("A0", {}, 0, "", True))                      # no init event


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
