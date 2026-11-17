"""run_arm.py must refuse to run on a Claude Code version other than the one pinned in env/versions.txt (issue #3).

A stub `claude` on PATH prints the version; no real Claude session is started.
Run: python3 -m unittest discover -s harness/tests -v
"""
import hashlib, os, re, subprocess, sys, tempfile, unittest

HARNESS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(HARNESS)
RUN_ARM = os.path.join(HARNESS, "run_arm.py")
LEDGER = os.path.join(ROOT, "results", "runs.csv")
with open(os.path.join(ROOT, "env", "versions.txt")) as _f:
    PIN = re.search(r"^claude-code:\s*(\S+)", _f.read(), re.M).group(1)


def sha(p):
    if not os.path.exists(p):
        return None
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


class VersionPin(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bin = os.path.join(self.tmp.name, "bin")
        self.home = os.path.join(self.tmp.name, "home")
        self.runs = os.path.join(self.tmp.name, "runs")   # private empty run root: no arm repo, so a run that gets
        os.makedirs(self.bin); os.makedirs(self.home)     # past the guard fails before any worktree or ledger write
        os.makedirs(self.runs, mode=0o700)
        self.ledger_before = sha(LEDGER)

    def tearDown(self):
        self.tmp.cleanup()
        self.assertEqual(sha(LEDGER), self.ledger_before, "a test wrote to the real ledger")

    def stub(self, version):
        p = os.path.join(self.bin, "claude")
        with open(p, "w") as f:
            f.write(f"#!/bin/sh\necho '{version} (Claude Code)'\n")
        os.chmod(p, 0o755)

    def run_arm(self, *args):
        env = dict(os.environ, PATH=self.bin + os.pathsep + os.environ["PATH"], HOME=self.home, PMXBENCH_RUNS=self.runs)
        return subprocess.run([sys.executable, RUN_ARM, *args], env=env, capture_output=True, text=True, timeout=60)

    def test_mismatch_refused_before_any_side_effect(self):
        self.stub("9.9.9")
        before = sha(LEDGER)
        for cmd in (["run", "A0", "T1_nca", "1", "claude-sonnet-4-6"], ["preflight", "A0", "claude-sonnet-4-6"]):
            r = self.run_arm(*cmd)
            self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("9.9.9", r.stderr)
            self.assertIn(PIN, r.stderr)
            self.assertIn("--allow-version-drift", r.stderr)
        self.assertEqual(sha(LEDGER), before, "ledger was written")
        self.assertEqual(os.listdir(self.home), [], "a run/worktree directory was created")
        self.assertEqual(os.listdir(self.runs), [], "a run/worktree directory was created")

    def test_match_passes_the_check(self):
        self.stub(PIN)
        r = self.run_arm("run", "A0", "T1_nca", "1", "claude-sonnet-4-6")
        # it gets past the version check and fails later (no arm repo in the temp HOME); the guard must stay silent
        self.assertNotIn("pinned to", r.stderr)

    def test_drift_allowed_with_warning(self):
        self.stub("9.9.9")
        r = self.run_arm("run", "A0", "T1_nca", "1", "claude-sonnet-4-6", "--allow-version-drift")
        self.assertIn("WARNING", r.stderr)
        self.assertIn("logs/deviations.md", r.stderr)
        self.assertNotIn("Install the pinned version", r.stderr)

    def test_setup_needs_no_claude(self):
        sys.path.insert(0, HARNESS)
        import run_arm
        self.assertEqual(run_arm.pinned_claude_version("T1_nca"), PIN)

    # --- per-task pin (logs/deviations.md §15): T1 stays on its version, T2/T3 use the `default` pin ---
    def pinned_install(self, version):
        """A harness-owned pinned binary: <PMXBENCH_CLAUDE_DIR>/<version>/claude."""
        d = os.path.join(self.tmp.name, "pins", version)
        os.makedirs(d)
        p = os.path.join(d, "claude")
        with open(p, "w") as f:
            f.write(f"#!/bin/sh\necho '{version} (Claude Code)'\n")
        os.chmod(p, 0o755)

    def run_arm_pins(self, *args):
        env = dict(os.environ, PATH=self.bin + os.pathsep + os.environ["PATH"], HOME=self.home, PMXBENCH_RUNS=self.runs,
                   PMXBENCH_CLAUDE_DIR=os.path.join(self.tmp.name, "pins"))
        return subprocess.run([sys.executable, RUN_ARM, *args], env=env, capture_output=True, text=True, timeout=60)

    def test_pin_differs_by_task(self):
        sys.path.insert(0, HARNESS)
        import run_arm
        default = run_arm.pinned_claude_version("T2_case")
        self.assertNotEqual(default, PIN)
        self.assertEqual(run_arm.pinned_claude_version("T3d_oral"), default)

    def test_pinned_install_preferred_over_path(self):
        self.stub("9.9.9")                      # whatever `claude` on PATH is, the pinned binary is used
        self.pinned_install(PIN)
        r = self.run_arm_pins("run", "A0", "T1_nca", "1", "claude-sonnet-4-6")
        self.assertNotIn("pinned to", r.stderr)

    def test_preflight_probes_the_pin_of_the_given_task(self):
        sys.path.insert(0, HARNESS)
        import run_arm
        self.stub("9.9.9")
        self.pinned_install(PIN)                # T1 pin only: a T2 preflight must ask for the default pin
        r = self.run_arm_pins("preflight", "A0", "claude-sonnet-4-6", "T2_case")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn(run_arm.pinned_claude_version("T2_case"), r.stderr)

    def test_task_with_other_pin_refused(self):
        sys.path.insert(0, HARNESS)
        import run_arm
        self.stub("9.9.9")
        self.pinned_install(PIN)                # only the T1 pin is installed; T2 needs the default pin
        r = self.run_arm_pins("run", "A0", "T2_case", "1", "claude-sonnet-4-6")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn(run_arm.pinned_claude_version("T2_case"), r.stderr)


if __name__ == "__main__":
    unittest.main()
