# cptpaper — PMxAgent vs Claude Code + Skills

Goal: test how much of PMxAgent's architecture (Docker + R Plumber + FastMCP) is needed versus plain Claude Code with Skills. Full plan and status: `docs/PLAN.md`. Public summary + T1 result table: `README.md`.

## Arms and tasks
- Arms: `A0` plain Claude Code · `A1` PMxAgent 1.0.0 via bare MCP · `A1b` secondary arm (T1 only, §21): PMxAgent 1.0.0 MCP + shipped `v1.0.0` `CLAUDE.md` (SHA-256 pinned) · `A2` knowledge-only skills · `A3` skills + bundled scripts · `A4` = A3 on a small model. Models: `claude-sonnet-4-6` (A0–A3, A1b), `claude-haiku-4-5-20251001` (A4).
- Tasks (`tasks/<T>/prompt.md`): `T1_nca` (paper's NCA benchmark, done; `results/T1_report.md`), `T2_case` (simulation case study), `T3a_messy` (Excel workbook), `T3b_blq`, `T3c_units`, `T3d_oral` (oral 1-CM vs analytical truth), `T3e_large`.

## Layout
- `CPT ... PMxAgent ....pdf` — the paper. Local only, git-ignored.
- `psp470325-sup-0001-appendixs1/` — their supplement: benchmark data, prompts, PKanalix reference, all agents' results. Read-only, local only, git-ignored; `tasks/build_tasks.py` and `scoring/score_nca.py --calibrate` need it at the repo root.
- `pmxagent-main/` — their repo. Read-only, git-ignored. Only infra files may be read; do NOT read `apis/endpoints/*` or `apis/models/*` while writing our skills (independence).
- `skills/` — our Agent Skills (`pmx-nca`, `pmx-pksim`, `pmx-data`, `pmx-er`, `pmx-library`). Each = `SKILL.md` + `scripts/` + `tests/`. Freeze hashes: `skills/FROZEN.sha256`.
- `docs/` — project docs: `PLAN.md` (protocol + status; `paper/SPEC.md` wins on conflict), `agents/` (agent-skills config); `docs/adr/` when created. `GLOSSARY.md` (root) — benchmark vocabulary (arm, task, rep, valid run, …).
- `tasks/` — task prompts + inputs (`build_tasks.py`); `tasks/*/reference/` is scorer-only and git-ignored.
- `harness/` — `run_arm.py` (setup/run/preflight; per-arm git repo + one worktree per rep in `/Users/Shared/pmxbench_runs/` (override: `$PMXBENCH_RUNS`), finished reps archived to `~/pmxbench_archive/`; A1's deployed stack stays in `~/pmxbench_runs/_pmxagent/` because colima only mounts `~`), `run_arm.sh` (wrapper), `run_matrix.sh` (full matrix), `run_t1_two_sessions.sh` / `run_t2_two_sessions.sh` (T1 / first T2 reps, max 2 concurrent sessions), `run_t2_t3_lanes.sh` (T2 + T3 lanes, max 2 sessions), `resume_lanes.sh` (re-runs the lanes after every usage-limit reset until done; start it from a Terminal tab, never from a Claude session), `tokens.py` (subscription-account pool: `~/.config/pmxbench/tokens/<label>`, first account not at its usage limit; `status` / `next-free`), `ledger.py` (the one valid-run rule: completed or arm failure, and not in `results/exclusions.csv`; 429 stops and infrastructure failures are re-run; used by `--until` and scoring; deviations §22), `pmx_root.py` (A1: PMxAgent's shared `data/`+`figures/` emptied per rep, one A1 rep at a time; deviations §20), `count_infra.py` (infrastructure footprint → `results/infra.csv`), `pmxagent.sh` (A1 Docker stack, digest-pinned), `test_all.sh` (all skill tests), `make_evidence.py` (manifest + evidence archive), `zenodo_upload.py` (deposit; `--publish` is irreversible), `tests/` (harness unit tests).
- `scoring/` — `score_nca.py` (paper's NCA metric), `score_all.py` (every run → `results/scores.csv`), `summarize.py` (→ `results/summary.{md,csv}`), `audit_isolation.py` (→ `results/isolation_audit.csv`), `stats.py` (pre-specified comparisons → `results/stats.*`), `figures.py` (→ `paper/figures/`), `check_blq_reference.py` (T3b protocol gate), `check_t2_parser.py` (T2 parser hand check → `logs/t2_parser_check.txt`, `results/t2_parser_check.csv`).
- `results/` — `runs.csv` (run ledger, append-only), `exclusions.csv` (protocol exclusions: runid, reason, deviation §), `scores.csv`, `summary.*`, `isolation_audit.csv`, `t2_parser_check.csv` (read by `paper/tables.py`), `T1_report.md`, `evidence/` (`MANIFEST.sha256`, `provenance.json`). `results/raw/` is git-ignored; raw T1 evidence is on Zenodo (doi:10.5281/zenodo.23019418).
- `logs/` — `deviations.md` (protocol deviations), `skill_changes.md` (post-freeze skill changes), `calibration.txt`; `*.log` git-ignored.
- `env/versions.txt` — pinned tool and package versions.
- `paper/` — bioRxiv preprint: `SPEC.md` (spec, decisions log, pre-specified analysis; work tracked as GitHub sub-issues), `main.tex`, `references.bib`; tables/numbers from `paper/tables.py`, figures from `scoring/figures.py` (Fig 1, the architecture diagram: TikZ `paper/figures/fig_arch.tex`, build command at its top). Never type a result number by hand.

## Rules
- Same pinned model for every arm in a comparison; one pinned Claude Code version per task (`env/versions.txt` `claude-code-pin`; harness-owned binaries in `~/.local/share/pmxbench/claude/`).
- Skills are frozen (`skills/FROZEN.sha256`) before benchmark runs; never tune them on PKanalix reference values. Log any change in `logs/skill_changes.md`.
- Log every departure from `docs/PLAN.md` in `logs/deviations.md`, in time order. Never decide exclusions by looking at accuracy scores.
- Arm workspaces live outside this repo and outside `~` (`/Users/Shared/pmxbench_runs/`) so no reference data, this CLAUDE.md, or `~/.claude/` instructions leak in (Claude Code reads CLAUDE.md from every ancestor folder).
- Keep `logs/*.md` and `results/*` at their paths: harness code and the published evidence manifest depend on them.
- Don't delete supplement, repo, or run outputs.
- Changes go on a branch → PR to `main` → review → merge (squash; `main` has linear history).

## Commands
- Tests: `Rscript -e 'testthat::test_dir("skills/pmx-nca/tests")'` (same per skill) or `bash harness/test_all.sh` · harness: `python3 -m unittest discover -s harness/tests`
- Build tasks: `python3 tasks/build_tasks.py`
- Calibrate scorer: `python3 scoring/score_nca.py --calibrate`
- Score a run: `python3 scoring/score_nca.py <individual.csv>` · score all: `python3 scoring/score_all.py [--arm A3] [--task T1_nca]`
- Summarize + audit: `python3 scoring/summarize.py` · `python3 scoring/audit_isolation.py`
- Build arm repos: `python3 harness/run_arm.py setup <arm>` · probe isolation: `python3 harness/run_arm.py preflight <arm> claude-sonnet-4-6`
- Paper pipeline: `python3 scoring/stats.py && python3 scoring/figures.py && (cd paper/figures && latexmk -pdf fig_arch.tex) && python3 paper/tables.py && (cd paper && latexmk -pdf main.tex)`
- Run an arm: `bash harness/run_arm.sh <A0|A1|A1b|A2|A3|A4> <task> <reps> claude-sonnet-4-6` (A1/A1b need `bash harness/pmxagent.sh up`)
- Evidence bundle: `python3 harness/make_evidence.py`

## Agent skills

### Issue tracker

Issues live in GitHub Issues (heyiamnotacoder/pmxagent-skills-benchmark), via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-role vocabulary (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
