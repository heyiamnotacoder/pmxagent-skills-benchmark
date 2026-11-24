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


CODE = {"Cmax": "CMAX", "Tmax": "TMAX", "AUClast": "AUCLST", "AUCINF_obs": "AUCIFO", "HL": "LAMZHL", "CL": "CLO",
        "Vz": "VZO"}   # CDISC PPTESTCD codes, as agents write them


def two_subject_ref():
    """Reference with two subjects of one drug, in file order abatacept_1, abatacept_2 (R2adj >= 0.80)."""
    ref = {}
    for s, v in (("abatacept_1", 10.0), ("abatacept_2", 20.0)):
        ref.update({(s, p): v for p in score_all.sn.PARAMS})
        ref[(s, "R2ADJ")], ref[(s, "NPTS")] = 0.99, 3.0
    return ref


def run_with(d, files):
    """A run directory whose output/ holds `files` {name: rows}."""
    run = os.path.join(d, "run"); os.makedirs(os.path.join(run, "output"))
    for name, rows in files.items():
        write_csv(os.path.join(run, "output", name), rows)
    return run


class UnscorableNca(unittest.TestCase):
    """A completed NCA run with nothing that maps to a subject scores 0 on every parameter (SPEC: every completed run
    counts), not only on `overall` (logs/deviations.md §17)."""

    def test_drug_only_rows_that_cannot_be_matched_score_zero_on_every_parameter(self):
        with tempfile.TemporaryDirectory() as d:   # one row per parameter for a drug with two subjects: no match
            run = run_with(d, {"nca_individual.csv": [{"DRUG": "abatacept", "PPTESTCD": CODE[p], "PPSTRESN": 10}
                                                      for p in score_all.sn.PARAMS]})
            r = score_all.score_nca_dir(run, two_subject_ref())
        self.assertEqual((r["scored_file"], r["coverage_pct"], r["overall"]), ("", 0.0, 0.0))
        self.assertEqual(r["note"], "no scorable individual file")
        for p in score_all.sn.PARAMS:
            self.assertEqual(r[f"{p}_pct"], 0.0, p)


class CanonicalNames(unittest.TestCase):
    """Parameter names are matched by rule, not by a list of names seen in runs (logs/deviations.md §29): lower-case,
    drop `. _ / -` and spaces, then look up CDISC PPTESTCD, PKNCA and PKanalix names."""

    def test_pknca_codes_map_to_scored_parameters(self):
        c = score_all.sn.canonical
        self.assertEqual([c(n) for n in ("aucinf.obs", "cl.obs", "vz.obs", "half.life", "adj.r.squared",
                                         "lambda.z.n.points", "cmax", "tmax", "auclast")],
                         ["AUCINF_obs", "CL", "Vz", "HL", "R2ADJ", "NPTS", "Cmax", "Tmax", "AUClast"])

    def test_punctuation_and_case_variants_map_alike(self):
        c = score_all.sn.canonical
        for n in ("CL.F_obs", "cl.f.obs", "CLF_obs", "cl/f_obs", "CLFO"):
            self.assertEqual(c(n), "CL", n)
        for n in ("Vz.F_obs", "vz.f.obs", "VZFOBS"):
            self.assertEqual(c(n), "Vz", n)
        self.assertEqual(c("No.Points.Lambda.z"), "NPTS")

    def test_no_two_names_collide_after_normalising(self):
        normed = [score_all.sn._norm(n) for names in score_all.sn.NAMES.values() for n in names]
        self.assertEqual(len(normed), len(set(normed)))

    def test_long_file_with_a_subject_column_other_than_usubjid_is_not_drug_only(self):
        for col in ("ID", "SUBJID", "Subject"):
            rows = [{"DRUG": "abatacept", col: s, "PPTESTCD": CODE[p], "PPSTRESN": v}
                    for s, v in (("2", 20.0), ("1", 10.0)) for p in score_all.sn.PARAMS]   # IDs, not row order
            with tempfile.TemporaryDirectory() as d:
                r = score_all.score_nca_dir(run_with(d, {"x.csv": rows}), two_subject_ref())
            self.assertEqual((r["overall"], r.get("note", "")), (100.0, ""), col)

    def test_predicted_and_unadjusted_values_are_not_scored(self):
        c = score_all.sn.canonical
        for n in ("aucinf.pred", "cl.pred", "vz.pred", "r.squared", "clast.obs", "cmax.dn", "", "foo"):
            self.assertIsNone(c(n), n)

    def test_pknca_long_file_is_scored(self):
        with tempfile.TemporaryDirectory() as d:
            codes = {"Cmax": "cmax", "Tmax": "tmax", "AUClast": "auclast", "AUCINF_obs": "aucinf.obs",
                     "HL": "half.life", "CL": "cl.obs", "Vz": "vz.obs"}
            rows = [{"DRUG": s, "PPTESTCD": codes[p], "PPSTRESN": v}
                    for s, v in (("abatacept_1", 10.0), ("abatacept_2", 20.0)) for p in score_all.sn.PARAMS]
            rows += [{"DRUG": s, "PPTESTCD": "adj.r.squared", "PPSTRESN": 0.99} for s in ("abatacept_1", "abatacept_2")]
            r = score_all.score_nca_dir(run_with(d, {"pknca.csv": rows}), two_subject_ref())
        self.assertEqual(r["overall"], 100.0)


class RowOrderMatching(unittest.TestCase):
    """Equal treatment of drug-only files in every arm (logs/deviations.md §29): within a drug and parameter, the k-th
    row is the drug's k-th subject in reference order, but only when the row count equals the drug's subject count."""

    def drug_only(self, values=(10.0, 20.0), params=None):
        return [{"DRUG": "abatacept", "PPTESTCD": CODE[p], "PPSTRESN": v}
                for p in (params or score_all.sn.PARAMS) for v in values]

    def test_drug_only_rows_are_matched_to_subjects_in_reference_order(self):
        with tempfile.TemporaryDirectory() as d:
            r = score_all.score_nca_dir(run_with(d, {"deliverable.csv": self.drug_only()}), two_subject_ref())
        self.assertEqual((r["scored_file"], r["coverage_pct"], r["overall"]), ("output/deliverable.csv", 77.78, 100.0))   # 14 of 18 keys: no R2adj/NPTS rows
        self.assertEqual(r["note"], "subjects matched by row order")

    def test_group_with_wrong_row_count_is_missing_and_others_still_match(self):
        rows = self.drug_only() + [{"DRUG": "abatacept", "PPTESTCD": "Cmax", "PPSTRESN": 30.0}]   # 3 Cmax rows
        with tempfile.TemporaryDirectory() as d:
            r = score_all.score_nca_dir(run_with(d, {"deliverable.csv": rows}), two_subject_ref())
        self.assertEqual(r["Cmax_pct"], 0.0)
        self.assertEqual(r["Tmax_pct"], 100.0)

    def test_order_comes_from_the_reference_not_from_sorting(self):
        with tempfile.TemporaryDirectory() as d:   # file lists subject 2's values first: both wrong
            r = score_all.score_nca_dir(run_with(d, {"deliverable.csv": self.drug_only((20.0, 10.0))}),
                                        two_subject_ref())
        self.assertEqual(r["overall"], 0.0)

    def test_file_with_subject_ids_wins_a_tie_with_a_matched_one(self):
        explicit = [{"DRUG": s, "PPTESTCD": CODE[p], "PPSTRESN": v}
                    for s, v in (("abatacept_1", 10.0), ("abatacept_2", 20.0)) for p in score_all.sn.PARAMS]
        with tempfile.TemporaryDirectory() as d:
            run = run_with(d, {"a_deliverable.csv": self.drug_only(), "z_script.csv": explicit})
            r = score_all.score_nca_dir(run, two_subject_ref())
        self.assertEqual((r["scored_file"], r.get("note", "")), ("output/z_script.csv", ""))

    def test_wide_drug_only_file_is_matched_too(self):
        rows = [{"DRUG": "abatacept", **{CODE[p]: v for p in score_all.sn.PARAMS}} for v in (10.0, 20.0)]
        with tempfile.TemporaryDirectory() as d:
            r = score_all.score_nca_dir(run_with(d, {"wide.csv": rows}), two_subject_ref())
        self.assertEqual(r["overall"], 100.0)


class CharacterOrderSensitivity(unittest.TestCase):
    """Post hoc sensitivity (logs/deviations.md §29): drug-only rows matched in character order of subject number
    (1, 10, 2, ...), as some agents sorted them. Never the primary rule: choosing an order by score is not allowed."""

    def test_character_order_sorts_subject_numbers_as_text(self):
        ref = {(f"abatacept_{i}", "Cmax"): float(i) for i in (1, 2, 10)}
        self.assertEqual(score_all.sn.subject_order(ref)["abatacept"], ["abatacept_1", "abatacept_2", "abatacept_10"])
        self.assertEqual(score_all.sn.subject_order(ref, character=True)["abatacept"],
                         ["abatacept_1", "abatacept_10", "abatacept_2"])

    def test_run_matched_by_row_order_also_gets_its_character_order_score(self):
        ref = {}
        for i in (1, 2, 10):   # reference (= input) order 1, 2, 10
            ref.update({(f"abatacept_{i}", p): float(i) for p in score_all.sn.PARAMS})
            ref[(f"abatacept_{i}", "R2ADJ")] = 0.99
        rows = [{"DRUG": "abatacept", "PPTESTCD": CODE[p], "PPSTRESN": float(i)}
                for p in score_all.sn.PARAMS for i in (1, 10, 2)]   # the file lists 1, 10, 2
        with tempfile.TemporaryDirectory() as d:
            r = score_all.score_nca_dir(run_with(d, {"deliverable.csv": rows}), ref)
        self.assertAlmostEqual(r["overall"], 100 / 3, places=4)    # primary rule: only subject 1 lines up
        self.assertEqual(r["overall_charorder"], 100.0)

    def test_run_with_subject_ids_has_no_character_order_score(self):
        rows = [{"DRUG": s, "PPTESTCD": CODE[p], "PPSTRESN": v}
                for s, v in (("abatacept_1", 10.0), ("abatacept_2", 20.0)) for p in score_all.sn.PARAMS]
        with tempfile.TemporaryDirectory() as d:
            self.assertNotIn("overall_charorder", score_all.score_nca_dir(run_with(d, {"x.csv": rows}), two_subject_ref()))


class StoredPrecision(unittest.TestCase):
    """Run scores are stored unrounded (6 decimals) and rounded only for display, so means are not biased by
    rounding each run first (peer review S10)."""

    def test_overall_is_not_rounded_to_two_decimals(self):
        ref = {}
        for i in (1, 2, 3):
            ref.update({(f"abatacept_{i}", p): 10.0 for p in score_all.sn.PARAMS})
            ref[(f"abatacept_{i}", "R2ADJ")] = 0.99
        rows = [{"DRUG": f"abatacept_{i}", "PPTESTCD": CODE[p], "PPSTRESN": 10.0 if (p, i) != ("Cmax", 3) else 99.0}
                for i in (1, 2, 3) for p in score_all.sn.PARAMS]
        with tempfile.TemporaryDirectory() as d:
            r = score_all.score_nca_dir(run_with(d, {"x.csv": rows}), ref)
        self.assertAlmostEqual(r["overall"], 100 * (6 + 2 / 3) / 7, places=6)
        self.assertAlmostEqual(r["Cmax_pct"], 200 / 3, places=6)


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
                             "lz_differ_n": 4, "lz_differ_err": 2, "lz_none_n": 0, "lz_none_err": 0})

    def test_subject_without_npts_in_a_reporting_run_is_its_own_group(self):
        b = score_all.sn.terminal_point_breakdown(self.agent(s1=3.0, s2=math.nan), self.REF)
        self.assertEqual((b["subjects"], b["match"], b["lz_differ_err"], b["lz_none_n"], b["lz_none_err"]),
                         (2, 1, 0, 4, 2))
        b = score_all.sn.terminal_point_breakdown(self.agent(s1=3.0), self.REF)   # absent, not NaN
        self.assertEqual((b["lz_none_n"], b["lz_none_err"]), (4, 2))

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
