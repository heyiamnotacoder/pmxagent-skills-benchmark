"""Harness unit tests: ledger writes, rep counting, isolation, tool permissions, preflight gate.
Run: python3 -m unittest discover -s harness/tests"""
import csv, hashlib, json, os, sys, tempfile, unittest
from unittest import mock

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
            os.environ.update(ANTHROPIC_BASE_URL="http://host-proxy", CLAUDE_CODE_CHILD_SESSION="1")
            env, mode = run_arm.run_env(os.path.join(d, "wt"), run_arm.tokens.Account("acct1", "x"))
        self.assertEqual(mode, "isolated")
        self.assertFalse([k for k in env if k.startswith("ANTHROPIC") or k == "CLAUDE_CODE_CHILD_SESSION"])
        self.assertEqual(env["HOME"], os.path.join(d, "wt.home"))
        self.assertEqual(env["CLAUDE_CODE_OAUTH_TOKEN"], "x")
        # the agent's own Bash/R/Python subprocesses must not inherit the token (it would reach published transcripts)
        self.assertEqual(env["CLAUDE_CODE_SUBPROCESS_ENV_SCRUB"], "1")
        self.assertIn("PATH", env)


    def test_no_account_is_the_keychain_login_mode(self):
        with tempfile.TemporaryDirectory() as d:
            env, mode = run_arm.run_env(os.path.join(d, "wt"), None)
        self.assertEqual(mode, "user")
        self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN", env)


class NextStep(unittest.TestCase):
    """--until after a rep: switch account on a 429 or bad token while another is free; never spin; else stop."""

    def pool(self, d, limited=()):
        tok = os.path.join(d, "tokens"); os.makedirs(tok, exist_ok=True)
        for lab in ("acct1", "acct2"):
            open(os.path.join(tok, lab), "w").write(lab)
        p = run_arm.tokens.Pool.load(tokens_dir=tok, single_file=os.path.join(d, "x"),
                                     limits_file=os.path.join(d, "limits.json"))
        for lab in limited:
            p.mark_limited(lab, 4e9)
        return p

    def row(self, status="ok", is_error=False, cost=0.5, api=None):
        return {"status": status, "is_error": is_error, "cost_usd": cost, "api_error_status": api}

    def test_valid_rep_resets_counters(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(run_arm.next_step(self.row(), 1, 1, self.pool(d)), ("go", 0, 0))

    def test_usage_limit_switches_while_another_account_is_free_then_stops(self):
        with tempfile.TemporaryDirectory() as d:
            hit = self.row("failed_ratelimit_midrun", True, 0.1, 429)
            self.assertEqual(run_arm.next_step(hit, 0, 0, self.pool(d, ["acct1"])), ("switch", 1, 1))
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(run_arm.next_step(hit, 1, 1, self.pool(d, ["acct1", "acct2"]))[0], "stop")

    def test_switches_are_bounded_by_pool_size(self):
        with tempfile.TemporaryDirectory() as d:   # a stale reset time leaves an account "free": must not spin
            hit = self.row("failed_ratelimit", True, None, 429)
            self.assertEqual(run_arm.next_step(hit, 2, 2, self.pool(d))[0], "stop")

    def test_bad_token_switches_and_other_failures_follow_the_old_rule(self):
        with tempfile.TemporaryDirectory() as d:
            pool = self.pool(d, ["acct1"])
            self.assertEqual(run_arm.next_step(self.row("exit1", True, None, 401), 0, 0, pool)[0], "switch")
            api = self.row("exit1", True, None, 500)                                  # instant API failure
            self.assertEqual(run_arm.next_step(api, 0, 0, pool)[0], "go")
            self.assertEqual(run_arm.next_step(api, 1, 0, pool)[0], "stop")
            self.assertEqual(run_arm.next_step(self.row("timeout", False, 0.8), 0, 0, pool), ("go", 0, 0))


class LimitStop(unittest.TestCase):
    def test_usage_limit_stop_exits_75_so_the_wrapper_waits_instead_of_finishing(self):
        with self.assertRaises(SystemExit) as cm:
            run_arm.limit_stop("A0 T2_case: usage limit")
        self.assertEqual(cm.exception.code, 75)


class ToolPermissions(unittest.TestCase):
    """CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1 forces Claude Code's permission mode to `default`, which ignores
    --permission-mode bypassPermissions and denies every tool in a headless run. Every arm must therefore carry an
    explicit allow-list (logs/deviations.md §16). The live check that it covers every tool shown is `preflight`."""
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
                self.assertEqual(run_arm.uncovered_tools(self.INIT_TOOLS, allowed), [])
                self.assertEqual(self.flag_values(cmd, "--disallowedTools"),
                                 ["WebSearch", "WebFetch", "Bash(git:*)", "Bash(gh:*)"])

    def test_mcp_tools_allowed_only_for_pmx_arms(self):
        for arm in ("A1", "A1b"):
            self.assertEqual(run_arm.uncovered_tools(self.INIT_TOOLS + self.MCP, run_arm.allowed_tools(arm)), [])
        self.assertEqual(run_arm.uncovered_tools(self.MCP, run_arm.allowed_tools("A0")), self.MCP)

    def test_a1b_verifies_pmx_claude_md_sha256(self):
        with tempfile.TemporaryDirectory() as d:
            good = os.path.join(d, "CLAUDE.md")
            open(good, "w").write("# PMxAgent CLAUDE.md fixture\n")
            digest = hashlib.sha256(open(good, "rb").read()).hexdigest()
            with mock.patch.object(run_arm, "PMX_CLAUDE_MD_SHA256", digest):
                self.assertEqual(run_arm.verify_pmx_claude_md(good), good)
            bad = os.path.join(d, "CLAUDE_bad.md")
            open(bad, "w").write("tampered\n")
            with self.assertRaises(SystemExit):
                run_arm.verify_pmx_claude_md(bad)

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
            tr = run_arm.parse_transcript(p)
        self.assertEqual((tr.tool_calls, tr.tool_errors, tr.permission_denials), (1, 1, 1))
        self.assertEqual(tr.denied, ["Bash"])
        self.assertEqual(tr.init["permissionMode"], "default")
        self.assertEqual(tr.result["is_error"], False)


class PreflightGate(unittest.TestCase):
    """A preflight must prove a tool runs and that the git deny rule still wins, not only list what is in context."""
    INIT = {"type": "system", "subtype": "init", "permissionMode": "default", "tools": ["Bash", "Read", "Write"]}
    GIT = {"tool_name": "Bash", "tool_input": {"command": "git --version"}}

    def probe(self, d, init=INIT, denials=(GIT,), stderr="", probe_file=True):
        """A raw preflight folder as run_once leaves it."""
        os.makedirs(os.path.join(d, "output"), exist_ok=True)
        if probe_file:
            open(os.path.join(d, "output", run_arm.PREFLIGHT_FILE), "w").write("ok\n")
        open(os.path.join(d, "stderr.txt"), "w").write(stderr)
        events = ([init] if init else []) + [{"type": "result", "permission_denials": list(denials)}]
        open(os.path.join(d, "transcript.jsonl"), "w").write("\n".join(json.dumps(e) for e in events))
        return d

    def problems(self, **kw):
        with tempfile.TemporaryDirectory() as d:
            return run_arm.preflight_problems("A0", self.probe(d, **kw))

    def test_clean_probe_passes(self):
        self.assertEqual(self.problems(), [])

    def test_each_failure_is_reported(self):
        self.assertTrue(self.problems(denials=(self.GIT, {"tool_name": "Write", "tool_input": {}})))  # other denial
        self.assertTrue(self.problems(denials=()))                       # git ran: the deny rule no longer wins
        self.assertTrue(self.problems(probe_file=False))                 # the Bash call did not run
        self.assertTrue(self.problems(stderr="⚠ Permission mode forced to default — CLAUDE_CODE_SUBPROCESS_ENV_SCRUB"))
        self.assertTrue(self.problems(init=dict(self.INIT, tools=["Bash", "mcp__pmxagent__health"])))  # not allowed
        self.assertTrue(self.problems(init=None))                        # no init event


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
