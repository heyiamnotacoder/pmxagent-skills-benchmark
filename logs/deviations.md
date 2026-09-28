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
