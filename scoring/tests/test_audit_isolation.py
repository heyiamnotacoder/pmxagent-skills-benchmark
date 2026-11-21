"""Isolation audit: A1's shared PMxAgent folders count as the run's own only when the harness emptied them first
(pmx_root.json, logs/deviations.md §20); the rep's own HOME is never a Claude-state hit.
Run: python3 -m unittest discover -s scoring/tests"""
import json, os, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import audit_isolation as ai

RID = "A1_T2_case_r14_20261121-130000"
PMX = "/Users/u/pmxbench_runs/_pmxagent"


def transcript(d, *commands):
    p = os.path.join(d, "transcript.jsonl")
    with open(p, "w") as f:
        for c in commands:
            f.write(json.dumps({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Bash", "input": {"command": c}}]}}) + "\n")
    return p


class SharedPmxFolder(unittest.TestCase):
    CMDS = (f"ls {PMX}/data/", f"cp {PMX}/data/pk_simulation_1.csv output/", f"ls {PMX}/figures/x/")

    def test_flagged_without_the_clean_record(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(ai.audit_run(transcript(d, *self.CMDS), RID)["run_area"], 3)

    def test_own_once_the_harness_emptied_it(self):
        with tempfile.TemporaryDirectory() as d:
            json.dump({"emptied_before_start": True}, open(os.path.join(d, "pmx_root.json"), "w"))
            hits = ai.audit_run(transcript(d, *self.CMDS, f"cat {PMX}/apis/endpoints/x.R"), RID)
            self.assertEqual(hits["run_area"], 1)   # PMxAgent's own source is still outside the run

    def test_own_home_claude_state_is_not_a_hit_but_another_is(self):
        with tempfile.TemporaryDirectory() as d:
            own = f"cat /Users/Shared/pmxbench_runs/A1/runs/{RID}.home/.claude/projects/p/tool-results/x.txt"
            self.assertEqual(ai.audit_run(transcript(d, own), RID)["claude_state"], 0)
            self.assertEqual(ai.audit_run(transcript(d, "ls ~/.claude/projects/"), RID)["claude_state"], 1)

    def test_a1b_runid_and_run_area_are_matched_like_a1(self):
        rid = "A1b_T1_nca_r01_20261121-150000"
        other = "A1b_T1_nca_r02_20261121-151000"
        with tempfile.TemporaryDirectory() as d:
            json.dump({"emptied_before_start": True}, open(os.path.join(d, "pmx_root.json"), "w"))
            own_cmd = f"ls /Users/Shared/pmxbench_runs/A1b/runs/{rid}/inputs/ && ls {PMX}/data/{rid}/"
            sib_cmd = f"ls /Users/Shared/pmxbench_runs/A1b/runs/{other}/"
            self.assertEqual(ai.audit_run(transcript(d, own_cmd), rid)["run_area"], 0)
            hits = ai.audit_run(transcript(d, sib_cmd), rid)
            self.assertEqual((hits["other_run_id"], hits["run_area"]), (1, 1))


if __name__ == "__main__":
    unittest.main()
