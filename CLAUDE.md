# cptpaper — PMxAgent vs Claude Code + Skills

Goal: test how much of PMxAgent's architecture (Docker + R Plumber + FastMCP) is needed versus plain Claude Code with Skills. Full plan and status: `docs/PLAN.md`. Public summary + T1 result table: `README.md`.

## Arms and tasks
- Arms: `A0` plain Claude Code · `A1` PMxAgent 1.0.0 via MCP · `A2` knowledge-only skills · `A3` skills + bundled scripts · `A4` = A3 on a small model. Models: `claude-sonnet-4-6` (A0–A3), `claude-haiku-4-5-20251001` (A4).
- Tasks (`tasks/<T>/prompt.md`): `T1_nca` (paper's NCA benchmark, done; `results/T1_report.md`), `T2_case` (simulation case study), `T3a_messy` (Excel workbook), `T3b_blq`, `T3c_units`, `T3d_oral` (oral 1-CM vs analytical truth), `T3e_large`.

## Layout
- `CPT ... PMxAgent ....pdf` — the paper. Local only, git-ignored.
- `psp470325-sup-0001-appendixs1/` — their supplement: benchmark data, prompts, PKanalix reference, all agents' results. Read-only, local only, git-ignored; `tasks/build_tasks.py` and `scoring/score_nca.py --calibrate` need it at the repo root.
- `pmxagent-main/` — their repo. Read-only, git-ignored. Only infra files may be read; do NOT read `apis/endpoints/*` or `apis/models/*` while writing our skills (independence).
- `skills/` — our Agent Skills (`pmx-nca`, `pmx-pksim`, `pmx-data`, `pmx-er`, `pmx-library`). Each = `SKILL.md` + `scripts/` + `tests/`. Freeze hashes: `skills/FROZEN.sha256`.
- `docs/` — project docs: `PLAN.md` (plan + status), `agents/` (agent-skills config); `GLOSSARY.md` / `docs/adr/` when created.
- `tasks/` — task prompts + inputs (`build_tasks.py`); `tasks/*/reference/` is scorer-only and git-ignored.
- `harness/` — `run_arm.py` (setup/run/preflight; per-arm git repo + one worktree per rep in `~/pmxbench_runs/`, finished reps archived to `~/pmxbench_archive/`), `run_arm.sh` (wrapper), `run_matrix.sh` (full matrix), `run_t1_two_sessions.sh` (T1, max 2 concurrent sessions), `pmxagent.sh` (A1 Docker stack, digest-pinned), `test_all.sh` (all skill tests), `make_evidence.py` (manifest + evidence archive), `zenodo_upload.py` (deposit; `--publish` is irreversible).
- `scoring/` — `score_nca.py` (paper's NCA metric), `score_all.py` (every run → `results/scores.csv`), `summarize.py` (→ `results/summary.{md,csv}`), `audit_isolation.py` (→ `results/isolation_audit.csv`).
- `results/` — `runs.csv` (run ledger), `scores.csv`, `summary.*`, `isolation_audit.csv`, `T1_report.md`, `evidence/` (`MANIFEST.sha256`, `provenance.json`). `results/raw/` is git-ignored; raw T1 evidence is on Zenodo (doi:10.5281/zenodo.23019418).
- `logs/` — `deviations.md` (protocol deviations), `skill_changes.md` (post-freeze skill changes), `calibration.txt`; `*.log` git-ignored.
- `env/versions.txt` — pinned tool and package versions.

## Rules
- Same pinned model for every arm in a comparison.
- Skills are frozen (`skills/FROZEN.sha256`) before benchmark runs; never tune them on PKanalix reference values. Log any change in `logs/skill_changes.md`.
- Log every departure from `docs/PLAN.md` in `logs/deviations.md`, in time order. Never decide exclusions by looking at accuracy scores.
- Arm workspaces live outside this repo (`~/pmxbench_runs/`) so no reference data or this CLAUDE.md leaks in.
- Keep `logs/*.md` and `results/*` at their paths: harness code and the published evidence manifest depend on them.
- Don't delete supplement, repo, or run outputs.
- Changes go on a branch → PR to `main` → review → merge (squash; `main` has linear history).

## Commands
- Tests: `Rscript -e 'testthat::test_dir("skills/pmx-nca/tests")'` (same per skill) or `bash harness/test_all.sh`
- Build tasks: `python3 tasks/build_tasks.py`
- Calibrate scorer: `python3 scoring/score_nca.py --calibrate`
- Score a run: `python3 scoring/score_nca.py <individual.csv>` · score all: `python3 scoring/score_all.py [--arm A3] [--task T1_nca]`
- Summarize + audit: `python3 scoring/summarize.py` · `python3 scoring/audit_isolation.py`
- Build arm repos: `python3 harness/run_arm.py setup <arm>` · probe isolation: `python3 harness/run_arm.py preflight <arm> claude-sonnet-4-6`
- Run an arm: `bash harness/run_arm.sh <A0|A1|A2|A3|A4> <task> <reps> claude-sonnet-4-6` (A1 needs `bash harness/pmxagent.sh up`)
- Evidence bundle: `python3 harness/make_evidence.py`

## Agent skills

### Issue tracker

Issues live in GitHub Issues (heyiamnotacoder/pmxagent-skills-benchmark), via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-role vocabulary (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
