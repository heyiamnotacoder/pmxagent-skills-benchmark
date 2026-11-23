# Manuscript manifest

- **Article type:** original research article; computational benchmark of LLM-agent designs for pharmacometric analysis. No reporting-guideline row fits exactly; the closest design file is `peer-review/designs/modelling.md` (reproducibility from paper and code). Reported against the pre-specified analysis in `paper/SPEC.md`.
- **Venue:** bioRxiv, Pharmacology & Toxicology, category *New Results*. Submission guide read 2026-11-24 (https://www.biorxiv.org/submit-a-manuscript): single PDF with text, figures and tables; LaTeX converted to PDF before upload; no word, abstract or reference limits; not peer reviewed; licence chosen at upload.
- **Length target (user, 2026-11-24):** about 4,500 words of main text (Introduction to Conclusions, excluding captions, tables and declarations). Current: 5,450 words in text + 512 in captions (texcount, `main.tex` before rewrite).
- **Abstract:** structured (Background, Methods, Results, Conclusions), kept; aim ≤ 350 words.
- **Reference style:** natbib numbers, `unsrtnat`, `paper/references.bib`.
- **AI-use policy:** bioRxiv FAQ "How should I acknowledge the use of generative AI" (read 2026-11-24, SPEC log): describe use in the manuscript, authors accountable, no AI author. ICMJE II.A.4.
- **Source of truth:** `paper/main.tex`; every result number is a `\num…` macro from `paper/tables/numbers.tex` (`paper/tables.py`). No `manuscript.md` / .docx (user decision, 2026-11-24).
- **Co-author approval:** S.S. approved the pre-rewrite draft (2026-11-24). The rewrite needs a second approval before posting (#16).

## Authors
1. Dhruvik Pandya, Department of Pharmacology, AIIMS Jodhpur. Corresponding author.
2. Surjit Singh, Department of Pharmacology, AIIMS Jodhpur.

CRediT and competing interests (none) and funding (no specific grant): `paper/SPEC.md` decisions log, 2026-11-16 and 2026-11-24.

## Sources
| Source | Path |
|---|---|
| Spec, claims C1–C5, wording rules, pre-specified analysis | `paper/SPEC.md` |
| Protocol | `docs/PLAN.md` |
| Deviations | `logs/deviations.md` |
| Scorer calibration | `logs/calibration.txt` |
| BLQ protocol gate | `logs/blq_check.txt` |
| Run ledger | `results/runs.csv`, `results/exclusions.csv` |
| Scores, stats | `results/scores.csv`, `results/stats*.csv`, `results/summary.csv` |
| Infrastructure | `results/infra.csv` |
| T2 parser check | `results/t2_parser_check.csv` |
| Generated numbers | `paper/tables/numbers.tex`, `paper/tables/*.tex` |
| Task prompts | `tasks/*/prompt.md`, `tasks/build_tasks.py` |
| Versions | `env/versions.txt` |
| PMxAgent supplement | `psp470325-sup-0001-appendixs1/` |

## Missing
- **PMxAgent paper PDF**: not at the repo root (the `CPT … PMxAgent ….pdf` named in CLAUDE.md is absent). Its published figures (98.3%, 91.6–98.2%) are checked against `logs/calibration.txt` and `docs/PLAN.md` instead.
- No ethics approval or registration applies (no human or animal data).
