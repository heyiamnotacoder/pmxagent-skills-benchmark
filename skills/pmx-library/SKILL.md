---
name: pmx-library
description: Find, inspect and simulate published population PK/PD models from the nlmixr2lib library (614 models — mAbs, antibiotics, oncology, TMDD, etc.) with rxode2. Use when asked for a "published model", a model for a named drug, literature-based simulation, or model parameters/references.
---

# Published model library

## Conventions
- **Search before assuming.** Look the drug or model type up in the library. Only say "no published model available" if the search comes back empty.
- **Report the model's reference and units** (time, dose, concentration) with any simulation. Library models often use **days** as the time unit.
- **Covariates:** many models need them (weight, age, albumin, ...). Use values the user gives. Otherwise use a stated typical value (e.g. 70 kg) and say so.
- **Variability:** default to between-subject variability with a seed. Use typical-value simulation (no IIV) when the user asks for "typical" or "population" predictions.
- **Dosing compartment:** use `depot` for oral/SC and `central` for IV, whichever the model's dosing compartments allow.

<!-- scripts:start -->
## Tool: `scripts/run_library.R`
This uses nlmixr2lib at commit d8a40f2 (614 models) with rxode2.

```bash
Rscript <skill_dir>/scripts/run_library.R list --search 'pembrolizumab|PD-1'
Rscript <skill_dir>/scripts/run_library.R show --model Ahamadi_2017_pembrolizumab
Rscript <skill_dir>/scripts/run_library.R simulate --model PK_2cmt_mAb_Davda_2014 --dose 100 --cmt central \
  --end 56 --covariates WT=70 --n 100 --seed 42 --outdir results
```

**What each command gives you:**
- `list`: name | description | parameters | dosing compartments.
- `show`: reference, units, required covariates, parameter table and the model code.

**`simulate` options:**
- `--cmt`, `--dur` (infusion), `--ii`, `--n-doses`
- `--times` or `--end`
- `--n`, `--no-iiv`, `--seed`, `--covariates`

**`simulate` outputs:**
- `library_sim.csv`: ID, TIME, IPRED, DV_SIM (with residual error)
- `library_sim_summary.csv`: the 5th, 50th and 95th percentiles
- a `.png` plot and a `_settings.txt` file

**First run:** rxode2 compiles each model the first time (10–30 s). The script sets `R_MAKEVARS_USER` itself, so no compiler setup is needed.
<!-- scripts:end -->
