# Protocol log and deviations

Everything that departed from `docs/PLAN.md`, in time order (IST, 2026-09-28). Nothing listed here was decided by looking at
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

### §14 T2 usage-limit stop labelled in the ledger (2026-11-17)
At 22:23 IST on 2026-11-16 the subscription's 5-hour limit was reached (`429 usage_limit_reached`, "resets 12am").
Two reps were cut off mid-run: **A0 r14** (7 turns) and **A1 r01** (10 turns). The runner saw the 429, kept both out
of scoring and stopped both lanes as designed (§2), but wrote the bare exit code (`exit1`) to the ledger, so a 429
stop could not be told apart from a real crash. `run_arm.run_status` now writes the §1 labels itself
(`failed_ratelimit` = no tokens, `failed_ratelimit_midrun` = partly run); the two rows were relabelled
`exit1` → `failed_ratelimit_midrun` (original status in `logs/t2_lane_*.log`). No effect on any score: both rows were
already excluded. Test: `harness/tests` `RunStatus`.

### §15 Branches merged, Claude Code pinned per task, A1 top-up isolation, test-artifact clean-up (2026-11-17, ~22:15–23:00 IST)
Decided with the user before any T2 score was computed and before A1 T1 runs 4–10 (`paper/SPEC.md` decisions log).
- **Branches.** The preprint branch (`paper/SPEC.md`, analysis plan of commit `08ea7b3`, stats/figures/tables, the
  Claude Code version guard of issue #3) and the T2 branch (isolation §11–12, T2 scorer §13) had diverged from
  `d09381a`. Merged; only `CLAUDE.md` conflicted (text only). The guard had never been active for the T2 reps.
- **Version rule.** SPEC said every new run uses 2.1.283; the first T2 reps (A0 r11–r14, A1 r01) ran on 2.1.310 and
  2.1.325 is now installed. The user removed that rule. New rule: **one pinned version per task** —
  `claude-code-pin T1_nca: 2.1.283` (A1 top-up, same as all T1 runs), `claude-code-pin default: 2.1.310` (T2/T3, same
  as the existing T2 reps). `run_arm.py` runs a harness-owned binary from `~/.local/share/pmxbench/claude/<version>/`
  (2.1.283 from npm, 2.1.310 copied from the native install) and refuses any other version; reps get
  `DISABLE_AUTOUPDATER=1`. The ledger's `claude_version` is read from that binary.
- **A1 T1 runs 4–10: isolated.** Runs 1–3 loaded the user's global CLAUDE.md (§ "Rules that held throughout"). That
  file has changed since; its T1-era text is not in Claude Code's file history and Time Machine could not mount its
  disk, so the T1 condition cannot be reproduced. Runs 4–10 therefore load no user instructions. Pre-specified
  sensitivity: `scoring/stats.py` reports A1 per regime and repeats A2−A1 and A3−A1 on each regime (primary = pooled).
- **T2 consistency.** Primary = the pre-specified lin-up/log-down check (`summary_consistent_pct`); the §13 "either
  rule" value is kept as a post-hoc sensitivity column (`summary_consistent_any_rule_pct`).
- **A1 T2 = 10 reps** (SPEC), not 3 (old runner/PLAN). `run_t2_two_sessions.sh` superseded by `run_t2_t3_lanes.sh`.
- **Test artifacts (no effect on data).** After the merge, the version-guard tests from the preprint branch still
  assumed the run root lived under `HOME`; with the run root at `/Users/Shared/pmxbench_runs` the "version matches"
  tests ran a stub `claude` as real A0 T1 reps and appended 9 rows (`status ok`, 0 tokens, `claude_version 9.9.9`)
  to `results/runs.csv` at 22:16–22:28. The ledger was restored from git (byte-identical to the committed file); the
  9 raw folders were moved to `results/raw/A0/_test_artifacts/` and their worktrees to
  `~/pmxbench_archive/_test_artifacts/A0/` (nothing deleted). The tests now use a private temporary run root and fail
  if the real ledger changes.
- **`--until` bug.** A leftover preflight worktree (rep 0) counted as a rep in progress. Every arm had one (16 Nov
  preflights, named `*_T1_nca_r00_*`), so the A1 T1 top-up would have stopped at 9 instead of 10; T2 counts were not
  affected (different task name). Fixed (`rep_state`, test in `harness/tests`); preflights are now archived like reps,
  and the five leftover preflight worktrees were moved to `~/pmxbench_archive/<arm>/`.
- **Code review of PR #20 (2026-11-17, ~23:30 IST).** (a) Reps now get `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1`: in
  isolated mode the subscription token is in the rep's environment, and the agent's own Bash/R/Python subprocesses
  inherited it, so an agent running `env` could have written it into a transcript that is later published. Checked
  before the fix: no file in `results/raw/` or `~/pmxbench_archive/` contains the token. The variable only removes
  credentials from subprocess environments; the 3 valid A0 T2 reps ran without it, all later reps run with it.
  (b) `auc_method` was `mixed` instead of `none` for a T2 run where no dose could be compared (label only; both
  consistency values were already empty). (c) `preflight` takes an optional task, so the T2/T3 binary can be probed.

### §16 Tool permissions made explicit: the §15 scrub silently denied every tool (2026-11-20, before any rep with it)
- **Found in a preflight before the A1 T1 top-up.** With `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1` (§15 (a)) Claude Code
  ignores `--permission-mode bypassPermissions` and forces mode `default` (stderr: "Permission mode forced to default
  — CLAUDE_CODE_SUBPROCESS_ENV_SCRUB is set … Declare allowedTools explicitly"). In a headless `-p` run that denies
  every tool call. Reproduced on both pins (2.1.283 and 2.1.310): a one-line Bash write was denied with the scrub and
  ran without it. The old preflight could not see this because its probe told the agent not to use tools.
- **No benchmark rep is affected.** The scrub went in after the last reps (16 Nov); the only run with it before this
  fix is the A1 T1 preflight of 20 Nov 15:49 IST (rep 0, never counted).
- **Fix (harness only, credentials stay scrubbed).** `run_arm.py` now passes `--permission-mode default` and an
  explicit `--allowedTools` list: the 27 built-in tools in the init event of the valid A0 T2 reps (2.1.310), plus
  for A1 the `mcp__pmxagent` server and the three MCP resource tools. That is every tool the agent is shown: the same
  list as in the A1 T2 rep and the A1 preflights on 2.1.283 (the T1 pin; the valid T1 transcripts are on Zenodo, not
  local). The permission mode changes nothing the agent sees (same init-event tool list in both modes), and
  `--disallowedTools` (web, `git`, `gh`) still wins. Not equivalent in one respect: `default` mode may still refuse
  actions Claude Code guards even under an allow rule (e.g. writes outside the working directory or to protected
  paths), which `bypassPermissions` allowed; any such refusal shows up in the new `permission_denials` column.
- **Preflight is now a gate.** The probe makes two Bash calls, one that must run (writes `output/preflight.txt`) and
  `git --version`, which must be denied, so every preflight records that deny rules still beat the allow-list.
  `preflight` exits non-zero on any other denial, git not denied, the forced-mode warning, a missing probe file, or a
  tool shown but not allowed. `run_t2_t3_lanes.sh` now preflights every arm before any rep (A1 inside its lane, once
  the stack answers), and the A1 T1 top-up command runs `preflight` first. Passed on 20 Nov (~16:30 IST) for A1 on the T1 pin
  and A0–A4 on the T2/T3 pin (`results/raw/<arm>/_preflight/`). Also checked by hand on 20 Nov (transcript
  not kept): A1's `mcp__pmxagent__health` runs.
- **Ledger.** New columns `permission_mode` and `permission_denials` (count) for every run; `run` prints a warning
  for a rep with any denial. Denials are recorded only; they are not an exclusion criterion (SPEC.md: the only
  exclusion rule is the usage limit).

### §17 No valid A1 T1 run called PMxAgent; two A1 runs unscorable; post-hoc sensitivity (2026-11-20, ~23:00–00:30 IST)
- **Scored after the supplement was restored.** The supplement was re-downloaded and unpacked at the repo root.
  `build_tasks.py` rebuilt every input unchanged except `T3a_messy/inputs/pk_raw.xlsx`: same 30 sheets with identical
  cells, but in a different order, because R's `list.files()` sorts by locale and this shell had `LANG` unset. The
  committed workbook was restored (no T3a run had started), and `build_tasks.py` now sorts sheets case-insensitively
  with `method='radix'`, which reproduces the committed order under any locale. (The file's xlsx timestamps still change
  on every rebuild; inputs are restored from git, not rebuilt, between runs.) `score_nca.py --calibrate`: max |diff| 0.00.
- **T1 raw outputs restored from Zenodo.** The evidence archive (doi:10.5281/zenodo.23019418, sha256 matches
  `results/evidence/provenance.json`) was unpacked into `results/raw/` without overwriting; all 1,298 raw-run files
  match `results/evidence/MANIFEST.sha256`. Re-scoring them reproduced every committed T1 score exactly.
- **Two A1 T1 runs scored 0.** `A1_T1_nca_r07_20261120-221734` and `A1_T1_nca_r11_20261120-223637` completed and wrote
  `output/nca_individual.csv` (16,380 rows), but the `DRUG` column holds the drug name only (`abatacept`), not
  `<drug>_<subject>`, so no row maps to a reference subject: "no scorable individual file", overall 0. The T1 prompt
  (the paper's, verbatim) names the columns but not the subject identifier. Primary analysis unchanged: SPEC.md says
  every completed run counts. The scorer now scores such a run as an empty table with the same metric, so every
  parameter column is 0 as well as `overall` (before, only `overall` was 0 and the per-parameter cells were blank).
- **No A1 run called PMxAgent.** Counting `mcp__pmxagent__*` tool calls in every A1 transcript (new `scores.csv`
  column `pmxagent_tool_calls`): 0 in all 10 valid T1 runs (Sept and Nov) and in A1 T3d rep 1. The server was
  `connected` with its 6 tools listed in every init event. In each run the agent loaded the NCA tool's definition via
  `ToolSearch` and then wrote its own PKNCA script. The zeros are therefore not a PMxAgent code defect; they come from
  the agent's own code. A1 measures "agent with PMxAgent offered", not PMxAgent's NCA endpoint. Reported in the preprint
  as observed (SPEC.md C5 wording rule). The tools were callable: the rate-limited (invalid, unscored) rep
  `A1_T2_case_r01_20261116-222204` made 7 PMxAgent calls.
- **Per-parameter zeros are post hoc too.** Scoring every parameter of an unscorable run as 0 was made explicit after
  the scores were seen; it changes A1's per-parameter cells in `tab_accuracy_T1_nca`, not any `overall`. Stated so in
  the preprint's Methods.
- **Post-hoc sensitivity (decided after seeing the scores, labelled post hoc).** Requested by the author: each NCA task
  with an unscorable run is also analysed without those runs (`scoring/stats.py` → `results/stats_posthoc.csv`,
  per-arm rows in `results/stats_posthoc_arms.csv`, section in `results/stats.md`; macros `...PostHoc`). The primary
  analysis is unchanged. The pre-specified isolation-regime split (§15) is now also reported in the preprint: both
  unscorable runs are in the `isolated` regime (A1 runs 4–10).
- **Reproducibility TODO closed.** With the raw outputs local, `stats.py` computes distinct parameter-value sets for T1;
  the preprint now cites them through macros.

### §18 T3b protocol check (S2, #4): reference follows the prompt's BLQ rule (2026-11-20, ~23:30 IST)
- Protocol check, not a deviation. `scoring/check_blq_reference.py` (input data and PKanalix reference only, never
  agent output) on the 220 subjects with a BLQ record after Tmax: PKanalix AUClast is matched within 1% by the prompt's
  rule (BLQ before Tmax = 0, after = missing) for 220/220, by `drop` for 208/220 and by `zero` for 82/220. Output:
  `logs/blq_check.txt`. Decision, as pre-specified in #4: T3b runs as built (no prompt or reference change, no task
  rebuild); the T2/T3 lanes are started with `T3B_OK=1`.

### §19 Runs on several subscription accounts (token pool) (2026-11-20, ~23:30 IST; first rep with it 23:39)
- **Why.** One account's 5-hour usage limit stopped the T2/T3 lanes twice (§14; 20 Nov 22:48). The author asked to use
  a second account alongside the first.
- **What.** `harness/tokens.py`: each account's `claude setup-token` token is a file
  `~/.config/pmxbench/tokens/acct<N>`; only names of that form count, so no personal name or e-mail can become a label
  (labels go into the ledger and the published evidence). `run_arm.py` gives each rep the first free account (label
  order). A rep stopped by HTTP 429 marks its account limited until the reset time of the **rejected** rate-limit
  window the API reported (not the weekly window also present in transcripts), clamped to 1 min .. 7 days ahead; a
  401/403 marks the account unusable for a day; an empty token file is skipped. State: `~/.config/pmxbench/limits.json`
  (labels and epochs only), replaced atomically under a lock file, so both lanes share it. With `--until` the arm
  continues on the next free account (at most once per account in a row, so a stale reset time cannot make it spin)
  and stops only when every account is limited. Without any `acct<N>` file the old single `oauth_token` is the pool
  (`default`), so earlier behaviour is unchanged; once `acct<N>` files exist, the old file is ignored, so it was moved
  to `tokens/acct1`. New ledger columns: `auth_label`, `api_error_status`.
- **What stays the same.** Pinned model, pinned Claude Code version per task, prompts, Skills, isolated HOME per rep,
  credential scrub, permissions, and at most 2 concurrent sessions in total (§3). The token is never logged.
- **What can differ.** Prompt-cache hits are per account, so cache-read tokens and the list-price cost estimate of a
  rep may depend on which account ran it (and on which account ran the previous reps). New ledger column
  `auth_label` records the account per rep so this can be checked. Accuracy endpoints are unaffected.
- **Exclusions unchanged.** Rate-limited reps (`failed_ratelimit*`) never count, whichever account ran them (§1).
- Chosen over one account per lane because the lanes are uneven (A1 alone vs four arms).
- **Launch (added 23:45 IST).** The first launch with the pool (23:37, reps from 23:39) was the same wrapper,
  `resume_lanes.sh`, started by the Claude session that wrote it. At the author's request it was moved to a Terminal
  tab. The wrapper was killed (no rep runs inside it) and the lanes were drained rather than killed: both accounts
  were marked limited with a placeholder reset in 2100, so each arm finished its rep in flight and stopped before
  the next one. No worktree was left behind; all 5 preflights and 5 reps of that launch (`ok`, `acct2`) are kept.
  The real limits were then restored (`acct1` until 03:10, `acct2` free).
- **resume_lanes.sh (reviewed before use).** Exit codes are the contract: `run_arm.py` exits 75 when it stops on a
  usage limit or API failure (also when a preflight probe itself hits a 429), `run_t2_t3_lanes.sh` waits for each lane
  and exits 0 (all done), 75 (a lane stopped on a limit) or the broken lane's code. The wrapper re-runs the lanes on
  75 (every account limited: earliest reset + 5 min, re-checked each minute; an account free: API failure, 30 min),
  stops on 0, and stops on any other code (needs a human). It refuses to run inside a Claude Code session, holds a
  lock so only one copy runs (§3: at most 2 sessions), and gives up after 30 limit windows. The A1 lane waits at most
  30 min for the PMxAgent stack. From 23:5x the lanes run from a Terminal tab.

### §20 A1 reps shared PMxAgent's output folders; all A1 T2/T3 reps so far excluded and re-run (2026-11-21, ~12:10 IST)
- **Found by** `scoring/audit_isolation.py`, run on the T2/T3 ledger snapshot of 21 Nov (12:0x IST), before any A1
  T2/T3 accuracy was looked at. 11 A1 runs flagged (`run_area`), against none in the last committed audit.
- **Cause.** The harness gives each A1 rep its own `/data/<runid>/` folder (prompt suffix, archived per rep), but
  PMxAgent's tools write their outputs to the **top** of its `/data/` and `/figures/` mounts. On this machine those are
  one pair of folders (`~/pmxbench_runs/_pmxagent/{data,figures}/`) shared by every A1 rep and never emptied. In every
  flagged T2 run the agent listed that folder and copied the newest `pk_simulation_*.csv`; A1 reps run one at a time,
  so that file was most likely its own, but earlier reps' outputs were visible. In T3a, `A1_T3a_messy_r07` wrote ~35
  processed `*_nca_ready.csv` files there, visible to the next rep. (`A1_T3d_oral_r04`'s `claude_state` hit was its own
  per-rep HOME's tool-result file: a false positive, now not counted.) T1 is unaffected: no valid A1 T1 run called a
  PMxAgent tool (§17), and the audit flags none of them.
- **Decision (author, 21 Nov).** Every A1 T2/T3 rep recorded so far is excluded and the A1 lane re-runs all of them.
  The exclusion depends only on when a run was made (before the fix), not on any score: all 41 A1 T2/T3 ledger rows
  with rep >= 1 are listed in the new `results/exclusions.csv` (16 had completed: T2 ×10, T3d ×5, T3a ×1; the other
  25 were already invalid). The A1 lane was stopped at ~12:10 IST mid-rep (`A1_T3a_messy_r08`: no ledger row,
  archived as usual). The A0/A2/A3/A4 lane was not touched.
- **Fix.** `harness/pmx_root.py`, used by `run_arm.py` for every A1 rep and preflight: the rep holds a lock (one A1
  rep at a time); before the agent starts, anything at the top of the shared folders is moved to
  `~/pmxbench_archive/A1/_stray/<runid>/`; after it ends, what its tools wrote there is moved into its own data folder
  (`_pmx_root/`, copied to `results/raw/.../pmxagent_data/` and archived with it); `results/raw/.../pmx_root.json`
  records both. Nothing is deleted or overwritten. The 42 files left from the excluded reps were moved to
  `~/pmxbench_archive/A1/_stray/pre-fix-20261121/`. Prompts, model, Claude Code pin, PMxAgent image and every other
  arm are unchanged.
- **Valid-run rule in one place.** `harness/ledger.py`: valid = completed (status ok, no error) and not in
  `results/exclusions.csv`; used by `run_arm.py --until`, `score_all.py` and `summarize.py` (new column
  `n_protocol_excluded`). `runs.csv` stays append-only; excluded rows keep their rep numbers, so new A1 reps continue
  the numbering (T2 from r14).
- **Audit.** For a run with `pmx_root.json`, the shared PMxAgent `data/` and `figures/` folders count as the run's own
  (reading them is how it fetches its tools' outputs); every other pattern is unchanged, and a rep's own HOME is no
  longer a `claude_state` hit.

### §21 Secondary arm `A1b` on T1 (PMxAgent MCP + shipped `CLAUDE.md`), non-429 failure separation, and A0 T2 drift disclosure (2026-11-21)
- **Root cause of §17 (why bare `A1` never called PMxAgent on T1).** Inspection of `pmxagent-main/` (tag `v1.0.0`),
  the live OpenAPI spec (`http://localhost:5762/openapi.json`), and all T1 transcripts showed:
  1. `pmxagent-main/README.md` instructs Claude Code users to run `claude` from the PMxAgent repo root, where `.mcp.json`
     sits next to a 41 KB `CLAUDE.md` (`pmxagent-main/CLAUDE.md`). That `CLAUDE.md` explicitly documents `/NCA`'s
     multi-drug `DRUG` column, per-subject numeric `ROUTE` (`1`/`2`/`3`), per-subject `AVALU`, and gives the exact
     `data_file=nca_benchmark.csv` example (lines 184–221, 602–603).
  2. `server.py` creates `FastMCP` with no `instructions=` and exposes tools purely from Plumber's `openapi.json`, where
     `/NCA` has `description: null` and `data_file` mentions only single-study ADPC files from `/DATA` (no mention of
     `DRUG`, numeric routes, or multi-drug batching).
  3. Because primary `A1` ran with `.mcp.json` only (no `pmxagent-main/CLAUDE.md`), every T1 `A1` agent ran `ToolSearch`
     on `r_Noncompartmental_analysis_NCA`, saw no multi-drug/mixed-route support in the schema, and pivoted to writing
     local R `PKNCA` scripts (10/10 runs used host R `PKNCA`, vs 0/10 in `A0` and `A2`, which wrote Python). By contrast,
     on `T2_case` (single-drug 2-CM IV simulation matching `/PK` by name), bare `A1` called PMxAgent MCP tools in 100%
     of runs (16/16 total, including 2/2 clean post-§20 reps).
- **Decision (author, 2026-11-21): add pre-specified secondary arm `A1b` on `T1_nca` (10 reps), keep `A1` unchanged.**
  - `A1` stays untouched as the primary bare-MCP arm (no prompt change, no existing T1 run discarded or re-run).
  - `A1b` uses the **exact same verbatim T1 prompt** (and same `SUFFIX` + `SUFFIX_A1`), same PMxAgent 1.0.0 container
    digests, same model (`claude-sonnet-4-6`), same T1 Claude Code pin (`2.1.283`), isolated mode, and `pmx_root.py`
    folder-emptying + exclusive lock, **plus** PMxAgent's verbatim shipped `v1.0.0` `CLAUDE.md` copied into the arm
    workspace (`harness/run_arm.py` verifies its SHA-256 `1ebc55d43c4a3142ed50b2c78efcea22c67bed522f3bc4d81a6bf379e295be8c`
    before setup and before every `A1b` run/preflight).
  - Pre-specified secondary comparisons (`scoring/stats.py` → `results/stats_secondary.csv`): `A1b − A1`, `A2 − A1b`,
    `A3 − A1b`, `A4 − A1b`, reported alongside primary `A1`, never instead of it.
  - Because `pmxagent-main/CLAUDE.md` also includes `curl http://localhost:5762/NCA` examples, `scoring/score_all.py` now
    records `pmxagent_http_calls` (Bash calls to `:5762/{NCA,ER,PK,DATA,LIBRARY}`) alongside `pmxagent_tool_calls` (MCP
    calls) for both `A1` and `A1b`.
- **Non-429 crash/timeout accounting (`harness/ledger.py`, `scoring/summarize.py`).** Previously `summarize.py` counted
  every non-completed run under `n_invalid_excluded` and described that column as HTTP 429 usage-limit stops. `ledger.py`
  now separates `rate_limited(r)` (`failed_ratelimit*`) from `crash_or_timeout(r)` (`exit*` / `timeout`), and
  `summarize.py` reports them in separate columns (`n_invalid_excluded` vs `n_crash_timeout`). Zero valid runs were
  affected (the only non-429 non-ok row in the ledger so far is `A1_T3a_messy_r07`, already excluded under §20).
- **Isolation audit (`scoring/audit_isolation.py`).** Rows in `results/isolation_audit.csv` now carry `excluded`
  (`True` if in `results/exclusions.csv`) and stdout reports valid flagged vs excluded flagged counts separately; arm-ID
  regexes now match `A1b` as well as `A0`–`A4`.
- **A0 `T2_case` within-arm harness drift (disclosure only, no exclusion).** The first 3 valid `A0` `T2_case` reps
  (`r11–r13`, 2026-11-16) ran under `bypassPermissions` without `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1` and with the single
  token (`permission_mode` / `auth_label` empty), whereas `r15–r21` (2026-11-20/21) ran under `default` + explicit
  `--allowedTools` + scrub (§16) + token pool `acct2` (§19). Both sets ran `isolated` on Claude Code `2.1.310` with 0
  permission denials; all 10 count as valid.
