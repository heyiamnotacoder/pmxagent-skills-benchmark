# Plan — Does PMxAgent's architecture beat plain Claude Code + Skills?

Paper: Bloomingdale & Khot, *PMxAgent: An Agentic Platform for Pharmacometrics*, CPT:PSP 2026;15:e70325.
Their stack: Docker Compose → R Plumber API (PKNCA, mrgsolve, rxode2) → OpenAPI → FastMCP server (OAuth) → MCP client.
Our stack: Claude Code + Agent Skills (SKILL.md + bundled, tested R scripts) run via Bash. No containers, no servers.

## Hypothesis
Determinism and accuracy come from *executing fixed, validated code*, not from MCP/Docker.
A skill that bundles a validated script should match PMxAgent on accuracy and reproducibility at a fraction of the infrastructure.

## Gaps in the paper we exploit
1. Confound: "tool (MCP)" vs "LLM writes fresh code" — never tested "skill with bundled script". Paper itself calls MCP-vs-skill an open question.
2. Baselines ran in Claude desktop / ChatGPT web, PMxAgent in Claude Code → harness differs, not just tools.
3. "Numerically identical across clients" is contradicted by their own QC (AUC ±0.4%, EC50 ±0.39%; agent chose 14 vs 20 timepoints).
4. No BLQ instruction, clean data only, no out-of-scope requests (/PK is IV-bolus only).
5. PMxAgent individual file has 14,401 rows vs PKanalix 14,431 — check what is missing.

## Phases

### Phase 0 — Environment & scorer calibration
- R 4.6.1 + PKNCA, mrgsolve, rxode2, nlmixr2lib, testthat (versions recorded in `env/versions.txt`).
- `scoring/score_nca.py` re-implements the paper's metric: |RE| < 1% vs PKanalix = correct; λz-dependent params (HL, AUCINF_obs, CL, Vz) only for subjects with PKanalix adj-R² ≥ 0.80; Cmax/Tmax/AUClast all subjects; overall = mean of 7 params.
- **Gate:** re-scoring their published CSVs must reproduce 98.3 / 98.2 / 95.6 / 94.5 / 91.6 (±0.1).

### Phase 1 — Skills (written by Claude from package docs only; NOT tuned on PKanalix reference; NOT copied from PMxAgent endpoint code)
| Skill | Engine | Script |
|---|---|---|
| `pmx-nca` | PKNCA | `run_nca.R` — CLI args for AUC method, λz rule, BLQ rule, route; CDISC PP long output |
| `pmx-pksim` | mrgsolve | 1/2/3-CM, IV bolus/infusion/oral, BSV, seed |
| `pmx-data` | R | raw / NONMEM / Excel → ADPC |
| `pmx-er` | R stats | linear/Emax/Imax/logistic, AIC selection, continuous + binary |
| `pmx-library` | rxode2 + nlmixr2lib | list / simulate published popPK models |
- Each script has testthat tests vs analytical solutions.
- **Freeze:** `skills/` hashed + recorded in `skills/FROZEN.sha256` before any benchmark run. Any later change is logged in `logs/skill_changes.md` and re-run.

### Phase 2 — Arms (all Claude Code, same pinned model, fresh headless session per run)
| Arm | Setup |
|---|---|
| A0 | Plain Claude Code (no skills, no MCP) |
| A1 | PMxAgent. **T1/T2: use their published outputs** (Sonnet 4.6, 10 runs + case study) — no Docker. Docker only if we run T3 stress on A1 |
| A2 | Claude Code + knowledge-only skills (no scripts) |
| A3 | Claude Code + skills with scripts ← main contender |
| A4 | A3 on a small model (Haiku 4.5) — optional |
- Model: **Sonnet 4.6 for all arms (decided 2026-09-28)** — matches the model behind PMxAgent's published results.
- Runs: `claude -p --model <pinned>` in an isolated workspace outside this repo (no reference data, no parent CLAUDE.md), 10 reps/arm.

### Phase 3 — Tasks
- **T1** NCA benchmark: 182 drugs / 1820 subjects, verbatim paper prompt (`psp.../benchmark/NCA-benchmark-prompt.txt`).
- **T2** Case study: sim → standardise → NCA → ER, verbatim prompt, 10 reps; track agent-chosen settings (timepoints, seed).
- **T3** Stress (beyond paper): messy raw data, BLQ-specified prompt, mixed units, out-of-scope request (oral 1-CM), large dataset.

### Phase 4 — Metrics & report
- Accuracy (per-param, overall, terminal-point match) · reproducibility (SHA-256 of outputs, setting drift) · tool-call errors · tokens/cost/wall time · human interventions · infrastructure LOC / services / setup time.
- Component verdict table: Docker, Plumber, OpenAPI→MCP, OAuth, file exchange, approval gates, audit trail → *necessary* / *replaceable* / *enterprise-only*.
- Honest concessions: MCP is client-agnostic (Cursor/ChatGPT); typed input validation; locked multi-user GxP deployment.

## Status (2026-09-28)
- [x] PLAN.md + CLAUDE.md · model = **claude-sonnet-4-6** for all arms · A1 T1 baseline = published outputs, plus live A1 runs for cost + T3
- [x] Phase 0: R stack (`env/versions.txt`), scorer calibrated: reproduces 98.3/98.2/95.6/94.5/91.6 exactly (`logs/calibration.txt`)
  - Finding: PMxAgent raw 10-run output (identical SHA ×10) scores 98.35. Their standardized single-run file scores 98.27, so their standardization dropped a few λz values.
- [x] Phase 1: five skills written from package docs, testthat vs analytical solutions (all pass: `bash harness/test_all.sh`), frozen v1 (`skills/FROZEN.sha256`, `logs/skill_changes.md`). Not scored on PKanalix before freeze.
- [x] Tasks built (`tasks/build_tasks.py`): T1 verbatim · T2 case study (+ results.json) · T3a messy xlsx · T3b explicit BLQ · T3c unit harmonisation · T3d oral 1-CM (out of scope for PMxAgent /PK, analytical truth) · T3e 9,100 subjects
- [x] Docker (colima + Rosetta) + PMxAgent 1.0.0 pinned by digest, deployed at `~/pmxbench_runs/_pmxagent` (`harness/pmxagent.sh up|down`); MCP reachable headless via CI bearer token (6 tools)
- [x] Harness `harness/run_arm.py`: per-arm git repo `~/pmxbench_runs/<arm>/base` with `ws/<task>` branches, fresh `git worktree` per rep, ledger `results/runs.csv` (cost, tokens, turns, tool calls/errors, wall time), transcripts + output SHA-256 in `results/raw/`
- [ ] **BLOCKER, isolation:** preflight shows the user-global `~/.claude/CLAUDE.md` + `~/.claude/rules/*.md` still load despite `--setting-sources project`. Options: (a) `--bare` + ANTHROPIC_API_KEY (cleanest; skills then via `--plugin-dir`), (b) find the flag/env that disables user memory, (c) accept (same leak in every arm) and document it. MCP/user skills/plugins do NOT leak (only Claude Code built-in skills, equal across arms).
- [ ] Preflights A1/A2/A3 (after blocker) → then runs: T1 ×10 (A0, A2, A3; A1 ×3 for cost), T2 ×10, T3 ×5
- [ ] T2 scorer (`scoring/score_case.py`) + T3d truth check; report
- Note: a first A0 probe accidentally ran the full T1 task (harness bug, fixed); it was quarantined in `results/raw/A0/_preflight/`, marked in the ledger, and is excluded.
