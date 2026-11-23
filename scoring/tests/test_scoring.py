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

    def test_cdisc_subjid_column_is_read(self):
        """SUBJID (CDISC) names the subject in 3 A2 T2 runs that were 'sim file not parseable' (deviations §25)."""
        times = [0, 1, 2, 4, 8, 24]
        with tempfile.TemporaryDirectory() as run:
            os.makedirs(os.path.join(run, "output"))
            rows = [{"SUBJID": s, "DOSE_MG": d, "time": t, "CONC": c}
                    for d in (10, 30, 100) for s, t, c in bolus_profiles(d, 20, times)]
            write_csv(os.path.join(run, "output", "sim.csv"), rows)
            gs = []
            for d in (10, 30, 100):
                t, c = zip(*[(t, c) for _, t, c in bolus_profiles(d, 1, times)])
                gs.append({"dose_mg": d, "mean_AUClast": score_all.auclast_lulog(t, c), "mean_Cmax": max(c)})
            json.dump({"group_summary": gs, "ec50": 20.0}, open(os.path.join(run, "output", "results.json"), "w"))
            r = score_all.score_case_run(run)
        self.assertEqual(r["n_subjects_sim"], 60)
        self.assertEqual(r["summary_consistent_pct"], 100.0)


class Ec50Units(unittest.TestCase):
    """EC50 in h·µg/mL (= h·mg/L), the unit of PMxAgent's case-study result, for a descriptive comparison (§25).
    Cases are unit strings the T2 runs actually wrote."""
    def test_converts_auc_units(self):
        cases = {"mg*h/L": 1, "mg/L*h (AUClast at 50% response probability)": 1, "h*mg/L (AUClast units)": 1,
                 "(mg/L)*h": 1, "h·mg/L (AUC 0-last)": 1, "h*ug/mL": 1, "µg·h/mL (AUClast)": 1, "h·µg/mL": 1,
                 "mg*day/L": 24, "mg·day/L (AUClast)": 24, "ng*h/mL": 0.001, "ng·h/mL (AUC)": 0.001,
                 "AUC (ng/mL * h)": 0.001, "h*ng/mL": 0.001, "mg h/L": 1}
        for units, k in cases.items():
            self.assertAlmostEqual(score_all.ec50_h_ug_per_ml(10.0, units), 10.0 * k, msg=units)

    def test_not_an_auc_unit_is_none(self):
        for units in ("dose_unit/L (mg/L)", "", None, "mg/L", "h", "ng/mL/h", "mg/(L*h)", "mg/L/day"):
            self.assertIsNone(score_all.ec50_h_ug_per_ml(10.0, units), msg=units)
        self.assertIsNone(score_all.ec50_h_ug_per_ml(None, "mg*h/L"))


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


class TerminalPointBreakdown(unittest.TestCase):
    """Terminal-point match and where the lambda-z-dependent errors fall (logs/deviations.md §26)."""
    REF = {**{(s, p): 10.0 for s in ("s1", "s2", "s3") for p in score_all.sn.PARAMS},
           ("s1", "R2ADJ"): 0.95, ("s1", "NPTS"): 3.0,
           ("s2", "R2ADJ"): 0.90, ("s2", "NPTS"): 4.0,
           ("s3", "R2ADJ"): 0.50, ("s3", "NPTS"): 3.0}   # s3: R2adj < 0.80, not scored for lambda-z parameters

    def agent(self, **npts):
        a = {(s, p): 10.0 for s in ("s1", "s2", "s3") for p in score_all.sn.PARAMS}
        a[("s2", "HL")], a[("s2", "Vz")] = 12.0, 13.0   # two lambda-z errors, both in s2
        a.update({(s, "NPTS"): v for s, v in npts.items()})
        return a

    def test_errors_split_by_whether_terminal_points_match(self):
        b = score_all.sn.terminal_point_breakdown(self.agent(s1=3.0, s2=5.0, s3=9.0), self.REF)
        self.assertEqual(b, {"subjects": 2, "match": 1, "lz_match_n": 4, "lz_match_err": 0,
                             "lz_differ_n": 4, "lz_differ_err": 2})

    def test_subject_without_npts_in_a_reporting_run_counts_as_differing(self):
        b = score_all.sn.terminal_point_breakdown(self.agent(s1=3.0), self.REF)
        self.assertEqual((b["subjects"], b["match"], b["lz_differ_err"]), (2, 1, 2))

    def test_run_that_reports_no_npts_is_none(self):
        self.assertIsNone(score_all.sn.terminal_point_breakdown(self.agent(), self.REF))


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


class OralNoOutput(unittest.TestCase):
    def test_t3d_run_without_results_json_scores_zero_not_missing(self):
        """§22: an arm failure that left nothing scores 0 on T3d too, so it is not dropped from the accuracy stats."""
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "output"))
            r = score_all.score_oral_run(d)
            self.assertEqual((r["completed"], r["overall"]), (False, 0.0))
            open(os.path.join(d, "output", "results.json"), "w").write("{not json")
            self.assertEqual(score_all.score_oral_run(d)["overall"], 0.0)


class SummarizeOutcomes(unittest.TestCase):
    def test_separates_ratelimit_infra_arm_failures_and_protocol_exclusions(self):
        base = {"arm": "A1", "task": "T3a_messy", "is_error": "False", "cost_usd": "1.0", "tool_calls": "9"}
        rows = [
            {**base, "runid": "r1", "status": "ok"},
            {**base, "runid": "r2", "status": "failed_ratelimit", "is_error": "True"},
            {**base, "runid": "r3", "status": "exit1"},                                   # arm failure, counted
            {**base, "runid": "r4", "status": "timeout", "cost_usd": ""},                 # arm failure, counted
            {**base, "runid": "r5", "status": "ok"},                                      # protocol-excluded
            {**base, "runid": "r6", "status": "exit1", "cost_usd": "", "tool_calls": "0"},  # infra: no work done
            {**base, "runid": "r7", "status": "exit1"},                                   # arm failure but excluded
        ]
        c = summarize.count_outcomes(rows, excluded={"r5", "r7"})
        k = ("A1", "T3a_messy")
        self.assertEqual((c["n_invalid_excluded"][k], c["n_infra_failed"][k], c["n_protocol_excluded"][k], c["n_arm_failed"][k]), (1, 1, 2, 2))


if __name__ == "__main__":
    unittest.main()
