"""resume_lanes.sh acts on the lanes' exit code (0 done, 75 wait for a reset, else stop), refuses to run inside a
Claude session and runs one copy at a time (logs/deviations.md §19). Stubs stand in for the lanes and the pool.
Run: python3 -m unittest discover -s harness/tests"""
import os, shutil, subprocess, tempfile, time, unittest

HARNESS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANES_STUB = """#!/usr/bin/env bash
n=$(cat "$STUB/calls" 2>/dev/null || echo 0); n=$((n + 1)); echo $n > "$STUB/calls"
codes=($STUB_CODES); exit ${codes[$((n - 1))]}
"""
TOKENS_STUB = """import os, sys, time
if sys.argv[1:] == ["next-free"]:
    print(int(time.time()) + int(os.environ.get("STUB_FREE_IN", "0")))
"""


class ResumeLanes(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.d, "harness")); os.makedirs(os.path.join(self.d, "logs"))
        shutil.copy(os.path.join(HARNESS, "resume_lanes.sh"), os.path.join(self.d, "harness"))
        open(os.path.join(self.d, "harness", "run_t2_t3_lanes.sh"), "w").write(LANES_STUB)
        open(os.path.join(self.d, "harness", "tokens.py"), "w").write(TOKENS_STUB)

    def tearDown(self):
        shutil.rmtree(self.d)

    def run_wrapper(self, codes, free_in=0, **extra):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE", "ANTHROPIC"))}
        env.update(STUB=self.d, STUB_CODES=codes, STUB_FREE_IN=str(free_in), RESUME_MARGIN_S="1",
                   RESUME_RETRY_S="1", RESUME_POLL_S="1", RESUME_MAX_ROUNDS="4", **extra)
        t0 = time.time()
        p = subprocess.run(["bash", os.path.join(self.d, "harness", "resume_lanes.sh")], env=env,
                           capture_output=True, text=True, timeout=60)
        calls = int(open(os.path.join(self.d, "calls")).read()) if os.path.exists(os.path.join(self.d, "calls")) else 0
        return p.returncode, calls, time.time() - t0, p.stdout + p.stderr

    def test_limit_then_done_waits_for_the_reset_and_finishes(self):
        rc, calls, took, out = self.run_wrapper("75 0", free_in=2)
        self.assertEqual((rc, calls), (0, 2), out)
        self.assertGreaterEqual(took, 2, out)                  # really waited for the reset (+ margin)
        self.assertFalse(os.path.exists(os.path.join(self.d, "logs", ".resume_lanes.lock")))

    def test_broken_lanes_stop_at_once_with_their_code(self):
        rc, calls, _, out = self.run_wrapper("3 0")
        self.assertEqual((rc, calls), (3, 1), out)

    def test_gives_up_after_max_rounds(self):
        rc, calls, _, out = self.run_wrapper("75 75 75 75 75")
        self.assertEqual((rc, calls), (1, 4), out)

    def test_refuses_inside_a_claude_session_and_a_second_copy(self):
        rc, calls, _, _ = self.run_wrapper("0", CLAUDECODE="1")
        self.assertEqual((rc, calls), (2, 0))
        lock = os.path.join(self.d, "logs", ".resume_lanes.lock"); os.makedirs(lock)
        open(os.path.join(lock, "pid"), "w").write(str(os.getpid()))   # a live process holds it
        rc, calls, _, _ = self.run_wrapper("0")
        self.assertEqual((rc, calls), (2, 0))
        open(os.path.join(lock, "pid"), "w").write("999999")           # stale lock is taken over
        rc, calls, _, out = self.run_wrapper("0")
        self.assertEqual((rc, calls), (0, 1), out)


if __name__ == "__main__":
    unittest.main()
