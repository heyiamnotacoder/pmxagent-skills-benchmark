# Benchmark summary

accuracy = paper metric (% of subject-parameters within 1% of PKanalix; mean of 7) for NCA tasks; % of 3 typical values within 1% of analytical truth for T3d; T2 see columns in summary.csv.
cost_usd = Claude Code list-price estimate from token usage (runs used a subscription).
n_runs = valid runs only; n_arm_failed = of n_runs, runs where the agent crashed, timed out or ended in error after real work, scored on what it left (deviations §22; a killed timeout reports no cost or turns, so it is missing from those means); n_invalid_excluded = runs cut off by the subscription usage limit (HTTP 429), not scored; n_infra_failed = API/auth errors or runs that did no work, not scored and re-run (deviations §22); n_protocol_excluded = completed runs or arm failures listed in results/exclusions.csv (reason + deviation there), not scored.

| arm | task | model | n_runs | n_arm_failed | n_invalid_excluded | n_infra_failed | n_protocol_excluded | accuracy_overall | accuracy_min | n_distinct_outputs | cost_usd_per_run | wall_min_per_run | turns_per_run | tool_calls_per_run | tool_errors_per_run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A0 | T1_nca | claude-sonnet-4-6 | 10 | 0 | 7 | 0 | 0 | 93.21 ± 1.13 | 91.57 | 10 | 0.381 ± 0.123 | 3.1 ± 1.8 | 11.8 ± 1.8 | 10.8 ± 1.8 | 0.9 ± 0.6 |
| A0 | T2_case | claude-sonnet-4-6 | 10 | 0 | 11 | 0 | 0 |  |  | 10 | 0.234 ± 0.094 | 3.3 ± 4.6 | 7.0 ± 2.6 | 8.7 ± 6.6 | 0.6 ± 1.3 |
| A0 | T3a_messy | claude-sonnet-4-6 | 5 | 0 | 6 | 0 | 0 | 92.93 ± 1.60 | 91.36 | 5 | 0.576 ± 0.154 | 4.1 ± 1.2 | 15.2 ± 1.5 | 14.2 ± 1.5 | 0.2 ± 0.4 |
| A0 | T3b_blq | claude-sonnet-4-6 | 3 | 0 | 5 | 0 | 0 | 95.76 ± 0.00 | 95.76 | 3 | 0.534 ± 0.235 | 3.7 ± 2.0 | 13.3 ± 2.1 | 12.3 ± 2.1 | 0.7 ± 0.6 |
| A0 | T3c_units | claude-sonnet-4-6 | 5 | 0 | 6 | 0 | 0 | 93.63 ± 2.64 | 91.36 | 5 | 0.633 ± 0.236 | 3.9 ± 1.9 | 17.0 ± 3.7 | 16.0 ± 3.7 | 0.2 ± 0.4 |
| A0 | T3d_oral | claude-sonnet-4-6 | 5 | 0 | 6 | 0 | 0 | 100.00 ± 0.00 | 100.0 | 5 | 0.121 ± 0.017 | 0.9 ± 0.1 | 6.4 ± 0.5 | 5.4 ± 0.5 | 0.4 ± 0.5 |
| A0 | T3e_large | claude-sonnet-4-6 | 5 | 0 | 5 | 0 | 0 | 93.21 ± 1.05 | 92.74 | 5 | 0.557 ± 0.080 | 3.8 ± 0.6 | 12.8 ± 0.8 | 11.8 ± 0.8 | 0.2 ± 0.4 |
| A1 | T1_nca | claude-sonnet-4-6 | 10 | 0 | 2 | 0 | 0 | 78.58 ± 41.41 | 0.0 | 10 | 0.730 ± 0.138 | 5.2 ± 1.0 | 27.0 ± 6.9 | 26.0 ± 6.9 | 1.6 ± 1.8 |
| A1 | T2_case | claude-sonnet-4-6 | 2 | 0 | 4 | 0 | 10 |  |  | 2 | 0.645 ± 0.003 | 3.0 ± 0.1 | 16.5 ± 0.7 | 15.5 ± 0.7 | 2.5 ± 0.7 |
| A1 | T3d_oral | claude-sonnet-4-6 | 5 | 0 | 1 | 0 | 5 | 93.33 ± 14.91 | 66.67 | 5 | 0.175 ± 0.043 | 1.0 ± 0.2 | 9.2 ± 2.5 | 8.2 ± 2.5 | 0.8 ± 0.8 |
| A2 | T1_nca | claude-sonnet-4-6 | 10 | 0 | 7 | 0 | 0 | 98.65 ± 0.06 | 98.58 | 10 | 0.497 ± 0.087 | 3.8 ± 1.4 | 16.6 ± 2.9 | 14.6 ± 2.9 | 1.3 ± 0.7 |
| A3 | T1_nca | claude-sonnet-4-6 | 10 | 0 | 2 | 0 | 0 | 98.64 ± 0.00 | 98.64 | 5 | 0.198 ± 0.037 | 1.2 ± 0.3 | 12.5 ± 1.6 | 10.5 ± 1.6 | 0.1 ± 0.3 |
| A4 | T1_nca | claude-haiku-4-5-20251001 | 10 | 0 | 1 | 0 | 0 | 98.64 ± 0.00 | 98.64 | 4 | 0.086 ± 0.018 | 1.1 ± 0.3 | 13.6 ± 3.9 | 11.6 ± 3.9 | 0.9 ± 0.7 |

## Tokens by model (summed over runs)

| arm | task | tokens |
|---|---|---|
| A0 | T1_nca | `{"claude-sonnet-4-6":{"inputTokens":136,"outputTokens":110005,"cacheReadInputTokens":2804746,"cacheCreationInputTokens":219412}}` |
| A0 | T2_case | `{"claude-sonnet-4-6":{"inputTokens":122,"outputTokens":64599,"cacheReadInputTokens":2177177,"cacheCreationInputTokens":119879}}` |
| A0 | T3a_messy | `{"claude-sonnet-4-6":{"inputTokens":86,"outputTokens":91002,"cacheReadInputTokens":2144734,"cacheCreationInputTokens":145311}}` |
| A0 | T3b_blq | `{"claude-sonnet-4-6":{"inputTokens":46,"outputTokens":51406,"cacheReadInputTokens":1194407,"cacheCreationInputTokens":78933}}` |
| A0 | T3c_units | `{"claude-sonnet-4-6":{"inputTokens":95,"outputTokens":89743,"cacheReadInputTokens":2763835,"cacheCreationInputTokens":164638}}` |
| A0 | T3d_oral | `{"claude-sonnet-4-6":{"inputTokens":42,"outputTokens":14380,"cacheReadInputTokens":616422,"cacheCreationInputTokens":34348}}` |
| A0 | T3e_large | `{"claude-sonnet-4-6":{"inputTokens":72,"outputTokens":88437,"cacheReadInputTokens":1903676,"cacheCreationInputTokens":147787}}` |
| A1 | T1_nca | `{"claude-sonnet-4-6":{"inputTokens":293,"outputTokens":177603,"cacheReadInputTokens":8374208,"cacheCreationInputTokens":354634}}` |
| A1 | T2_case | `{"claude-sonnet-4-6":{"inputTokens":39,"outputTokens":22527,"cacheReadInputTokens":1298033,"cacheCreationInputTokens":93783}}` |
| A1 | T3d_oral | `{"claude-sonnet-4-6":{"inputTokens":63,"outputTokens":18670,"cacheReadInputTokens":978875,"cacheCreationInputTokens":50592}}` |
| A2 | T1_nca | `{"claude-sonnet-4-6":{"inputTokens":184,"outputTokens":134471,"cacheReadInputTokens":4237186,"cacheCreationInputTokens":279624}}` |
| A3 | T1_nca | `{"claude-sonnet-4-6":{"inputTokens":144,"outputTokens":32888,"cacheReadInputTokens":2399304,"cacheCreationInputTokens":126990}}` |
| A4 | T1_nca | `{"claude-haiku-4-5-20251001":{"inputTokens":968,"outputTokens":41606,"cacheReadInputTokens":2717377,"cacheCreationInputTokens":189790}}` |
