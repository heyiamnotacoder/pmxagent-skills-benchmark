#!/usr/bin/env python3
"""Build task inputs (agent-visible) and references (scorer-only, git-ignored) from the paper's supplement.

tasks/<T>/prompt.md         task prompt given to every arm (harness adds a fixed suffix)
tasks/<T>/inputs/           files copied into the arm workspace
tasks/<T>/reference/        scoring truth: never copied into a workspace

Deterministic: drug subsets are chosen by sha256(drug) order, no RNG.
"""
import csv, hashlib, json, math, os, shutil, subprocess, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUP = os.path.join(ROOT, "psp470325-sup-0001-appendixs1")
DATA = os.path.join(SUP, "benchmark", "nca_benchmark_individual.csv")
PKX = os.path.join(SUP, "benchmark", "Single Run Analysis", "nca_results_PKanalix_individual.csv")
T1_PROMPT = open(os.path.join(SUP, "benchmark", "NCA-benchmark-prompt.txt")).read().strip()
T = os.path.join(ROOT, "tasks")

rows = list(csv.DictReader(open(DATA)))
FIELDS = list(rows[0].keys())
pkx = list(csv.DictReader(open(PKX)))
by_drug = collections.defaultdict(list)
for r in rows:
    by_drug[r["DRUG"]].append(r)
drug_unit = {d: v[0]["AVALU"] for d, v in by_drug.items()}
drug_route = {d: v[0]["ROUTE"] for d, v in by_drug.items()}
drug_blq = {d: sum(r["BLQ"] == "1" for r in v) for d, v in by_drug.items()}
order = sorted(by_drug, key=lambda d: hashlib.sha256(d.encode()).hexdigest())

ID_NOTE = ("Individual results file: columns DRUG, PPTESTCD, PPSTRESN, where DRUG is "
           "`<drug>_<subject number>` (e.g. `abatacept_1`).")


def fresh(task):
    for sub in ("inputs", "reference"):
        p = os.path.join(T, task, sub)
        shutil.rmtree(p, ignore_errors=True)
        os.makedirs(p)
    return os.path.join(T, task)


def write_csv(path, fieldnames, data):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_NONNUMERIC)
        w.writeheader()
        w.writerows(data)


def ref_subset(drugs, path, transform=None, rename=None):
    out = []
    for r in pkx:
        drug = r["DRUG"].rsplit("_", 1)[0]
        if drug in drugs:
            r = dict(r)
            if rename:
                r["DRUG"] = rename(r["DRUG"])
            if transform:
                r = transform(r, drug)
                if r is None:
                    continue
            out.append(r)
    write_csv(path, ["DRUG", "PPTESTCD", "PPSTRESN"], out)
    return len({r["DRUG"] for r in out})


def meta(task, **kw):
    json.dump(kw, open(os.path.join(T, task, "reference", "meta.json"), "w"), indent=2)


# ---------------- T1: the paper's NCA benchmark, verbatim ----------------
d = fresh("T1_nca")
shutil.copy(DATA, os.path.join(d, "inputs", "nca_benchmark.csv"))
open(os.path.join(d, "prompt.md"), "w").write(T1_PROMPT + "\n")
shutil.copy(PKX, os.path.join(d, "reference", "pkanalix_individual.csv"))
meta("T1_nca", kind="nca", subjects=1820, source="PKanalix 2024R1 (paper supplement)")

# ---------------- T2: the paper's case study (steps 1-3, verbatim) ----------------
d = fresh("T2_case")
case = open(os.path.join(SUP, "demo", "CaseStudyPrompt.md")).read()
steps = case[case.index("(1)"):].strip()
open(os.path.join(d, "prompt.md"), "w").write(
    "Please conduct the following analysis:\n\n" + steps + "\n\n"
    "When finished, also write `output/results.json` with keys: `group_summary` (list of objects with "
    "dose_mg, mean_AUClast, mean_Cmax, mean_half_life), `ec50` (number, exposure units), `ec50_units`, "
    "`seed` (or null), `n_timepoints_per_subject`, `pk_parameters` (typical values used), and `files` "
    "(paths of the simulated data, NCA results and ER data you produced).\n")
meta("T2_case", kind="case_study", truth="internal consistency + cross-rep reproducibility; paper EC50 ~2146 h*ug/mL")

# ---------------- T3a: messy Excel workbook, one sheet per drug ----------------
d = fresh("T3a_messy")
t3a = [x for x in order][:30]
wb_dir = os.path.join(d, "reference", "_sheets")
os.makedirs(wb_dir)
route_txt = {"1": "IV bolus", "2": "Oral/SC (extravascular)"}
for drug in t3a:
    obs = [r for r in by_drug[drug] if r["EVID"] == "0"]
    times = sorted({float(r["ATPTN"]) for r in obs})
    subj = sorted({int(r["USUBJID"]) for r in obs})
    tcols = [f"{t:g} h" for t in times]
    table = []
    for s in subj:
        rec = {r_["ATPTN"]: r_ for r_ in obs if int(r_["USUBJID"]) == s}
        dose = next(r_["DOSE"] for r_ in by_drug[drug] if int(r_["USUBJID"]) == s)
        row = {"Patient": f"P{s:03d}", "Dose (mg)": dose, "Route": route_txt[drug_route[drug]],
               "Conc. units": drug_unit[drug]}
        for t, c in zip(times, tcols):
            r_ = rec.get(f"{t:g}") or next((v for k, v in rec.items() if float(k) == t), None)
            row[c] = "" if r_ is None else ("<LLOQ" if r_["BLQ"] == "1" else r_["AVAL"])
        table.append(row)
    write_csv(os.path.join(wb_dir, f"{drug[:31]}.csv"), ["Patient", "Dose (mg)", "Route", "Conc. units"] + tcols, table)
xlsx = os.path.join(d, "inputs", "pk_raw.xlsx")
subprocess.run(["Rscript", "-e", f"""
fs <- list.files('{wb_dir}', full.names=TRUE); sh <- lapply(fs, function(f) {{
  x <- read.csv(f, check.names=FALSE, colClasses='character'); x }})
names(sh) <- tools::file_path_sans_ext(basename(fs)); writexl::write_xlsx(sh, '{xlsx}')"""], check=True)
shutil.rmtree(wb_dir)
ref_subset(set(t3a), os.path.join(d, "reference", "pkanalix_individual.csv"))
open(os.path.join(d, "prompt.md"), "w").write(
    "The Excel workbook `pk_raw.xlsx` contains single-dose PK data from 30 drugs, one sheet per drug "
    "(sheet name = drug). Each row is a patient; time columns give hours post-dose; `<LLOQ` means below the "
    "limit of quantification; blank cells were not sampled.\n\n"
    "Please perform noncompartmental analysis and report the individual and mean PK parameters for each "
    "patient/drug: AUClast, AUCINF_obs, HL_Lambda_z, Cmax, Tmax, CL_obs (or CLF_obs for extravascular), "
    "Vz_obs (or VzF_obs for extravascular), adjusted R2 (Rsq_adjusted), and number of terminal timepoints "
    "(No_points_lambda_z).\n\nNotes:\n(1) Use adjusted R2 for terminal point selection and lambda_z estimation\n"
    "(2) DO NOT perform any unit conversions\n(3) Use Linear Up Log Down trapezoidal rule\n\n"
    + ID_NOTE + " Subject number = the number in the Patient ID (P007 -> 7).\n")
meta("T3a_messy", kind="nca", drugs=t3a, source="PKanalix subset; data reshaped only")

# ---------------- T3b: BLQ rule stated explicitly ----------------
d = fresh("T3b_blq")
t3b = [x for x in order if drug_blq[x] > 0]
write_csv(os.path.join(d, "inputs", "nca_blq.csv"), FIELDS, [r for r in rows if r["DRUG"] in set(t3b)])
ref_subset(set(t3b), os.path.join(d, "reference", "pkanalix_individual.csv"))
open(os.path.join(d, "prompt.md"), "w").write(
    T1_PROMPT.replace("nca_benchmark.csv", "nca_blq.csv") +
    "\n(5) BLQ = 1 marks concentrations below the limit of quantification: treat BLQ values before Tmax as zero "
    "and BLQ values after Tmax as missing\n\n" + ID_NOTE + "\n")
meta("T3b_blq", kind="nca", drugs=t3b, source="PKanalix subset (drugs with BLQ records)")

# ---------------- T3c: unit harmonisation requested ----------------
d = fresh("T3c_units")
to_ugml = {"ng/mL": 1e-3, "ug/L": 1e-3, "mg/L": 1.0, "ug/mL": 1.0, "pg/mL": 1e-6}
t3c = [x for x in order if drug_unit[x] in to_ugml][:30]
write_csv(os.path.join(d, "inputs", "nca_units.csv"), FIELDS, [r for r in rows if r["DRUG"] in set(t3c)])


def to_std(r, drug):
    f = to_ugml[drug_unit[drug]]
    code, v = r["PPTESTCD"], float(r["PPSTRESN"])
    scale = {"Cmax": f, "AUClast": f, "AUCINF_obs": f, "CL_obs": 1 / f, "CLF_obs": 1 / f,
             "Vz_obs": 1 / f, "VzF_obs": 1 / f}.get(code, 1.0)
    r["PPSTRESN"] = repr(v * scale)
    return r


ref_subset(set(t3c), os.path.join(d, "reference", "pkanalix_individual.csv"), transform=to_std)
open(os.path.join(d, "prompt.md"), "w").write(
    "Please perform noncompartmental analysis on `nca_units.csv` (concentration units differ between drugs, see "
    "AVALU; doses are in mg; ATPTN is hours post-dose). Report individual and mean AUClast, AUCINF_obs, "
    "HL_Lambda_z, Cmax, Tmax, CL_obs (or CLF_obs for extravascular), Vz_obs (or VzF_obs for extravascular), "
    "Rsq_adjusted and No_points_lambda_z.\n\n**Report all results in harmonised units:** concentrations in ug/mL, "
    "AUC in h*ug/mL, clearance in L/h, volume in L, half-life in h.\n\nNotes:\n(1) Use adjusted R2 for terminal "
    "point selection and lambda_z estimation\n(2) Route of administration (ROUTE) of 1 is intravenous and 2 is "
    "extravascular\n(3) Use Linear Up Log Down trapezoidal rule\n\n" + ID_NOTE + "\n")
meta("T3c_units", kind="nca", drugs=t3c, factors_to_ugml={k: to_ugml[drug_unit[k]] for k in t3c})

# ---------------- T3d: out-of-scope for PMxAgent's /PK (oral 1-CM) ----------------
d = fresh("T3d_oral")
ka, CL, V, F, D = 1.2, 4.0, 40.0, 1.0, 200.0
k = CL / V
tmax = math.log(ka / k) / (ka - k)
cmax = F * D * ka / (V * (ka - k)) * (math.exp(-k * tmax) - math.exp(-ka * tmax))
open(os.path.join(d, "prompt.md"), "w").write(
    "Simulate 20 subjects receiving a single 200 mg oral dose using a one-compartment model with first-order "
    "absorption (ka = 1.2 1/h, CL = 4 L/h, V = 40 L, F = 1) and 30% between-subject variability on CL and V. "
    "Plot the concentration-time profiles over 48 h, and report the typical-subject (no variability) Cmax, "
    "Tmax and AUC0-inf.\n\nWhen finished, also write `output/results.json` with keys `typical_cmax_mg_per_L`, "
    "`typical_tmax_h`, `typical_auc_inf_mg_h_per_L`, `model_used` (short description) and `files`.\n")
json.dump({"typical_cmax_mg_per_L": cmax, "typical_tmax_h": tmax, "typical_auc_inf_mg_h_per_L": F * D / CL,
           "route": "oral", "kind": "analytical"},
          open(os.path.join(d, "reference", "truth.json"), "w"), indent=2)
meta("T3d_oral", kind="analytical", note="PMxAgent /PK supports IV bolus 1/2-CM only")

# ---------------- T3e: 5x the benchmark (9100 subjects) ----------------
d = fresh("T3e_large")
big = []
for rep in range(5):
    for r in rows:
        r = dict(r)
        r["USUBJID"] = str(int(r["USUBJID"]) + 100 * rep)
        big.append(r)
write_csv(os.path.join(d, "inputs", "nca_large.csv"), FIELDS, big)


def rep_rename(rep):
    return lambda s: f"{s.rsplit('_', 1)[0]}_{int(s.rsplit('_', 1)[1]) + 100 * rep}"


out = []
for rep in range(5):
    for r in pkx:
        out.append({"DRUG": rep_rename(rep)(r["DRUG"]), "PPTESTCD": r["PPTESTCD"], "PPSTRESN": r["PPSTRESN"]})
write_csv(os.path.join(d, "reference", "pkanalix_individual.csv"), ["DRUG", "PPTESTCD", "PPSTRESN"], out)
open(os.path.join(d, "prompt.md"), "w").write(T1_PROMPT.replace("nca_benchmark.csv", "nca_large.csv") + "\n\n" + ID_NOTE + "\n")
meta("T3e_large", kind="nca", subjects=9100, note="benchmark x5, USUBJID offset by 100*rep")

for t in sorted(os.listdir(T)):
    p = os.path.join(T, t)
    if os.path.isdir(p):
        print(t, "| inputs:", os.listdir(os.path.join(p, "inputs")), "| ref:", os.listdir(os.path.join(p, "reference")))
