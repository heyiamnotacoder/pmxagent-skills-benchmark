# Benchmark summary

accuracy = paper metric (% of subject-parameters within 1% of PKanalix; mean of 7) for NCA tasks; % of 3 typical values within 1% of analytical truth for T3d; T2 see columns in summary.csv.
cost_usd = Claude Code list-price estimate from token usage (runs used a subscription).
n_runs = valid runs only; n_invalid_excluded = runs cut off by the subscription usage limit (HTTP 429), not scored.

| arm | task | model | n_runs | n_invalid_excluded | accuracy_overall | accuracy_min | n_distinct_outputs | cost_usd_per_run | wall_min_per_run | turns_per_run | tool_calls_per_run | tool_errors_per_run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A0 | T1_nca | claude-sonnet-4-6 | 10 | 7 | 93.21 ± 1.13 | 91.57 | 10 | 0.381 ± 0.123 | 3.1 ± 1.8 | 11.8 ± 1.8 | 10.8 ± 1.8 | 0.9 ± 0.6 |
| A0 | T2_case | claude-sonnet-4-6 | 3 | 11 |  |  | 3 | 0.318 ± 0.151 | 7.5 ± 7.7 | 6.7 ± 5.5 | 14.7 ± 11.0 | 1.7 ± 2.1 |
| A0 | T3d_oral | claude-sonnet-4-6 | 2 | 6 | 100.00 ± 0.00 | 100.0 | 2 | 0.139 ± 0.003 | 1.0 ± 0.0 | 7.0 ± 0.0 | 6.0 ± 0.0 | 1.0 ± 0.0 |
| A1 | T1_nca | claude-sonnet-4-6 | 10 | 2 | 78.58 ± 41.41 | 0.0 | 10 | 0.730 ± 0.138 | 5.2 ± 1.0 | 27.0 ± 6.9 | 26.0 ± 6.9 | 1.6 ± 1.8 |
| A1 | T3d_oral | claude-sonnet-4-6 | 1 | 1 | 100.00 | 100.0 | 1 | 0.166 | 1.0 | 8.0 | 7.0 | 1.0 |
| A2 | T1_nca | claude-sonnet-4-6 | 10 | 7 | 98.65 ± 0.06 | 98.58 | 10 | 0.497 ± 0.087 | 3.8 ± 1.4 | 16.6 ± 2.9 | 14.6 ± 2.9 | 1.3 ± 0.7 |
| A3 | T1_nca | claude-sonnet-4-6 | 10 | 2 | 98.64 ± 0.00 | 98.64 | 5 | 0.198 ± 0.037 | 1.2 ± 0.3 | 12.5 ± 1.6 | 10.5 ± 1.6 | 0.1 ± 0.3 |
| A4 | T1_nca | claude-haiku-4-5-20251001 | 10 | 1 | 98.64 ± 0.00 | 98.64 | 4 | 0.086 ± 0.018 | 1.1 ± 0.3 | 13.6 ± 3.9 | 11.6 ± 3.9 | 0.9 ± 0.7 |

## Tokens by model (summed over runs)

| arm | task | tokens |
|---|---|---|
| A0 | T1_nca | `{"claude-sonnet-4-6":{"inputTokens":136,"outputTokens":110005,"cacheReadInputTokens":2804746,"cacheCreationInputTokens":219412}}` |
| A0 | T2_case | `{"claude-sonnet-4-6":{"inputTokens":59,"outputTokens":22624,"cacheReadInputTokens":1170113,"cacheCreationInputTokens":44060}}` |
| A0 | T3d_oral | `{"claude-sonnet-4-6":{"inputTokens":18,"outputTokens":6967,"cacheReadInputTokens":277413,"cacheCreationInputTokens":15191}}` |
| A1 | T1_nca | `{"claude-sonnet-4-6":{"inputTokens":293,"outputTokens":177603,"cacheReadInputTokens":8374208,"cacheCreationInputTokens":354634}}` |
| A1 | T3d_oral | `{"claude-sonnet-4-6":{"inputTokens":12,"outputTokens":3666,"cacheReadInputTokens":171094,"cacheCreationInputTokens":9965}}` |
| A2 | T1_nca | `{"claude-sonnet-4-6":{"inputTokens":184,"outputTokens":134471,"cacheReadInputTokens":4237186,"cacheCreationInputTokens":279624}}` |
| A3 | T1_nca | `{"claude-sonnet-4-6":{"inputTokens":144,"outputTokens":32888,"cacheReadInputTokens":2399304,"cacheCreationInputTokens":126990}}` |
| A4 | T1_nca | `{"claude-haiku-4-5-20251001":{"inputTokens":968,"outputTokens":41606,"cacheReadInputTokens":2717377,"cacheCreationInputTokens":189790}}` |
