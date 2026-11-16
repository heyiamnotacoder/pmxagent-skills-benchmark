# Protocol log and deviations

Everything that departed from `PLAN.md`, in time order (IST, 2026-09-28). Nothing listed here was decided by looking at
accuracy scores; the only exclusion rule is "run did not finish because the API returned HTTP 429 (usage limit)".

## Rules that held throughout
- Model pinned per arm: `claude-sonnet-4-6` (A0–A3), `claude-haiku-4-5-20251001` (A4). Verified per run from the
  `modelUsage` block of the Claude Code result event (`model_seen` column in `results/runs.csv`).
- Each rep = fresh headless `claude -p` process in a fresh detached git worktree of the task branch. No conversation
  is resumed; auto-memory off (`CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`); `--setting-sources project`, `--strict-mcp-config`;
  git/gh/WebSearch/WebFetch disallowed.
- Skills frozen before any benchmark run (`skills/FROZEN.sha256`, checked by the runner before every A2/A3/A4 run).
- Runs used a Claude subscription, not an API key. `cost_usd` is Claude Code's list-price estimate from token counts.
- Known leak, accepted: the user's global `~/.claude/CLAUDE.md` (tool-usage rules only: Playwright, Firecrawl, ripgrep,
  "don't delete infrastructure") is loaded in every arm equally. Confirmed by preflight.

## 1. Usage-limit failures (12:33–12:45)
First matrix launched all 5 arms × all tasks in parallel at ~12:22. At ~12:33 the subscription session limit was hit
("You've hit your session limit · resets 3:30pm"). 174 runs failed instantly (0 tokens) and 5 were cut off mid-run.
- Ledger status set to `failed_ratelimit` / `failed_ratelimit_midrun` (original ledger kept as
  `results/runs.csv.bak-20260928`). Raw transcripts kept in `results/raw/`. Excluded from scoring; counted in
  `results/summary.md` column `n_invalid_excluded`.
- No valid T2/T3 run exists from this matrix; all T2/T3 attempts were usage-limited.

## 2. Top-up rule (from 15:45)
Missing reps were re-run with `run_arm.py run ... --until`: run until the arm has N valid reps (N = 10; A1 = 3, as
planned, because of cost/time), stop immediately on a 429. Every completed run counts, whatever its score.

## 3. Concurrency reduced to 2 sessions (from 15:45)
To save subscription usage: at most 2 simultaneous Claude Code sessions (A1 in one, the other arms one after another
in the second; after A1 finished, the second slot ran A3→A4). May change wall time slightly; does not change prompts,
tools or models.

## 4. Sibling-run isolation tightened (15:44)
Before: finished worktrees stayed under `~/pmxbench_runs/<arm>/runs/`, readable by a later agent in principle
(agents run with bypassPermissions). Audit of all transcripts up to then (`scoring/audit_isolation.py`): **no run
referenced another run's folder, a parent folder, or `~/.claude/projects`**.
After: each finished rep (worktree, A1 `/data/<runid>` folder, MCP config) is moved with `git worktree move` to
`~/pmxbench_archive/<arm>/` (mode 0300, not listable). Earlier runs moved there too. Nothing deleted.
Re-audit of all tool calls in all 225 transcripts at 16:2x (incl. failed and preflight runs): 0 flagged
(`results/isolation_audit.csv`; 228 after the last run: 0 flagged). Positive control: the audit flags listing `runs/`, reading a sibling run's file,
the archive, `../`, and `~/.claude/projects`, and does not flag the run's own folder.

## 5. Scorer: parameter-name aliases (naming only)
Agents name parameters freely (`CLFO`, `CL/F_obs`, `Vz/F_obs`, ...). The scorer's alias table was extended twice so
these spellings map to the same parameter. Values are never changed. After each change `score_nca.py --calibrate`
reproduces the paper's published scores exactly (max |diff| 0.00), and all runs were re-scored with the same table.
- 16:1x: added `cl/f_obs`, `vz/f_obs`, `cl/f`, `vz/f`, `adj_r_squared` (one A1 run went from 81.55 to 97.97;
  CL/Vz values were present but unrecognised).

## 6. Runner bug (A1 only, not T1)
A1 crashed on tasks with no input files (T2, T3d) because git does not track empty folders. Fixed; no T1 run affected.

## 7. Scope
2026-09-28: user decision — compare arms only, and complete Task 1 (NCA benchmark) first. T2/T3 not run yet.

## 8. Docker
PMxAgent stack stopped at the user's request after the first matrix and restarted for the A1 top-up (15:45), then
stopped again when A1 finished (15:59). Same pinned image digests (`env/versions.txt`); every A1 run is independent.

---
# Task 2 (case study) — from 2026-11-16 (IST)

## 9. Restored on a fresh checkout
The original working copy was not on this machine. The repo was cloned from GitHub; PMxAgent was re-deployed from its
public tag `v1.0.0` into `~/pmxbench_runs/_pmxagent` and started from the **same image digests** as T1
(`env/versions.txt`). T2 needs no supplement data. Arm repos rebuilt with `run_arm.py setup` from the frozen skills
(hashes verified, all skill tests pass).

## 10. Environment drift since T1
Claude Code 2.1.283 → 2.1.310, R 4.6.1 → 4.6.2, Python 3.14.7 → 3.15.2, Docker 29.8.1 → 29.9.2. All R packages
(PKNCA, mrgsolve, rxode2, nlmixr2lib, …) unchanged. Same for every T2 arm; the Claude Code version is in the ledger
per run. T1 and T2 are separate comparisons, so drift between them does not affect any within-task arm comparison.

## 11. Isolation: no user instructions in T2 (stronger than T1)
The user's `~/.claude/CLAUDE.md` and `~/.claude/rules/` had grown since T1 (they now include working-style rules such
as "write tests first" and a PR workflow) and could change agent behaviour on an open-ended task. Preflights traced
how they reach a rep:
- **Mechanism (also T1's accepted leak):** Claude Code reads `CLAUDE.md` and `.claude/rules/` from *every ancestor*
  of its working directory. T1 worktrees lived under `~/pmxbench_runs/`, so `/Users/dhruvik/.claude/CLAUDE.md` and
  its rules loaded as ancestor *project* instructions, which `--setting-sources project` does not exclude. An empty
  `CLAUDE_CONFIG_DIR`, then an empty `HOME`, did not help (preflights quarantined under `results/raw/*/_preflight/`,
  rep 0, never scored). A probe outside `~` with a sentinel `CLAUDE.md` in the config dir loaded nothing.
- **Fix:** arm workspaces moved to `/Users/Shared/pmxbench_runs/` (no `.claude/` in any ancestor). PMxAgent stays
  under `~` (colima mounts only the home folder); agents only read/write its data folder, they never run there.
- **Also:** each rep gets a whitelisted environment (`PATH`, locale, `TERM`, `TMPDIR`, user/shell). The harness had
  been launched from a Claude Code desktop session whose ~35 `CLAUDE_*`/`ANTHROPIC_*` variables (incl. a proxy base
  URL) would otherwise pass to every rep. Each rep also gets its own empty `HOME` + config dir (archived with the rep;
  earlier reps' session files unreachable), authenticated by a subscription token from `claude setup-token`
  (environment only, never logged). Ledger column `claude_config` = `isolated` (empty for T1 runs).
- **Check:** final preflights on A0/A2/A3/A4 (2026-11-16 21:58) report no CLAUDE.md/rules/memory, the pinned model,
  and the expected skills (none for A0, the 5 pmx skills for A2–A4). Decided and verified before any T2 run.

## 12. Harness and scorer changes (no effect on T1 numbers)
- `run_arm.py setup` handles tasks with no input files (T2, T3d) on a fresh clone.
- Ledger writer rewrites the header when a run adds a column, so old rows stay aligned (`harness/tests`).
- `score_all.py`, `summarize.py`, `audit_isolation.py` update their tables by run ID and keep rows for runs whose raw
  files are not on this machine (T1 raw is on Zenodo); distinct-output counts fall back to the evidence manifest.
  Check: re-running all three with no raw files leaves every committed T1 file byte-identical.
- T2 scorer also finds A1's simulated data under `pmxagent_data/` (container paths in `results.json` are matched
  by path suffix) (`scoring/tests`).
- Isolation audit: project-path pattern now also matches `projects/pmxagent`; A1's own `/data/<runid>` host folder
  is no longer counted as another run's area.
- Run-root guard (added 2026-11-16 ~22:05, while A0 T2 reps were running; a check only, no change to what a rep
  sees): `/Users/Shared` is world-writable, so another local user could plant `CLAUDE.md`/`.claude/` in an ancestor
  of the workspaces. `run_arm.py` now refuses to run unless the run root is owned by the user with mode 0700 and no
  ancestor holds `CLAUDE.md`, `CLAUDE.local.md` or `.claude/`; reps run with umask 077. Verified at the time: no such
  files in any ancestor, so earlier reps were unaffected.

### §13 T2 scorer: either AUC rule counts (2026-11-16, ~22:20, before any T2 scoring)
The first finished rep (A0 r11) reported group means from **linear-trapezoidal** AUClast; they match its own
simulated data exactly, but the scorer only recomputed lin-up/log-down, so it read 50% consistent. The verbatim prompt
names no AUC rule, so `score_case_run` now accepts either (`AUC_RULES`) and records which one the run used
(`auc_method`: linear / lin-up/log-down / mixed / none). The same rule applies to every arm; found on the scorer's
first real input, not tuned on any arm's results. Test: `test_linear_trapezoidal_summary_counts_as_consistent`.
