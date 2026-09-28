# Skill change log

Skills are frozen in `skills/FROZEN.sha256`. `harness/run_arm.py` refuses to run A2/A3/A4 if any hash differs.
Any change after freeze: describe it here, re-run `bash harness/test_all.sh`, re-freeze, and re-run affected arms.

## 2026-09-28 — v1 freeze
- Written from package documentation (PKNCA 0.12.1, mrgsolve 2.0.1, rxode2, nlmixr2lib @d8a40f2) and general NCA conventions.
  PMxAgent endpoint/model code was not read.
- Validation: testthat against analytical solutions only (IV/EV Bateman, bi-exponential, infusion, superposition,
  hand-computed lin-up/log-down, BLQ rules, logistic/Emax recovery, data round trip through NCA).
- The NCA script was smoke-run on the T1 input to check it completes and covers all 1820 subjects
  (1738 with lambda_z). **Its output was not scored against PKanalix before freezing.**
