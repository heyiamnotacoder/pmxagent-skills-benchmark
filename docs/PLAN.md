# Plan — Does PMxAgent's architecture beat plain Claude Code + Skills?

Paper: Bloomingdale & Khot, *PMxAgent: An Agentic Platform for Pharmacometrics*, CPT:PSP 2026;15:e70325.
Their stack: Docker Compose → R Plumber API (PKNCA, mrgsolve, rxode2) → OpenAPI → FastMCP server (OAuth) → MCP client.
Our stack: Claude Code + Agent Skills (SKILL.md + bundled, tested R scripts) run via Bash. No containers, no servers.

Preprint (bioRxiv) spec, decisions and the pre-specified analysis for T2/T3: `paper/SPEC.md`. **Where this plan and
`paper/SPEC.md` disagree, SPEC wins** (decided 2026-11-17).

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
| A1 | PMxAgent 1.0.0 run live via MCP (Docker, digest-pinned): T1 10 runs (3 + top-up), T2 10, T3 5 per task. Their published outputs are used for scorer calibration only |
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

## Status (updated 2026-11-17)
- [x] PLAN.md + CLAUDE.md · model = **claude-sonnet-4-6** for all arms · A1 T1 baseline = published outputs, plus live A1 runs for cost + T3
- [x] Phase 0: R stack (`env/versions.txt`), scorer calibrated: reproduces 98.3/98.2/95.6/94.5/91.6 exactly (`logs/calibration.txt`)
  - Finding: PMxAgent raw 10-run output (identical SHA ×10) scores 98.35. Their standardized single-run file scores 98.27, so their standardization dropped a few λz values.
- [x] Phase 1: five skills written from package docs, testthat vs analytical solutions (all pass: `bash harness/test_all.sh`), frozen v1 (`skills/FROZEN.sha256`, `logs/skill_changes.md`). Not scored on PKanalix before freeze.
- [x] Tasks built (`tasks/build_tasks.py`): T1 verbatim · T2 case study (+ results.json) · T3a messy xlsx · T3b explicit BLQ · T3c unit harmonisation · T3d oral 1-CM (out of scope for PMxAgent /PK, analytical truth) · T3e 9,100 subjects
- [x] Docker (colima + Rosetta) + PMxAgent 1.0.0 pinned by digest, deployed at `~/pmxbench_runs/_pmxagent` (`harness/pmxagent.sh up|down`); MCP reachable headless via CI bearer token (6 tools)
- [x] Harness `harness/run_arm.py`: per-arm git repo `~/pmxbench_runs/<arm>/base` with `ws/<task>` branches, fresh `git worktree` per rep, ledger `results/runs.csv` (cost, tokens, turns, tool calls/errors, wall time), transcripts + output SHA-256 in `results/raw/`
- [x] Isolation blocker: T1 accepted the user-CLAUDE.md leak (equal in all arms; `logs/deviations.md`). T2 removes it: per-rep empty `CLAUDE_CONFIG_DIR` + `claude setup-token` subscription token (§11).
- [x] **T1 complete (2026-09-28):** A0–A4, `results/T1_report.md`; evidence on Zenodo (doi:10.5281/zenodo.23019418). Scope decision: arms only, T1 first.
- [x] Preprint branch merged into the T2 work (2026-11-17): `paper/SPEC.md`, stats/figures/tables pipeline, per-task Claude Code pin (`logs/deviations.md` §15)
- [x] A1 T1 top-up to 10 runs (T1 pin 2.1.283, isolated; sensitivity by isolation regime). The A1 agent called no PMxAgent tool in any T1 run; 2 runs unscorable (`logs/deviations.md` §17)
- [x] S2 BLQ check passed; T3b runs as built (§18)
- [x] Token pool: reps may run on several subscription accounts, `~/.config/pmxbench/tokens/acct<N>` (`harness/tokens.py`, §19)
- [ ] **T2 (in progress):** case study ×10 per arm incl. A1; 3 valid A0 reps so far. Scorer `score_case_run` (primary = pre-specified lin-up/log-down consistency) → `results/T2_report.md`
- [ ] T3 stress (T3a–e ×5): needs the supplement re-downloaded to rebuild `tasks/*/reference/`
- Note: a first A0 probe accidentally ran the full T1 task (harness bug, fixed); it was quarantined in `results/raw/A0/_preflight/`, marked in the ledger, and is excluded.
