# Previous scorer: frozen statistics

`stats.csv`, `stats_arms.csv` and `stats_secondary.csv` exactly as `scoring/stats.py` wrote them at commit `92d614c`,
before the scorer changes of `logs/deviations.md` §29 (row-order matching of drug-only files as the primary rule,
parameter names matched by rule, value sets on the seven scored parameters, unrounded run scores).
`paper/tables.py` reads them for the `\num...Vone` macros, so the paper can report what changed without typing a
number. Do not regenerate or edit.
