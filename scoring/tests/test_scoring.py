"""Tests for the parts of scoring that must hold when only some runs' raw files are on this machine.

T1 raw files live on Zenodo, not in results/raw/, so re-scoring T2 must keep the committed T1 rows.
Run: python3 -m unittest discover -s scoring/tests
"""
import csv, json, math, os, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import runstore
import score_all
import summarize


def write_csv(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


class MergeRows(unittest.TestCase):
    def test_keeps_rows_not_rescanned_and_replaces_rescanned(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "scores.csv")
            write_csv(p, [{"runid": "t1", "overall": "98.64"}, {"runid": "t2", "overall": "1"}])
            runstore.merge_rows(p, [{"runid": "t2", "overall": "", "ec50": "50"}], rescanned={"t2"})
            rows = list(csv.DictReader(open(p)))
        self.assertEqual([r["runid"] for r in rows], ["t1", "t2"])
        self.assertEqual(rows[0]["overall"], "98.64")
        self.assertEqual(rows[1]["ec50"], "50")

    def test_rescanned_run_that_no_longer_scores_is_dropped(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "scores.csv")
            write_csv(p, [{"runid": "t1", "overall": "98"}])
            runstore.merge_rows(p, [], rescanned={"t1"})
            self.assertEqual(list(csv.DictReader(open(p))), [])


class OutputHashes(unittest.TestCase):
    def test_falls_back_to_evidence_manifest_when_raw_is_absent(self):
        with tempfile.TemporaryDirectory() as d:
            man = os.path.join(d, "MANIFEST.sha256")
            open(man, "w").write("aa  results/raw/A3/T1_nca/run1/output/x.csv\n"
                                 "bb  results/raw/A3/T1_nca/run1/output/sub/y.csv\n"
                                 "cc  results/raw/A3/T1_nca/run1/transcript.jsonl\n"
                                 "dd  results/raw/A3/T1_nca/run10/output/x.csv\n")
            h = runstore.output_hashes("A3", "T1_nca", "run1", raw=os.path.join(d, "raw"), manifests=[man])
        self.assertEqual(h, {"x.csv": "aa", os.path.join("sub", "y.csv"): "bb"})

    def test_prefers_local_raw(self):
        with tempfile.TemporaryDirectory() as d:
            rd = os.path.join(d, "raw", "A3", "T2_case", "run1")
            os.makedirs(rd)
            json.dump({"r.json": "ff"}, open(os.path.join(rd, "output_sha256.json"), "w"))
            self.assertEqual(runstore.output_hashes("A3", "T2_case", "run1", raw=os.path.join(d, "raw"), manifests=[]),
                             {"r.json": "ff"})


def bolus_profiles(dose, n, times):
    """Analytical 1-CM bolus, CL=1, V=10: AUC0-last and Cmax are exact functions of the dose."""
    return [(f"{dose}-{i}", t, dose / 10 * math.exp(-0.1 * t)) for i in range(n) for t in times]


class ScoreCase(unittest.TestCase):
    def test_finds_A1_simulation_in_pmxagent_data_via_container_path(self):
        times = [0.5, 1, 2, 4, 8, 12, 24]
        with tempfile.TemporaryDirectory() as run:
            os.makedirs(os.path.join(run, "output")); os.makedirs(os.path.join(run, "pmxagent_data", "sim"))
            rows = [{"ID": s, "TIME": t, "DV": c, "DOSE": d}
                    for d in (10, 30, 100) for s, t, c in bolus_profiles(d, 20, times)]
            write_csv(os.path.join(run, "pmxagent_data", "sim", "pk_sim.csv"), rows)
            gs = []
            for d in (10, 30, 100):
                prof = [(t, c) for s, t, c in bolus_profiles(d, 1, times)]
                gs.append({"dose_mg": d, "mean_AUClast": score_all.auclast_lulog(*zip(*prof)),
                           "mean_Cmax": max(c for _, c in prof), "mean_half_life": math.log(2) / 0.1})
            json.dump({"group_summary": gs, "ec50": 300.0, "ec50_units": "mg*h/L", "seed": 1,
                       "n_timepoints_per_subject": 7, "pk_parameters": {"CL": 1},
                       "files": {"simulated": "/data/A1_T2_case_r01_x/sim/pk_sim.csv"}},
                      open(os.path.join(run, "output", "results.json"), "w"))
            r = score_all.score_case_run(run)
        self.assertTrue(r["completed"])
        self.assertEqual(r["n_subjects_sim"], 60)
        self.assertEqual(r["summary_consistent_pct"], 100.0)
        self.assertEqual(r["summary_consistent_any_rule_pct"], 100.0)
        self.assertEqual(r["sim_file"], os.path.join("pmxagent_data", "sim", "pk_sim.csv"))
        self.assertEqual(r["auc_method"], "lin-up/log-down")

    def test_linear_trapezoidal_summary_primary_vs_any_rule(self):
        """Primary (pre-specified, commit 08ea7b3): AUClast recomputed lin-up/log-down only, so a linear-rule summary
        matches on Cmax but not AUC (3 of 6 checks). Post-hoc sensitivity (deviations §13): either rule counts."""
        times = [0, 1, 2, 4, 8, 24]
        with tempfile.TemporaryDirectory() as run:
            os.makedirs(os.path.join(run, "output"))
            rows = [{"subject_id": s, "time_h": t, "conc": c, "dose_mg": d}
                    for d in (10, 30, 100) for s, t, c in bolus_profiles(d, 20, times)]
            write_csv(os.path.join(run, "output", "sim.csv"), rows)
            gs = []
            for d in (10, 30, 100):
                t, c = zip(*[(t, c) for _, t, c in bolus_profiles(d, 1, times)])
                lin = sum((t[i + 1] - t[i]) * (c[i] + c[i + 1]) / 2 for i in range(len(t) - 1))
                self.assertGreater(lin / score_all.auclast_lulog(t, c), 1.01)   # the two rules really differ here
                gs.append({"dose_mg": d, "mean_AUClast": lin, "mean_Cmax": max(c), "mean_half_life": 6.93})
            json.dump({"group_summary": gs, "ec50": 20.0, "files": {"sim": "output/sim.csv"}},
                      open(os.path.join(run, "output", "results.json"), "w"))
            r = score_all.score_case_run(run)
        self.assertEqual(r["summary_consistent_pct"], 50.0)
        self.assertEqual(r["summary_consistent_any_rule_pct"], 100.0)
        self.assertEqual(r["auc_method"], "linear")

    def test_no_dose_compared_is_auc_method_none(self):
        """Summary doses that match no simulated dose: nothing compared, so no rule can be named."""
        times = [0, 1, 2, 4, 8, 24]
        with tempfile.TemporaryDirectory() as run:
            os.makedirs(os.path.join(run, "output"))
            rows = [{"subject_id": s, "time_h": t, "conc": c, "dose_mg": d}
                    for d in (10, 30, 100) for s, t, c in bolus_profiles(d, 20, times)]
            write_csv(os.path.join(run, "output", "sim.csv"), rows)
            gs = [{"dose_mg": d, "mean_AUClast": 1.0, "mean_Cmax": 1.0} for d in (5, 50, 500)]
            json.dump({"group_summary": gs, "ec50": 20.0, "files": {"sim": "output/sim.csv"}},
                      open(os.path.join(run, "output", "results.json"), "w"))
            r = score_all.score_case_run(run)
        self.assertEqual(r["auc_method"], "none")
        self.assertIsNone(r["summary_consistent_pct"])


class UnscorableNca(unittest.TestCase):
    """A completed NCA run whose individual file has no subject keys scores 0 on every parameter (SPEC: every
    completed run counts), not only on `overall` (logs/deviations.md §17)."""

    def test_drug_only_ids_score_zero_on_every_parameter(self):
        with tempfile.TemporaryDirectory() as d:
            ref = {("abatacept_1", p): 10.0 for p in score_all.sn.PARAMS}
            ref[("abatacept_1", "R2ADJ")], ref[("abatacept_1", "NPTS")] = 0.99, 3.0
            run = os.path.join(d, "run"); os.makedirs(os.path.join(run, "output"))
            write_csv(os.path.join(run, "output", "nca_individual.csv"),
                      [{"DRUG": "abatacept", "PPTESTCD": "Cmax", "PPSTRESN": 10}])
            r = score_all.score_nca_dir(run, ref)
        self.assertEqual((r["scored_file"], r["coverage_pct"], r["overall"]), ("", 0.0, 0.0))
        self.assertEqual(r["note"], "no scorable individual file")
        for p in score_all.sn.PARAMS:
            self.assertEqual(r[f"{p}_pct"], 0.0, p)


class PmxagentToolCalls(unittest.TestCase):
    def test_counts_only_pmxagent_mcp_tool_uses(self):
        with tempfile.TemporaryDirectory() as run:
            ev = [{"type": "system", "subtype": "init"},
                  {"type": "assistant", "message": {"content": [
                      {"type": "tool_use", "name": "ToolSearch", "input": {}},
                      {"type": "tool_use", "name": "mcp__pmxagent__r_Noncompartmental_analysis_NCA", "input": {}},
                      {"type": "text", "text": "mcp__pmxagent__health"}]}},
                  {"type": "assistant", "message": {"content": [
                      {"type": "tool_use", "name": "mcp__pmxagent__health", "input": {}},
                      {"type": "tool_use", "name": "Bash", "input": {}}]}}]
            open(os.path.join(run, "transcript.jsonl"), "w").write("\n".join(json.dumps(e) for e in ev) + "\nnot json\n")
            self.assertEqual(score_all.pmxagent_tool_calls(run), 2)

    def test_no_transcript_is_none(self):
        with tempfile.TemporaryDirectory() as run:
            self.assertIsNone(score_all.pmxagent_tool_calls(run))
            self.assertIsNone(score_all.pmxagent_http_calls(run))

    def test_counts_direct_plumber_http_endpoint_calls_only(self):
        with tempfile.TemporaryDirectory() as run:
            ev = [{"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Bash",
                 "input": {"command": "curl -X POST http://localhost:5762/NCA -d data_file=x.csv"}},
                {"type": "tool_use", "name": "Bash",
                 "input": {"command": "curl http://127.0.0.1:5762/PK -d dose=10"}},
                {"type": "tool_use", "name": "Write",
                 "input": {"file_path": "run.py", "content": "requests.post('http://localhost:5762/NCA')"}},
                {"type": "tool_use", "name": "Bash",
                 "input": {"command": "grep localhost:5762/NCA CLAUDE.md"}},
                {"type": "tool_use", "name": "Bash",
                 "input": {"command": "curl http://localhost:5762/__docs__/"}},
                {"type": "text", "text": "http://localhost:5762/NCA"}]}}]
            open(os.path.join(run, "transcript.jsonl"), "w").write("\n".join(json.dumps(e) for e in ev))
            self.assertEqual(score_all.pmxagent_http_calls(run), 3)


class SummarizeOutcomes(unittest.TestCase):
    def test_separates_ratelimit_crash_and_protocol_exclusions(self):
        rows = [
            {"runid": "r1", "arm": "A1", "task": "T3a_messy", "status": "ok", "is_error": "False"},
            {"runid": "r2", "arm": "A1", "task": "T3a_messy", "status": "failed_ratelimit", "is_error": "True"},
            {"runid": "r3", "arm": "A1", "task": "T3a_messy", "status": "exit1", "is_error": "False"},
            {"runid": "r4", "arm": "A1", "task": "T3a_messy", "status": "timeout", "is_error": "False"},
            {"runid": "r5", "arm": "A1", "task": "T3a_messy", "status": "ok", "is_error": "False"},
        ]
        n_rl, n_crash, n_excl = summarize.count_outcomes(rows, excluded={"r5"})
        k = ("A1", "T3a_messy")
        self.assertEqual((n_rl[k], n_crash[k], n_excl[k]), (1, 2, 1))


if __name__ == "__main__":
    unittest.main()
