# Spec: bioRxiv preprint — MCP platform vs Agent Skills for pharmacometrics agents

Status: open. Tracking issue: #2; one sub-issue per slice (#3–#16, see "Slices" below). This file is the
source of truth for scope and decisions; the issues are the work. The benchmark protocol itself is `../docs/PLAN.md`;
**where the two disagree, this file wins** (decided 2026-11-17).

Working title: *Do agentic pharmacometrics tools need server infrastructure? A controlled benchmark of an MCP
platform versus Agent Skills for noncompartmental analysis and PK workflows.*

## Problem statement
PMxAgent (Bloomingdale & Khot, CPT:PSP 2026;15:e70325) wraps validated R functions in Docker + R Plumber + an
OpenAPI-generated MCP server and reports 98.3% NCA accuracy with identical results across runs. Its comparison changes
the client, the model, the domain instructions and the execution of fixed code at the same time, so it cannot say
which of these produces accuracy and reproducibility. Our Letter to the Editor on this was cancelled (the journal does
not take letters on its open-access articles). The T1 (NCA) benchmark is complete; T2 and T3 have never run.

## Solution
A standalone research article, posted to **bioRxiv (Pharmacology & Toxicology)** once T2 and T3 are complete, that separates the three ingredients:
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
| 2026-11-16 | Venue: **bioRxiv**, Pharmacology & Toxicology (no endorsement needed). A later edit that switched this to arXiv misread the user and was reverted the same day | user |
| 2026-11-16 | Manuscript drafting: T1 sections were drafted before T2/T3, without asking first; the user had said to wait for T2 + T3. Further manuscript work waits for T2/T3 results (#15) | user |
| 2026-11-16 | Corresponding author: Dhruvik Pandya. Co-author Prof. Surjit Singh has agreed to the preprint | user |
| 2026-11-16 | Competing interests: none | user |
| 2026-11-17 | Rule "every new run uses Claude Code 2.1.283" removed. Replaced by **one pinned version per task**: T1 → 2.1.283 (A1 top-up), T2/T3 → 2.1.310 (the version of the first T2 reps). Harness runs a harness-owned pinned binary and refuses any other version (`env/versions.txt`, `logs/deviations.md` §15) | user |
| 2026-11-17 | A1 T2 = 10 reps, as specified here (the old plan said 3). This file wins over `docs/PLAN.md` | user |
| 2026-11-17 | A1 T1 runs 4–10 run **isolated** (no user instructions): the T1-era global CLAUDE.md cannot be recovered on this machine. Pre-specified sensitivity analysis by isolation regime (below), fixed before those runs | user |
| 2026-11-17 | T2 internal consistency: **primary = the pre-specified lin-up/log-down check**; the "either AUC rule" version (§13) is a labelled post-hoc sensitivity analysis | user |
| 2026-11-17 | Run order: A1 T1 top-up alone (T1 pin) → lanes on the T2/T3 pin (T3d, T2, T3a, T3c, T3e) → T3b after the BLQ check (S2). Lanes started from a Terminal tab the user can watch | user |
| 2026-11-20 | Two A1 T1 runs had no scorable file (drug without subject) and stay at 0 in the primary analysis; a **post-hoc** analysis without them is added and labelled as such. The preprint reports that A1's agent never called a PMxAgent tool on T1 (`logs/deviations.md` §17) | user |
| 2026-11-20 | No A1 variant whose prompt tells the agent to use PMxAgent's tools: A1 keeps the shared prompt and is reported as observed (C5). The tool-use count (`pmxagent_tool_calls`) is reported for every A1 run | user |
| 2026-11-20 | T2/T3 reps may run on **several subscription accounts** (token pool, `harness/tokens.py`): a rep uses the first account not at its usage limit; a 429 moves the arm to the next free account. Same pinned model, Claude Code version, prompts and isolation; still **at most 2 concurrent sessions in total** (§3). Ledger column `auth_label` records the account (label only). Rate-limited reps stay excluded whichever account ran them (`logs/deviations.md` §19) | user |
| 2026-11-20 | **Token pool, not one account per lane**: the lanes are uneven (A1 alone vs A0/A2/A3/A4), so a fixed account per lane would leave one account mostly idle | user |
| 2026-11-20 | T3b runs: the S2 BLQ check passed (prompt rule matches PKanalix for 220/220 subjects; #4, `logs/blq_check.txt`, deviations §18) | user |
| 2026-11-20 | Runs are started from a **clean Terminal tab** (`caffeinate -is bash harness/resume_lanes.sh`), never from inside a Claude session; `resume_lanes.sh` re-runs the lanes after every usage-limit reset until every lane is done, and stops on any other failure (exit codes: 0 done, 75 limit, else broken; §19) | user |

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
7. As the authors, we want a PDF that passes bioRxiv screening first time (reads as original research, no TODOs).

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
- **T2:** completion (results.json with 3 dose groups), internal consistency (group means recomputed lin-up/log-down from the
  agent's own simulated data, `score_all.py`), cross-run spread of EC50, seed and n_timepoints (reproducibility).
  No ground truth: report descriptively.
- **Comparisons (T1, and each NCA task):** A2−A1, A3−A1, A3−A2, A4−A3, A0−A3. Difference in mean overall accuracy,
  95% percentile bootstrap CI (10,000 resamples of runs within arm, seed 20261116) and two-sided exact/Monte-Carlo
  permutation p-value. Equivalence margin ±1.0 percentage point: "equivalent" only if the whole 95% CI lies inside it.
  No multiplicity adjustment; the CIs are the result, p-values are secondary.
- **Reproducibility:** SD of overall accuracy; number of distinct parameter-value sets per arm (hash of the scored
  individual table, sorted, values rounded to 6 significant digits). Distinct *file* sets reported separately.
- **Effort:** cost/run, wall time, turns, tool calls, tool errors (mean ± SD).
- **Reps:** T1 = 10 per arm (A1 currently 3, see R0), T2 = 10 per arm (A1 included), T3a–e = 5 per arm.

Added 2026-11-20, **post hoc** (after seeing the T1 scores; `logs/deviations.md` §17), at the author's request:
- **Unscorable-run sensitivity (post-hoc, labelled as such):** in each NCA task where a completed run had no
  scorable individual file (scored 0 above), per-arm stats and the pairs involving an arm that lost runs, repeated
  without those runs (`scoring/stats.py` → `results/stats_posthoc.csv`). The primary analysis is unchanged.

Added 2026-11-17, before any T2 score was computed and before A1 T1 runs 4–10 (`logs/deviations.md` §15):
- **T2 sensitivity (post-hoc, labelled as such):** internal consistency with either AUC rule (linear or
  lin-up/log-down) counted (`summary_consistent_any_rule_pct`), because the prompt names no rule (§13).
- **Isolation-regime sensitivity:** for an arm whose runs in a task used more than one isolation regime (T1-era
  "user instructions loaded" vs "isolated"), report that arm per regime and repeat each pre-specified comparison with
  that arm restricted to each regime (`scoring/stats.py` → `results/stats_sensitivity.csv`). Primary = pooled.

## Implementation decisions
- **One Claude Code version per task.** Every arm of a task runs on the same version, pinned in `env/versions.txt`
  (`claude-code-pin T1_nca: 2.1.283`, `claude-code-pin default: 2.1.310`). `run_arm.py` runs the pinned binary from
  `~/.local/share/pmxbench/claude/<version>/` (immune to the native installer's updates) and refuses any other
  version; `--allow-version-drift` overrides by hand and must be logged. Same pinned models and PMxAgent image digests.
- **No hand-typed numbers.** Tables and number macros come from `paper/tables.py`; figures from `scoring/figures.py`;
  comparisons from `scoring/stats.py`. The manuscript only `\input`s them.
- **Pipeline:** `score_all.py → summarize.py → stats.py → figures.py → paper/tables.py → latexmk`.
- **Concurrency and exclusion** as for T1 (`logs/deviations.md` §2–3): at most 2 Claude Code sessions, `--until`
  top-up, stop on HTTP 429. Runner: A1 T1 top-up first, alone (`run_arm.py run A1 T1_nca 10 … --until`), then
  `harness/run_t2_t3_lanes.sh` (`T3B_OK=1` after S2).
- **Protocol gate before T3b:** `scoring/check_blq_reference.py` decides whether the PKanalix reference follows the BLQ
  rule the T3b prompt states, using only input data and reference, never agent output.
- **Comparisons for non-NCA tasks** (T3d) are exploratory: `stats.py` may compute them, but the paper labels them as
  not pre-specified.
- **bioRxiv submission:** one PDF built from the LaTeX source (line numbers kept, figures embedded, no `\TODO`),
  built by a script, not by hand.

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

| # | Issue | Slice | Type | Blocked by |
|---|---|---|---|---|
| S1 | #3 | Harness: refuse runs on a different Claude Code version | AFK | — |
| S2 | #4 | BLQ reference check for T3b | HITL | — |
| S3 | #5 | A1 T1 top-up to 10 runs, end to end | HITL | S1 (#3) |
| S4 | #6 | T3d oral 1-CM, end to end | HITL | S1 (#3) |
| S5 | #7 | T2 case study, end to end | HITL | S1 (#3) |
| S6 | #8 | T3a / T3c / T3e NCA stress tasks, end to end | HITL | S1 (#3) |
| S7 | #9 | T3b BLQ task, end to end | HITL | S1, S2 (#3, #4) |
| S8 | #10 | Reproducibility: distinct parameter-value sets + terminal-point match | HITL | S3 (#5) |
| S9 | #11 | Infrastructure footprint table | HITL | — |
| S10 | #12 | Fig 1: architecture of the two stacks | AFK | — |
| S11 | #13 | Verify software and web references | AFK | — |
| S12 | #14 | Isolation audit, evidence bundle, Zenodo new version | HITL | S3–S7 (#5–#9) |
| S13 | #15 | Finalise manuscript and co-author sign-off | HITL | S3–S12 (#5–#14) |
| S14 | #16 | bioRxiv submission PDF and posting | HITL | S12, S13 (#14, #15) |

## Known limitations to state in the paper
Single benchmark source (paper's 182-drug set, PKanalix as reference, not ground truth) · subscription runs, cost is
Claude Code's list-price estimate · user-global CLAUDE.md loaded in all T1 arms equally (tool-usage rules only) except A1 runs 4–10, which ran
isolated (sensitivity analysis by regime); T2/T3 load no user instructions · skills
written with Claude from package docs · A1 containers under Rosetta (wall time) · one model family (Claude) · ceiling
effect near 98.6% (remaining errors mostly λz point selection) · T1 comparisons specified after the T1 runs · A1 T1
runs 4–10 made about seven weeks after runs 1–3 (same pinned Claude Code, models and images) · T2/T3 on a later
Claude Code version than T1 (2.1.310 vs 2.1.283; within-task comparisons unaffected) · A1's agent never called a
PMxAgent tool on T1 (0/10 runs; it wrote its own PKNCA code), so A1 is "PMxAgent offered", not its NCA endpoint; two A1
T1 runs unscorable (drug without subject), analysis without them is post hoc (§17).
