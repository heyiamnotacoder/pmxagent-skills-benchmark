---
name: pmx-er
description: Exposure-response (ER) analysis — logistic regression for binary endpoints (EC50, slope), and linear / Emax / sigmoid Emax / Imax for continuous endpoints, with AIC model selection. Use for "ER analysis", exposure vs response, EC50 estimation, or response-rate vs AUC/Cmax.
---

# Exposure-response

## Conventions
- **Exposure:** use the individual NCA metric the user names (AUClast, Cmax, ...), one row per subject. Read it from the NCA output file. **Never re-type exposure values into code or into the prompt**: transcription errors grow with dataset size.
- **Binary endpoints:**
  - Logistic regression, logit P = b0 + b1·E, with EC50 = −b0/b1 (exposure at P = 0.5).
  - Also fit a log-exposure version and compare the two by AIC.
  - Report the EC50 standard error by the delta method.
- **Continuous endpoints:** linear, Emax, sigmoid Emax (Hill) and Imax. Select by AIC and report the parameters with their standard errors.
- **Generating binary data from response rates** (e.g. "use rates 0.1, 0.5 and 0.9 per group"):
  - Default to *exact* rates: round(rate·n) responders per group, placed randomly within each group.
  - Use independent Bernoulli draws only if the user asks for them.
  - Always use and report a seed.
- **Report:** n, candidate models with their AIC, the selected model, the parameters, per-group mean exposure against observed response rate, and a plot.

<!-- scripts:start -->
## Tool: `scripts/run_er.R` (tested; deterministic with seed)

```bash
# binary, generating responses from group rates, exposure read straight from pmx-nca output
Rscript <skill_dir>/scripts/run_er.R --input results/nca_results_individual.csv --exposure AUClast \
  --group DOSEGRP --response-rates 1:0.1,2:0.5,3:0.9 --seed 42 --outdir results
# continuous, observed response column
Rscript <skill_dir>/scripts/run_er.R --input er.csv --exposure AUC --response Y --type continuous --outdir results
```

| Option | Default | Notes |
|---|---|---|
| `--input` | — | A wide CSV with one row per subject, or pmx-nca long output (detected by its PPTESTCD/PPSTRESN columns) |
| `--exposure` | AUClast | Column name, or the PPTESTCD for long input |
| `--subject` / `--group` | USUBJID / none | |
| `--response` | — | Observed response column |
| `--response-rates` | — | `group:rate,...`, used to generate a binary response |
| `--rate-mode` | exact | or `bernoulli` |
| `--type` | binary | or `continuous` |
| `--models` | all for the type | `logistic,logistic-log` or `linear,emax,sigmoid-emax,imax` |
| `--seed` | 42 | |

**Outputs:** `er_parameters.csv` (all models; the `selected` flag marks the chosen one), `er_group_summary.csv`, `er_data.csv`, `er_predictions.csv` and `er.png`.
<!-- scripts:end -->
