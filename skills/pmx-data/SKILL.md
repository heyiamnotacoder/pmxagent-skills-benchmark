---
name: pmx-data
description: Clean and standardise PK concentration data into an analysis-ready long (ADPC-like) table — wide sheets with time columns, NONMEM datasets, Excel files, "<LLOQ"/"BLQ" strings, mixed units, missing dose rows. Use before NCA/ER whenever input is not already one row per record with numeric concentrations, or when asked to convert data to ADPC/NONMEM-style format.
---

# PK data standardisation

## Target format (one row per record)
`USUBJID, GROUP, EVID (1 = dose, 0 = obs), ATPTN (time since dose), AVAL, AVALU, DOSE, DOSEU, ROUTE (1 = IV, 2 = extravascular), BLQ (1/0)`

This is the format the `pmx-nca` script reads by default. Use `--group GROUP` when calling it on this output.

## Rules
- **BLQ text** ("<LLOQ", "BLQ", "BQL", "<0.5", "ND"): set AVAL to 0 and BLQ to 1. **Don't decide how BLQ is treated here**; that belongs to the NCA step.
- **Other non-numeric values:** set them to missing and report every one. Never guess numbers.
- **Units:** don't convert unless asked.
  - Mass/volume units convert (pg, ng, µg, mg, g over mL, dL, L).
  - Molar and IU units need a molecular weight or activity. Refuse and say so; don't invent a factor.
- **Route mapping:**
  - IV, intravenous and bolus → 1.
  - Oral, PO, SC, IM and other extravascular routes → 2.
  - In NONMEM data, a dose given into the observation compartment means IV.
- **Checks:** report duplicate subject/time records, negative values, missing doses and subjects without a route. Keep a log of every change.

<!-- scripts:start -->
## Tool: `scripts/run_data.R` (tested, including a round trip through `pmx-nca`)

```bash
Rscript <skill_dir>/scripts/run_data.R --input raw.xlsx --outdir results [options]
```

**Format detection** (`--format auto`):
- `nonmem`: the file has ID, TIME and DV plus AMT, EVID or MDV.
- `wide`: numeric-looking time columns.
- `long`: anything else.

The script auto-detects columns (subject, time, conc, dose, route, unit). If the guesses are wrong, override them with:
`--subject`, `--group`, `--time`, `--conc`, `--time-cols '<regex>'` (wide files), `--dose <col or number>`, `--route <col or value>`, `--unit-col` / `--conc-unit`, `--dose-unit`, `--to-unit ug/mL`, `--sheet`.

**Outputs:** `adpc.csv` (with `.` for missing values) and `adpc_qc.txt`. **Read the QC file and pass its warnings on to the user.**
<!-- scripts:end -->
