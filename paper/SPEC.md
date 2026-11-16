# Spec: arXiv preprint — MCP platform vs Agent Skills for pharmacometrics agents

Status: open. Tracking issue and sub-issues on GitHub (one issue per slice, see "Slices" below). This file is the
source of truth for scope and decisions; the issues are the work. The benchmark protocol itself is `../PLAN.md`.

Working title: *Do agentic pharmacometrics tools need server infrastructure? A controlled benchmark of an MCP
platform versus Agent Skills for noncompartmental analysis and PK workflows.*

## Problem statement
PMxAgent (Bloomingdale & Khot, CPT:PSP 2026;15:e70325) wraps validated R functions in Docker + R Plumber + an
OpenAPI-generated MCP server and reports 98.3% NCA accuracy with identical results across runs. Its comparison changes
the client, the model, the domain instructions and the execution of fixed code at the same time, so it cannot say
which of these produces accuracy and reproducibility. Our Letter to the Editor on this was cancelled (the journal does
not take letters on its open-access articles). The T1 (NCA) benchmark is complete; T2 and T3 have never run.

## Solution
A standalone research article, posted to **arXiv** once T2 and T3 are complete, that separates the three ingredients:
instructions only (A2), instructions + fixed script (A3/A4), server stack (A1), against no tools (A0), in one
client with one model. PMxAgent is the motivating system and one arm, not the target. Tone: neutral; credit their
benchmark and open data; state what MCP gives that Skills do not.

## Decisions log
| Date | Decision | By |
|---|---|---|
| 2026-11-16 | Standalone research article, not a letter; LaTeX | user |
| 2026-11-16 | Post only after T2 and T3 are complete | user |
| 2026-11-16 | Pre-specified analysis fixed in commit `08ea7b3` (section below, unchanged) | — |
| 2026-11-16 | Top up A1 on T1 from 3 to 10 runs (was "R0, your call") | user |
| 2026-11-16 | Venue: **arXiv** (was bioRxiv). Proposed category q-bio.QM, cross-list cs.AI; confirm at submission | user |
| 2026-11-16 | Corresponding author: Dhruvik Pandya. Co-author Prof. Surjit Singh has agreed to the preprint | user |
| 2026-11-16 | Competing interests: none | user |

## User stories
1. As a pharmacometrician reading the preprint, I want to see which ingredient (instructions, fixed code, server
   stack) produces NCA accuracy, so that I know what to build for my own agent.
2. As a reader, I want run-to-run reproducibility reported as identical parameter values, so that I can judge
   suitability for regulated work.
3. As a reader, I want cost, wall time and infrastructure footprint for each design, so that I can weigh the
   trade-off.
4. As a reader, I want results beyond the single NCA benchmark (case study, messy data, BLQ, units, out-of-scope
   model, larger data), so that the conclusion does not rest on one task.
5. As a reviewer, I want every comparison specified before the data were seen, every number generated from the
   results files, and the raw transcripts archived, so that I can audit the claims.
6. As the PMxAgent authors, I want our system run as published and described fairly, including what MCP does better.
7. As the authors, we want a submission package arXiv accepts first time (TeX source with `.bbl`, no TODOs).

## Claims the data must support (and wording rules)
| # | Claim | Evidence | Wording rule |
|---|---|---|---|
| C1 | Domain knowledge alone closes most of the gap to a tool stack | T1: A2 vs A0, A2 vs A1 | "comparable", unless the pre-specified equivalence test below says otherwise |
| C2 | Executing a bundled, tested script gives run-to-run identical results | T1 SD, distinct outputs; T3 | describe identity of parameter values, not of files |
| C3 | With a script, a small model matches a large one | A4 vs A3 on all tasks | only for the tasks tested |
| C4 | Infrastructure and cost are lower with Skills | cost, wall time, turns, services, LOC | cost = list-price estimate; A1 wall time penalised by Rosetta |
| C5 | Skills extend to steps outside the MCP tool set | T3d (oral 1-CM, PMxAgent /PK is IV only), T2 | report A1 behaviour as observed |

## Pre-specified analysis (freeze by committing this file before any T2/T3 run)
Analysis plan fixed in commit `08ea7b3` (2026-11-16). Nothing below may be changed after seeing T2/T3 scores; any change goes
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

## Implementation decisions
- **Same toolchain for every new run.** All T1/T2/T3 runs so far used Claude Code 2.1.283 (`env/versions.txt`). New
  runs (A1 top-up, T2, T3) must use the same Claude Code version, the same pinned models and the same PMxAgent image
  digests; the harness refuses to run otherwise. If 2.1.283 or a model can no longer be used, stop and log a deviation
  before running anything.
- **No hand-typed numbers.** Tables and number macros come from `paper/tables.py`; figures from `scoring/figures.py`;
  comparisons from `scoring/stats.py`. The manuscript only `\input`s them.
- **Pipeline:** `score_all.py → summarize.py → stats.py → figures.py → paper/tables.py → latexmk`.
- **Concurrency and exclusion** as for T1 (`logs/deviations.md` §2–3): at most 2 Claude Code sessions, `--until`
  top-up, stop on HTTP 429. Runner: `harness/run_t2_t3_lanes.sh` (`A1_T1=10`, `T3B_OK=1`).
- **Protocol gate before T3b:** `scoring/check_blq_reference.py` decides whether the PKanalix reference follows the BLQ
  rule the T3b prompt states, using only input data and reference, never agent output.
- **Comparisons for non-NCA tasks** (T3d) are exploratory: `stats.py` may compute them, but the paper labels them as
  not pre-specified.
- **arXiv package:** TeX source + `.bbl` (arXiv does not run BibTeX reliably), figures as PDF, no line numbers, no
  `\TODO`. Built by a script, not by hand.

## Testing decisions
- Scorer: `python3 scoring/score_nca.py --calibrate` must still reproduce the paper's published scores (max |diff| 0.00)
  after any scorer change.
- Skills: `bash harness/test_all.sh` passes and `skills/FROZEN.sha256` verifies (the runner checks this).
- Analysis code: each new generator is run on the committed `results/` and its output inspected; the manuscript
  compiles with zero undefined references and zero overfull boxes.
- Isolation: `scoring/audit_isolation.py` flags 0 transcripts after the new runs.

## Out of scope
- Changing the frozen Skills (any change → `logs/skill_changes.md`, re-freeze, re-run affected arms).
- Tuning anything on PKanalix reference values.
- Other model families (stated as a limitation).
- Journal submission (after the preprint).

## Slices
Tracked as GitHub sub-issues of the spec issue. HITL = needs a human (the Mac with R, Docker, the supplement and the
Claude subscription, or an account action); AFK = an agent can do it in this repository alone.

| # | Slice | Type | Blocked by |
|---|---|---|---|
| S1 | Harness: refuse runs on a different Claude Code version | AFK | — |
| S2 | BLQ reference check for T3b | HITL | — |
| S3 | A1 T1 top-up to 10 runs, end to end | HITL | S1 |
| S4 | T3d oral 1-CM, end to end | HITL | S1 |
| S5 | T2 case study, end to end | HITL | S1 |
| S6 | T3a / T3c / T3e NCA stress tasks, end to end | HITL | S1 |
| S7 | T3b BLQ task, end to end | HITL | S1, S2 |
| S8 | Reproducibility: distinct parameter-value sets + terminal-point match | HITL | S3 |
| S9 | Infrastructure footprint table | HITL | — |
| S10 | Fig 1: architecture of the two stacks | AFK | — |
| S11 | Verify software and web references | AFK | — |
| S12 | Isolation audit, evidence bundle, Zenodo new version | HITL | S3–S7 |
| S13 | Finalise manuscript and co-author sign-off | HITL | S3–S12 |
| S14 | arXiv submission package and posting | HITL | S12, S13 |

## Known limitations to state in the paper
Single benchmark source (paper's 182-drug set, PKanalix as reference, not ground truth) · subscription runs, cost is
Claude Code's list-price estimate · user-global CLAUDE.md loaded in all arms equally (tool-usage rules only) · skills
written with Claude from package docs · A1 containers under Rosetta (wall time) · one model family (Claude) · ceiling
effect near 98.6% (remaining errors mostly λz point selection) · T1 comparisons specified after the T1 runs · A1 T1
runs 4–10 made about seven weeks after runs 1–3 (same pinned toolchain).
