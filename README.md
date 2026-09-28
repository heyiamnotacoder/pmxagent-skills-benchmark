# Agent Skills vs PMxAgent — NCA benchmark

Code, frozen skills and results for a Letter to the Editor about Bloomingdale & Khot, *PMxAgent: an agentic platform
for pharmacometrics*, CPT Pharmacometrics Syst Pharmacol 2026;15(10):e70325 (doi:10.1002/psp4.70325).

The question: does PMxAgent's NCA accuracy and reproducibility need its Docker + R Plumber + MCP stack? We compare
that stack with plain Claude Code + Agent Skills on the paper's NCA benchmark (182 drugs, 1,820 subjects, PKanalix
reference) and score with the paper's metric.

## Result (Task 1, NCA)
| Arm | Setup | Model | Runs | Accuracy, mean (range) | Cost/run (USD) | Wall time (min) |
|---|---|---|---|---|---|---|
| A0 | No tools | claude-sonnet-4-6 | 10 | 93.21 (91.57–95.09) | 0.38 | 3.1 |
| A1 | PMxAgent 1.0.0 (MCP) | claude-sonnet-4-6 | 3 | 98.18 (97.97–98.29) | 0.69 | 6.4 |
| A2 | Skills, knowledge only | claude-sonnet-4-6 | 10 | 98.65 (98.58–98.70) | 0.50 | 3.8 |
| A3 | Skills + script | claude-sonnet-4-6 | 10 | 98.64 (98.64–98.64) | 0.20 | 1.2 |
| A4 | Skills + script | claude-haiku-4-5 | 10 | 98.64 (98.64–98.64) | 0.09 | 1.1 |

Full report: `results/T1_report.md`. Protocol deviations: `logs/deviations.md`.

## Layout
- `skills/` — Agent Skills (`SKILL.md` + `scripts/` + `tests/`). Frozen before the benchmark runs (`skills/FROZEN.sha256`).
- `harness/` — `run_arm.py` (per-arm git repo, one fresh worktree and headless Claude Code session per run),
  `pmxagent.sh` (the PMxAgent Docker stack for arm A1) and `make_evidence.py` (manifest + evidence archive).
- `scoring/` — `score_nca.py` re-implements the paper's metric. `--calibrate` reproduces the published agent scores
  exactly. `audit_isolation.py` checks that no run touched another run's files.
- `tasks/` — task prompts and inputs (`build_tasks.py`).
- `results/` — ledger (`runs.csv`), per-run scores, summary, isolation audit, evidence manifest and provenance.

## Evidence
Raw agent transcripts, output files and logs for every run (including failed runs) are archived on Zenodo:
**https://doi.org/10.5281/zenodo.23019418**. `results/evidence/MANIFEST.sha256` lists the SHA-256 of every archived file, and
`results/evidence/provenance.json` holds the archive's own hash, model IDs, Claude Code version and container digests.

## Data and licences
- The benchmark data (`tasks/T1_nca/inputs/nca_benchmark.csv`) comes from the Supporting Information of the paper
  above (© the authors; Creative Commons Attribution-NonCommercial licence). Reuse it non-commercially, with attribution to the original article.
  The PKanalix reference values are not redistributed here; get them from the paper's supplement.
- PMxAgent (AGPL-3.0) is not included. Arm A1 pulls its public container images.
- Everything else in this repository: MIT licence (`LICENSE`).

## Author
Dr. Dhruvik Pandya, Department of Pharmacology, AIIMS Jodhpur, India.
Claude Code (Anthropic) was used to build the harness and scorer; the author checked all code and results.
