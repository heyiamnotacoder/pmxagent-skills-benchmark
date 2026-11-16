# Preprint plan — bioRxiv (Pharmacology & Toxicology)

Decided 2026-11-16 (user): standalone research article, **not** a letter; post to **bioRxiv**; **LaTeX**;
**wait for T2 + T3** before posting. The benchmark protocol itself stays in `../PLAN.md`; this file covers the
paper and the remaining runs.

Working title: *Do agentic pharmacometrics tools need server infrastructure? A controlled benchmark of an MCP
platform versus Agent Skills for noncompartmental analysis and PK workflows.*

## Framing
- Research question: in an LLM agent for pharmacometrics, which part of the setup produces accuracy and
  reproducibility: domain instructions, executing fixed validated code, or the server stack (Docker + R Plumber +
  OpenAPI + MCP)?
- PMxAgent (Bloomingdale & Khot 2026) is the motivating system and one arm (A1), not the target of the paper.
  Tone: neutral, credit their benchmark and open data, list what MCP gives that Skills do not.
- bioRxiv does not take commentaries/opinion: the paper has to read as original methods + results.

## Claims the data must support (and wording rules)
| # | Claim | Evidence | Wording rule |
|---|---|---|---|
| C1 | Domain knowledge alone closes most of the gap to a tool stack | T1: A2 vs A0, A2 vs A1 | "comparable", unless the pre-specified equivalence test below says otherwise |
| C2 | Executing a bundled, tested script gives run-to-run identical results | T1 SD, distinct outputs; T3 | describe identity of parameter values, not of files |
| C3 | With a script, a small model matches a large one | A4 vs A3 on all tasks | only for the tasks tested |
| C4 | Infrastructure and cost are lower with Skills | cost, wall time, turns, services, LOC | cost = list-price estimate; A1 wall time penalised by Rosetta |
| C5 | Skills extend to steps outside the MCP tool set | T3d (oral 1-CM, PMxAgent /PK is IV only), T2 | report A1 behaviour as observed |

## Pre-specified analysis (freeze by committing this file before any T2/T3 run)
Commit hash of this file = the analysis plan. Nothing below may be changed after seeing T2/T3 scores; any change goes
in `logs/deviations.md` with the reason.
- **Unit of analysis:** one run. Valid run = ledger `status == ok` and not `is_error`. Only exclusion rule: HTTP 429 /
  usage limit (as for T1). Every completed run counts, whatever its score.
- **Primary endpoint (NCA tasks T1, T3a, T3b, T3c, T3e):** the paper's overall accuracy (`scoring/score_nca.py`).
- **T3d:** % of 3 typical values (Cmax, Tmax, AUCinf) within 1% of the analytical solution, plus completion.
- **T2:** completion (results.json with 3 dose groups), internal consistency (group means recomputed from the
  agent's own simulated data, `score_all.py`), cross-run spread of EC50, seed and n_timepoints (reproducibility).
  No ground truth: report descriptively.
- **Comparisons (T1, and each NCA task):** A2−A1, A3−A1, A3−A2, A4−A3, A0−A3. Difference in mean overall accuracy,
  95% percentile bootstrap CI (10,000 resamples of runs within arm, seed 20261116) and two-sided exact/Monte-Carlo
  permutation p-value. Equivalence margin ±1.0 percentage point: "equivalent" only if the whole 95% CI lies inside it.
  No multiplicity adjustment; the CIs are the result, p-values are secondary.
- **Reproducibility:** SD of overall accuracy; number of distinct parameter-value sets per arm (hash of the scored
  individual table, sorted, values rounded to 6 significant digits). Distinct *file* sets reported separately.
- **Effort:** cost/run, wall time, turns, tool calls, tool errors (mean ± SD).
- **Reps:** T1 = 10 per arm (A1 currently 3, see R0), T2 = 10, T3a–e = 5 per arm.

## Work items
### R — runs (your Mac; need R, Docker/colima, the supplement, Claude subscription)
- [ ] R0 *(recommended, your call)*: top up A1 on T1 from 3 to 10 runs, so every T1 comparison is 10 vs 10.
- [ ] R1 Protocol check before T3b: `python3 scoring/check_blq_reference.py`. It shows which BLQ rule the PKanalix
      reference follows. If it is not the rule the T3b prompt states, fix the prompt or the reference *before*
      running T3b, and log it. Do not look at any agent output for this.
- [ ] R2 T2 ×10 and T3a–e ×5 for all arms: `bash harness/run_t2_t3_lanes.sh` (2 sessions max, stops on 429, resumable).
- [ ] R3 `python3 scoring/score_all.py && python3 scoring/summarize.py && python3 scoring/stats.py && python3 scoring/figures.py`
- [ ] R4 Isolation audit on the new transcripts (`scoring/audit_isolation.py`), new evidence bundle + Zenodo
      new version (`harness/make_evidence.py`, `harness/zenodo_upload.py`).
- [ ] R5 Infrastructure count: `python3 harness/count_infra.py` (services, containers, LOC of each stack).

### A — analysis code (this repo, can be done now)
- [x] A1 `scoring/stats.py` — bootstrap CIs, permutation tests, equivalence, distinct value sets → `results/stats.md`, `results/stats.csv`
- [x] A2 `scoring/figures.py` — Fig 2 per-parameter accuracy, Fig 3 accuracy vs cost → `paper/figures/`
- [x] A3 `scoring/check_blq_reference.py` (R1)
- [x] A4 `harness/run_t2_t3_lanes.sh` (R2)
- [x] A5 `harness/count_infra.py` (R5)
- [x] A6 `paper/tables.py` — LaTeX tables generated from `results/*.csv` (no hand-typed numbers)

### M — manuscript (`paper/main.tex`, `paper/references.bib`)
- [x] M1 Skeleton: abstract, introduction, methods (T1 complete), results (T1 complete), discussion, limitations,
      data availability, AI-use statement, author contributions, competing interests.
- [ ] M2 T2/T3 methods + results once runs are in.
- [ ] M3 Fig 1 architecture diagram (two stacks side by side).
- [ ] M4 Verify every reference against the source (DOIs); `% VERIFY` marks entries not yet checked.
- [ ] M5 Co-author read-through (Prof. Singh) and sign-off.

### P — posting
- [ ] P1 bioRxiv checks: original research, PDF with line numbers, figures embedded, CC licence choice
      (data are CC BY-NC from the supplement; choose CC BY-NC 4.0 for the preprint to stay compatible).
- [ ] P2 Tag the repo (`v1.0-preprint`), Zenodo new version with the full evidence, cite both DOIs in the paper.
- [ ] P3 Target journal after preprint (check its preprint policy first).

## Known limitations to state in the paper
Single benchmark source (paper's 182-drug set, PKanalix as reference, not ground truth) · A1 runs fewer than other
arms (unless R0) · subscription runs, cost is Claude Code's list-price estimate · user-global CLAUDE.md loaded in all
arms equally (tool-usage rules only) · skills written with Claude from package docs · A1 containers under Rosetta
(wall time) · one model family (Claude) · ceiling effect near 98.6% (remaining errors mostly λz point selection).
