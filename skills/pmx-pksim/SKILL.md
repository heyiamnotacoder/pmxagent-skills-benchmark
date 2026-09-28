---
name: pmx-pksim
description: Simulate population PK profiles (1/2/3-compartment; IV bolus, IV infusion, oral/SC first-order absorption; single or repeated dosing) with between-subject variability. Use for "simulate PK", dose-group simulations, virtual populations, or concentration-time plots from a compartmental model.
---

# PK simulation

## Conventions
- **Parameters:**
  - CL is clearance, V1 is the central volume, Q is intercompartmental clearance, V2 is the peripheral volume.
  - For 3-CM, Q3 and V3 are the second peripheral pair.
  - KA is the first-order absorption rate and F is bioavailability.
  - Rate constants follow the time unit.
- **Concentration units:** dose unit / L. So mg and L give mg/L, which equals µg/mL.
- **BSV** is log-normal: P_i = P·exp(η), with η ~ N(0, ω²). A requested CV is converted with ω = √ln(1 + CV²). Say which parameters carry BSV; the default is all structural parameters.
- **No parameters given:** don't invent new ones. Use a documented set and name it in the report. For a typical mAb, use Davda et al. 2014 (70 kg, time in days):
  - CL 0.200 L/day, V1 3.61 L, Q 0.747 L/day, V2 2.75 L
  - For SC dosing: KA 0.282 /day and F 0.744
- **Ambiguous design:** for example, "over 4 weeks" could mean a 4-week observation after one dose or repeated dosing for 4 weeks. Choose the literal reading (a single dose, observed for 4 weeks), state the assumption, and make it easy to rerun with the other reading.
- **Reproducibility:** always set and report a seed, the sampling times and the individual parameters.
- **Plots:** plot concentration vs time on a log y-axis, coloured by dose group.

<!-- scripts:start -->
## Tool: `scripts/run_pksim.R` (mrgsolve; tested against analytical solutions)
Use this script instead of writing ODE code:

```bash
Rscript <skill_dir>/scripts/run_pksim.R --model 2cmt --route iv-bolus --preset mab-davda2014 \
  --doses 10,30,100 --n-per-group 20 --end 672 --time-unit h --bsv 0.3 --seed 42 --outdir results
```

| Option | Default | Notes |
|---|---|---|
| `--model` | 2cmt | `1cmt`, `2cmt` or `3cmt` |
| `--route` | iv-bolus | `iv-bolus`, `iv-infusion` (`--dur`) or `oral` (first-order KA and F; use it for SC too) |
| `--params` / `--preset` | — | `'CL=..,V1=..,Q=..,V2=..'` or `mab-davda2014`. The preset converts itself to the chosen `--time-unit`, and `--params` overrides individual preset values. |
| `--per-kg --bw 70` | off | Multiplies CL, Q and V by body weight |
| `--doses`, `--n-per-group` | —, 20 | One group per dose level |
| `--ii`, `--n-doses` | 0, 1 | Repeated dosing |
| `--end`, `--times` or `--delta` | —, end/100 | Sampling grid |
| `--bsv`, `--bsv-params` | 0, all structural parameters | CV |
| `--ruv-prop`, `--ruv-add` | 0, 0 | Residual error. Negative values are floored at 0. |
| `--seed` | 42 | |

**Outputs:**
- `pk_simulation.csv`: USUBJID, DOSEGRP, DOSE, DOSEU, TIME, TIMEU, CONC, CONCU, ROUTE
- `pk_simulation_individual_params.csv`
- `pk_simulation_settings.txt`
- `pk_simulation.png`

**For NCA on simulated data:** use the `pmx-nca` script with:
```
--group DOSEGRP --time TIME --conc CONC --evid '' --blq '' --route '' --route-default intravascular
```
(or `extravascular` for oral). With `--evid ''`, each subject's dose comes from its first row.
<!-- scripts:end -->

## Report
State the model, route, typical parameters with their source, the BSV, the dose groups, the sampling grid, the seed, and any assumptions you made.
