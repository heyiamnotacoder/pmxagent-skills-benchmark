---
name: pmx-nca
description: Noncompartmental PK analysis (NCA) of concentration-time data — AUClast, AUCinf, Cmax, Tmax, half-life/lambda_z, CL, Vz, CL/F, Vz/F, adjusted R2, terminal points. Use for any request to "run NCA", compute AUC/Cmax/half-life, or summarise exposure per subject/group.
---

# NCA

## Method conventions (apply unless the user says otherwise)
- **AUC:** linear-up/log-down trapezoid is the default. Use linear-only if asked. AUClast runs from dose time to **Tlast, the last measurable (non-zero) concentration**.
- **λz (terminal slope):**
  - Fit log-linear regression to the last n points after Tmax (Tmax itself excluded), with n ≥ 3.
  - Pick the n with the best **adjusted R²**. When the adjusted R² values are within 1e-4, prefer more points.
  - Report adjusted R² and n alongside every λz. Don't drop subjects silently; let the user filter on R².
- **Derived parameters:**
  - HL = ln2/λz
  - AUCinf_obs = AUClast + Clast_obs/λz
  - CL = Dose/AUCinf_obs
  - Vz = CL/λz
- **Route:**
  - IV bolus → report `CL_obs` and `Vz_obs`.
  - Extravascular → report the apparent `CLF_obs` and `VzF_obs`. Never label oral clearance as CL.
- **IV bolus with no t=0 sample:** back-extrapolate C0 log-linearly from the first two points. If they aren't declining, use the first concentration.
- **BLQ:**
  - Default: BLQ before Tmax = 0; BLQ after Tmax = missing (dropped).
  - If the user specifies a rule, follow the user.
  - Record which rule was used.
- **Units:** don't convert unless asked. CL is in dose-unit / (conc-unit·time-unit), exactly as given.
- **Dose rows:** rows with EVID=1, or an AVAL of `.` or empty, are dose records, not observations.
- **Outputs:**
  - Individual results in long format (group, subject, PPTESTCD, value).
  - Means per group are arithmetic means of the individual values.
  - Always say how many subjects have λz, and which settings were used.

<!-- scripts:start -->
## Tool: `scripts/run_nca.R` (PKNCA, tested, deterministic)
Use this script instead of writing NCA code. Run it once for the whole dataset (1,800 subjects take about 15 s):

```bash
Rscript <skill_dir>/scripts/run_nca.R --input data.csv --outdir results [options]
```

| Option | Default | Notes |
|---|---|---|
| `--group` / `--subject` / `--time` / `--conc` / `--dose` | DRUG / USUBJID / ATPTN / AVAL / DOSE | Column names. Use `--group ''` if there is no grouping. |
| `--route` / `--route-iv` | ROUTE / `1,IV,...` | Values meaning IV bolus. Everything else is extravascular. Use `--route '' --route-default intravascular` if there is no route column. |
| `--evid` | EVID | Use `''` if the file has only observations (then each subject's dose is taken from its first row). |
| `--blq` / `--blq-rule` | BLQ / `zero-before-tmax-missing-after` | Also `zero`, `missing`, `pknca-default`. With `--blq ''`, conc == 0 counts as BLQ. |
| `--auc-method` | `lin-up/log-down` | or `linear` |
| `--min-points` / `--adjr2-factor` / `--min-r2` | 3 / 1e-4 / ~0 | λz selection |
| `--allow-tmax-in-lambda` | off | |
| `--id-style` | `separate` | `combined` writes `GROUP_SUBJECT` in the first column (e.g. `abatacept_1`) |
| `--prefix` | `nca_results` | |

**Outputs:**
- `<prefix>_individual.csv`: group, USUBJID, PPTESTCD, PPSTRESN, ROUTE
- `<prefix>_mean.csv`: group, PPTESTCD, mean, N
- `<prefix>_settings.txt`: the settings used

**PPTESTCD values:** Cmax, Tmax, AUClast, AUCINF_obs, HL_Lambda_z, CL_obs or CLF_obs, Vz_obs or VzF_obs, Rsq_adjusted, No_points_lambda_z.

**If the user wants a different output shape:** reshape the script's CSV with a few lines of code, e.g. keep only the requested columns or rename the group column. Don't recompute the parameters.

The script needs R with PKNCA and optparse. If the input has unusual structure (wide format, text units, `<LLOQ` strings, NONMEM layout), clean it to one row per record first. The `pmx-data` skill does this.
<!-- scripts:end -->

## Before you report
- Check the counts. Every subject should have Cmax, Tmax and AUClast. Say how many have λz.
- If AUCinf extrapolation is more than 20% of AUCinf, or adjusted R² is below 0.8, flag the subject; don't drop it.
- State the settings: AUC method, λz rule, BLQ rule and route handling.
