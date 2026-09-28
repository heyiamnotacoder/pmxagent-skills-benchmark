# Task 1 (NCA benchmark) — arm comparison

Completed 2026-09-28. Task: the paper's single-run NCA benchmark (1,820 subjects), same prompt for every arm.
Metric: the paper's — % of subject-parameters within 1% of PKanalix (Cmax/Tmax/AUClast all subjects; λz-dependent
parameters where reference R²adj ≥ 0.8), overall = mean of 7. The scorer reproduces the paper's published scores
exactly (`logs/calibration.txt`). Valid runs only; usage-limited runs are excluded and listed below.

## Arms
| Arm | Setup | Model |
|---|---|---|
| A0 | Claude Code, no skills, no MCP | claude-sonnet-4-6 |
| A1 | Claude Code + PMxAgent 1.0.0 MCP server (Docker, R Plumber + FastMCP) | claude-sonnet-4-6 |
| A2 | Claude Code + Skills, knowledge only (SKILL.md text, no scripts) | claude-sonnet-4-6 |
| A3 | Claude Code + Skills with scripts (PKNCA wrapper) | claude-sonnet-4-6 |
| A4 | = A3 with a small model | claude-haiku-4-5-20251001 |

## Accuracy (% correct within 1% of PKanalix, mean over runs)
| Arm | n | Cmax | Tmax | AUClast | AUCINF_obs | HL | CL | Vz | Overall | Range |
|---|---|---|---|---|---|---|---|---|---|---|
| A0 | 10 | 100.0 | 100.0 | 94.2 | 94.6 | 86.0 | 94.6 | 83.2 | 93.21 | 91.57–95.09 |
| A1 | 3 | 100.0 | 100.0 | 98.7 | 98.8 | 95.8 | 98.8 | 95.1 | 98.18 | 97.97–98.29 |
| A2 | 10 | 100.0 | 100.0 | 99.9 | 99.5 | 95.8 | 99.5 | 95.8 | 98.65 | 98.58–98.70 |
| A3 | 10 | 100.0 | 100.0 | 100.0 | 99.5 | 95.8 | 99.5 | 95.8 | 98.64 | 98.64–98.64 |
| A4 | 10 | 100.0 | 100.0 | 100.0 | 99.5 | 95.8 | 99.5 | 95.8 | 98.64 | 98.64–98.64 |

Paper, for reference (same metric): PMxAgent 98.3; Claude Sonnet 4.6 without tools 94.5.

## Effort per run (mean ± SD)
| Arm | Cost/run (USD, list price) | Wall time (min) | Turns | Tool calls | Tool errors | Distinct outputs / runs |
|---|---|---|---|---|---|---|
| A0 | 0.381 ± 0.123 | 3.1 ± 1.8 | 11.8 ± 1.8 | 10.8 ± 1.8 | 0.9 ± 0.6 | 10 / 10 |
| A1 | 0.687 ± 0.195 | 6.4 ± 0.6 | 26.0 ± 3.5 | 25.0 ± 3.5 | 2.0 ± 1.7 | 3 / 3 |
| A2 | 0.497 ± 0.087 | 3.8 ± 1.4 | 16.6 ± 2.9 | 14.6 ± 2.9 | 1.3 ± 0.7 | 10 / 10 |
| A3 | 0.198 ± 0.037 | 1.2 ± 0.3 | 12.5 ± 1.6 | 10.5 ± 1.6 | 0.1 ± 0.3 | 5 / 10 |
| A4 | 0.086 ± 0.018 | 1.1 ± 0.3 | 13.6 ± 3.9 | 11.6 ± 3.9 | 0.9 ± 0.7 | 4 / 10 |

## Tokens (summed over the valid runs)
| Arm | Input | Output | Cache read | Cache write |
|---|---|---|---|---|
| A0 | 136 | 110,005 | 2,804,746 | 219,412 |
| A1 | 86 | 48,742 | 2,362,839 | 103,333 |
| A2 | 184 | 134,471 | 4,237,186 | 279,624 |
| A3 | 144 | 32,888 | 2,399,304 | 126,990 |
| A4 | 968 | 41,606 | 2,717,377 | 189,790 |

## Notes for interpretation
- Cost: runs used a Claude subscription; `cost_usd` is Claude Code's own list-price estimate from these token counts.
- A1 wall time includes PMxAgent's amd64 containers running under Rosetta on Apple silicon (`env/versions.txt`).
- A1 has 3 runs (planned, because of cost/time); the others have 10.
- "Distinct outputs": number of different output file sets (SHA-256). A3/A4 produce identical parameter values
  in every run (SD 0.00); differences are in extra files (plots, summaries).
- Excluded runs (HTTP 429, subscription usage limit; never scored): A0 7, A1 2, A2 7, A3 2, A4 1. See
  `logs/deviations.md` §1–2.
- Isolation audit: 0 of 228 transcripts touched another run's files (`results/isolation_audit.csv`).

## Sources
`results/runs.csv` (ledger), `results/scores.csv` (per run), `results/summary.md`, raw transcripts under
`results/raw/` (hashes in `results/evidence/MANIFEST.sha256`).
