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
        self.home = os.path.join(self.tmp.name, "home")   # ~/pmxbench_runs resolves here
        os.makedirs(self.bin); os.makedirs(self.home)

    def tearDown(self):
        self.tmp.cleanup()

    def stub(self, version):
        p = os.path.join(self.bin, "claude")
        with open(p, "w") as f:
            f.write(f"#!/bin/sh\necho '{version} (Claude Code)'\n")
        os.chmod(p, 0o755)

    def run_arm(self, *args):
        env = dict(os.environ, PATH=self.bin + os.pathsep + os.environ["PATH"], HOME=self.home)
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
        self.assertEqual(run_arm.pinned_claude_version(), PIN)


if __name__ == "__main__":
    unittest.main()
