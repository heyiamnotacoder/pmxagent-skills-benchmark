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
| 2026-11-21 | **Secondary arm `A1b` on `T1_nca` (10 reps, T1 pin `2.1.283`, isolated):** PMxAgent 1.0.0 MCP **plus PMxAgent's shipped `v1.0.0` `CLAUDE.md`** (pinned SHA-256 `1ebc55d4…`), using the **exact same task prompt** (no prompt change). Motivated by finding that PMxAgent's multi-drug `/NCA` support is documented only in its repo `CLAUDE.md` and absent from `openapi.json`. Primary `A1` (bare MCP, 10 reps) stays unchanged; `A1b` is reported alongside it (`results/stats_secondary.csv`, `logs/deviations.md` §21). Also log direct Plumber HTTP calls (`pmxagent_http_calls`) alongside MCP calls (`pmxagent_tool_calls`) | user |
| 2026-11-21 | **Crash/timeout vs HTTP 429 reporting & isolation audit clarity:** separate `n_crash_timeout` from `n_invalid_excluded` (HTTP 429) in `results/summary.{csv,md}` (`harness/ledger.py`, `scoring/summarize.py`), and mark protocol-excluded runs in `results/isolation_audit.csv` so valid vs excluded flagged counts are shown distinctly (§21) | user |
| 2026-11-21 | **Arm failures count, infrastructure failures repeat:** a rep that did real work and then crashed / timed out / ended in error (no API/auth error) is a valid run scored on what it left; API/auth errors, no-work reps and harness-bug statuses are repeated. Replaces the "relabel only" split of §21, which still re-ran every crash. No valid run changes (the only such rep so far, `A1_T3a_messy_r07`, is already excluded under §20). Also: `A1b` relabelled **post hoc** (specified after A0–A4 T1 results were known), with the doc-authorship and timing disclosures (§22) | user |
| 2026-11-24 | Manuscript finalised against C1–C5 (#15): "did not use PMxAgent's tools for NCA" softened to "rarely" (A1 called its NCA tool in 1 of 30 NCA-task runs, all in T3a; generated macro `\numNcaAonePmxRuns`); T3 reproducibility claim limited to A3 (A4 varied on T3a); T3d wording corrected (A1 wrote code and did not solve it in every run). Limitations regrouped and extended for T2/T3 | — |
| 2026-11-24 | Corresponding e-mail: personal Gmail. Funding: no specific grant. CRediT: D.P. conceptualization, methodology, software, investigation, formal analysis, data curation, visualization, writing (original draft, review & editing); S.S. conceptualization, supervision, validation, writing (review & editing). Code cited as GitHub URL + release tag `v1.0-preprint` (the name #16 already uses; tag created at posting). Use-of-AI statement checked against the bioRxiv FAQ ("How should I acknowledge the use of generative AI", read 2026-11-24): use described in the manuscript, authors accountable, no AI author | user |
| _pending_ | Prof. Surjit Singh read and approved the full draft (#15) | S.S. |

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
  *Amended 2026-11-21 (`logs/deviations.md` §22), before any run the amendment could change:* a rep in which the
  agent did real work (cost or tool calls > 0) and then crashed, hit the time limit or ended in error, with no API/auth
  error behind it, is an **arm failure**: it is a valid run, scored on whatever it left (no scorable output → 0), and
  is not repeated. A rep that ended on an API/auth error, did no work, or carries a harness-bug status is an
  **infrastructure failure**: not scored and repeated, like a usage-limit stop. A harness bug that only shows after
  real work is excluded through `results/exclusions.csv` with its deviation, decided from the setup, never the score.
  Rule in `harness/ledger.py` (`arm_failure`, `infra_failure`, `valid`).
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

Added 2026-11-21, **post hoc** (`logs/deviations.md` §21, relabelled in §22): motivated by A1's observed behaviour on
T1 (0/10 runs called a PMxAgent tool), not by any score, but specified after the T1 results of A0–A4 were known;
fixed before any `A1b` run. Report `A1b` and its comparisons as post hoc:
- **Secondary arm `A1b` on `T1_nca` (10 reps, `claude-sonnet-4-6`, T1 pin `2.1.283`, isolated):** PMxAgent 1.0.0 MCP
  plus PMxAgent's verbatim shipped `v1.0.0` `CLAUDE.md` (SHA-256 `1ebc55d43c4a3142ed50b2c78efcea22c67bed522f3bc4d81a6bf379e295be8c`)
  in the workspace, with the **same verbatim T1 task prompt** (and same `SUFFIX` + `SUFFIX_A1` as `A1`). Reported
  alongside primary `A1`, never instead of it. Secondary comparisons (`results/stats_secondary.csv`, same 10,000-resample
  percentile bootstrap CI and exact/MC permutation p-value, ±1.0 pp margin): `A1b − A1`, `A2 − A1b`, `A3 − A1b`,
  `A4 − A1b`. Both MCP calls (`pmxagent_tool_calls`) and direct Plumber HTTP calls (`pmxagent_http_calls`, `:5762`) are
  reported per run.

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
- **No hand-typed numbers.** Tables and number macros come from `paper/tables.py`; figures from `scoring/figures.py` (Fig 1: TikZ source `paper/figures/fig_arch.tex`, arm colours kept in step by `scoring/tests/test_fig_arch.py`);
  comparisons from `scoring/stats.py`. The manuscript only `\input`s them.
- **Pipeline:** `score_all.py → summarize.py → stats.py → figures.py (+ `fig_arch.tex`, Fig 1) → paper/tables.py → latexmk`.
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
- Isolation: `scoring/audit_isolation.py` flags 0 **valid** transcripts after the new runs (protocol-excluded pre-§20 A1 transcripts are marked `excluded=True` and reported separately).

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
| S3b | — | A1b T1 secondary arm (PMxAgent MCP + shipped `CLAUDE.md`), 10 reps (§21) | HITL | S1 (#3) |
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
Kept in step with the Limitations section of `main.tex` (grouped there as benchmark and models · arms · T1 protocol ·
T2 and T3).

**T2 and T3 (added 2026-11-24, #15):** T2 has no reference answer (completion, internal consistency and agreement
between runs only) · T2 EC50 summary, unit conversion and the 1% rule for the comparison with PMxAgent's published
EC50 chosen after the data were seen · scorer's reading of agents' T2 files hand-checked on a fixed subset only
(`check_t2_parser.py`; `SUBJID` fix after the first T2 results, changing no computed value) · T3 has 5 runs per arm
(wide intervals); T3d comparisons exploratory · T3 prompts, unlike T1's, state how to identify subjects, so T1's
unscorable-output failure could not recur in T3 · A1 T2/T3 runs made before PMxAgent's shared folders were emptied were
excluded and repeated (§20, decided from run timing) · T2/T3 spread over two subscription accounts (same model and
Claude Code version within a task; §19) · the λz error split by terminal-point match is descriptive and post hoc (§26) ·
Skills written by the study authors (frozen before any run, output not compared with PKanalix before the freeze) ·
one client (Claude Code) as well as one model family · all A1b runs, like A1 runs 4–10, ran isolated · over the five NCA
tasks A1's agent called a PMxAgent tool in 1 of 30 runs (one T3a run; `\numNcaAonePmxRuns`), so "rarely", not "never".

**Earlier list:** Single benchmark source (paper's 182-drug set, PKanalix as reference, not ground truth) · subscription runs, cost is
Claude Code's list-price estimate · user-global CLAUDE.md loaded in all T1 arms equally (tool-usage rules only) except A1 runs 4–10, which ran
isolated (sensitivity analysis by regime); T2/T3 load no user instructions · skills
written with Claude from package docs · A1 containers under Rosetta (wall time) · one model family (Claude) · ceiling
effect near 98.6% (remaining errors mostly λz point selection) · T1 comparisons specified after the T1 runs · A1 T1
runs 4–10 made about seven weeks after runs 1–3 (same pinned Claude Code, models and images) · T2/T3 on a later
Claude Code version than T1 (2.1.310 vs 2.1.283; within-task comparisons unaffected) · A1's agent never called a
PMxAgent tool on T1 (0/10 runs; it wrote its own R PKNCA code instead), so primary A1 is "bare PMxAgent MCP offered". `openapi.json` omits `/NCA`'s multi-drug/mixed-route support, which is documented only in `pmxagent-main/CLAUDE.md` (checked); that this gap is *why* the agents wrote their own code is a hypothesis, not an observation, and post-hoc secondary arm `A1b` tests it by adding that shipped `v1.0.0` `CLAUDE.md` with the same prompt (§21, §22). That document was written by PMxAgent's authors (who also built the 182-drug benchmark) and describes this dataset's `/LIBRARY` benchmark → `/NCA` workflow (dataset-specific guidance, no reference values). `A1b` runs about 8 weeks after the A0/A2–A4 T1 runs (28 Sep) and one day after A1 runs 6–12 (same pinned Claude Code, model ID and images); two A1
T1 runs unscorable (drug without subject), analysis without them is post hoc (§17) · minor within-arm drift in A0 T2 (`r11–r13` ran under `bypassPermissions` without env scrub; `r15–r21` under `default` + `--allowedTools` + scrub; §21).
