# cptpaper — PMxAgent vs Claude Code + Skills

Goal: test how much of PMxAgent's architecture (Docker + R Plumber + FastMCP) is needed versus plain Claude Code with Skills. Full plan and status: `PLAN.md`.

## Layout
- `CPT ... PMxAgent ....pdf` — the paper.
- `psp470325-sup-0001-appendixs1/` — their supplement: benchmark data, prompts, PKanalix reference, all agents' results. Read-only.
- `pmxagent-main/` — their repo. Read-only. Only infra files may be read; do NOT read `apis/endpoints/*` or `apis/models/*` while writing our skills (independence).
- `skills/` — our Agent Skills (`pmx-nca`, `pmx-pksim`, `pmx-data`, `pmx-er`, `pmx-library`). Each = `SKILL.md` + `scripts/` + `tests/`.
- `scoring/` — NCA scorer that reproduces the paper's metric.
- `tasks/` — task prompts + inputs (`build_tasks.py`); `tasks/*/reference/` is scorer-only and git-ignored.
- `harness/` — `run_arm.py` (setup/run/preflight; per-arm git repo + one worktree per rep in `~/pmxbench_runs/`), `pmxagent.sh` (A1 Docker stack).
- `results/`, `logs/`, `env/` — outputs, logs, pinned versions.

## Rules
- Same pinned model for every arm in a comparison.
- Skills are frozen (`skills/FROZEN.sha256`) before benchmark runs; never tune them on PKanalix reference values. Log any change in `logs/skill_changes.md`.
- Arm workspaces live outside this repo (`~/pmxbench_runs/`) so no reference data or this CLAUDE.md leaks in.
- Don't delete supplement, repo, or run outputs.

## Commands
- Tests: `Rscript -e 'testthat::test_dir("skills/pmx-nca/tests")'` (same per skill) or `bash harness/test_all.sh`
- Calibrate scorer: `python3 scoring/score_nca.py --calibrate`
- Score a run: `python3 scoring/score_nca.py <individual.csv>`
- Build arm repos: `python3 harness/run_arm.py setup <arm>` · probe isolation: `python3 harness/run_arm.py preflight <arm> claude-sonnet-4-6`
- Run an arm: `bash harness/run_arm.sh <A0|A1|A2|A3|A4> <task> <reps> claude-sonnet-4-6` (A1 needs `bash harness/pmxagent.sh up`)
