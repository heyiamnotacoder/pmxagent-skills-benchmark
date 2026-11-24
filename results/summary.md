# Benchmark summary

accuracy = paper metric (% of subject-parameters within 1% of PKanalix; mean of 7) for NCA tasks; % of 3 typical values within 1% of analytical truth for T3d; T2 see columns in summary.csv.
cost_usd = Claude Code list-price estimate from token usage (runs used a subscription).
n_runs = valid runs only; n_arm_failed = of n_runs, runs where the agent crashed, timed out or ended in error after real work, scored on what it left (deviations §22; a killed timeout reports no cost or turns, so it is missing from those means); n_invalid_excluded = runs cut off by the subscription usage limit (HTTP 429), not scored; n_infra_failed = API/auth errors or runs that did no work, not scored and re-run (deviations §22); n_protocol_excluded = completed runs or arm failures listed in results/exclusions.csv (reason + deviation there), not scored.

| arm | task | model | n_runs | n_arm_failed | n_invalid_excluded | n_infra_failed | n_protocol_excluded | accuracy_overall | accuracy_min | n_distinct_outputs | cost_usd_per_run | wall_min_per_run | turns_per_run | tool_calls_per_run | tool_errors_per_run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A0 | T1_nca | claude-sonnet-4-6 | 10 | 0 | 7 | 0 | 0 | 93.21 ± 1.13 | 91.568494 | 10 | 0.381 ± 0.123 | 3.1 ± 1.8 | 11.8 ± 1.8 | 10.8 ± 1.8 | 0.9 ± 0.6 |
| A0 | T2_case | claude-sonnet-4-6 | 10 | 0 | 11 | 0 | 0 |  |  | 10 | 0.234 ± 0.094 | 3.3 ± 4.6 | 7.0 ± 2.6 | 8.7 ± 6.6 | 0.6 ± 1.3 |
| A0 | T3a_messy | claude-sonnet-4-6 | 5 | 0 | 6 | 0 | 0 | 92.93 ± 1.60 | 91.362545 | 5 | 0.576 ± 0.154 | 4.1 ± 1.2 | 15.2 ± 1.5 | 14.2 ± 1.5 | 0.2 ± 0.4 |
| A0 | T3b_blq | claude-sonnet-4-6 | 5 | 0 | 5 | 0 | 0 | 95.53 ± 0.52 | 94.606742 | 5 | 0.461 ± 0.199 | 3.0 ± 1.7 | 13.0 ± 1.6 | 12.0 ± 1.6 | 0.8 ± 0.4 |
| A0 | T3c_units | claude-sonnet-4-6 | 5 | 0 | 6 | 0 | 0 | 93.63 ± 2.64 | 91.362545 | 5 | 0.633 ± 0.236 | 3.9 ± 1.9 | 17.0 ± 3.7 | 16.0 ± 3.7 | 0.2 ± 0.4 |
| A0 | T3d_oral | claude-sonnet-4-6 | 5 | 0 | 6 | 0 | 0 | 100.00 ± 0.00 | 100.0 | 5 | 0.121 ± 0.017 | 0.9 ± 0.1 | 6.4 ± 0.5 | 5.4 ± 0.5 | 0.4 ± 0.5 |
| A0 | T3e_large | claude-sonnet-4-6 | 5 | 0 | 5 | 0 | 0 | 93.21 ± 1.05 | 92.74384 | 5 | 0.557 ± 0.080 | 3.8 ± 0.6 | 12.8 ± 0.8 | 11.8 ± 0.8 | 0.2 ± 0.4 |
| A1 | T1_nca | claude-sonnet-4-6 | 10 | 0 | 2 | 0 | 0 | 98.24 ± 0.12 | 97.969763 | 10 | 0.730 ± 0.138 | 5.2 ± 1.0 | 27.0 ± 6.9 | 26.0 ± 6.9 | 1.6 ± 1.8 |
| A1 | T2_case | claude-sonnet-4-6 | 10 | 0 | 5 | 0 | 10 |  |  | 10 | 0.663 ± 0.074 | 3.1 ± 0.5 | 17.1 ± 1.0 | 16.1 ± 1.0 | 2.7 ± 0.7 |
| A1 | T3a_messy | claude-sonnet-4-6 | 5 | 0 | 7 | 0 | 2 | 98.68 ± 0.00 | 98.679472 | 5 | 1.117 ± 0.673 | 6.8 ± 5.6 | 36.2 ± 10.6 | 35.0 ± 10.3 | 1.6 ± 1.5 |
| A1 | T3b_blq | claude-sonnet-4-6 | 5 | 0 | 6 | 0 | 0 | 96.08 ± 0.35 | 95.634029 | 5 | 0.788 ± 0.202 | 5.1 ± 1.6 | 22.2 ± 5.2 | 21.2 ± 5.2 | 1.8 ± 1.3 |
| A1 | T3c_units | claude-sonnet-4-6 | 5 | 0 | 6 | 0 | 0 | 98.68 ± 0.00 | 98.679472 | 5 | 0.823 ± 0.190 | 4.6 ± 1.4 | 27.0 ± 5.4 | 26.0 ± 5.4 | 2.6 ± 1.3 |
| A1 | T3d_oral | claude-sonnet-4-6 | 5 | 0 | 1 | 0 | 5 | 93.33 ± 14.91 | 66.666667 | 5 | 0.175 ± 0.043 | 1.0 ± 0.2 | 9.2 ± 2.5 | 8.2 ± 2.5 | 0.8 ± 0.8 |
| A1 | T3e_large | claude-sonnet-4-6 | 5 | 0 | 5 | 0 | 0 | 98.25 ± 0.11 | 98.058494 | 5 | 0.856 ± 0.086 | 6.0 ± 1.0 | 21.4 ± 15.4 | 31.0 ± 3.7 | 0.8 ± 0.8 |
| A1b | T1_nca | claude-sonnet-4-6 | 10 | 0 | 1 | 0 | 0 | 79.95 ± 33.67 | 16.535049 | 10 | 1.012 ± 0.418 | 8.0 ± 4.2 | 28.2 ± 9.4 | 27.2 ± 9.4 | 1.8 ± 1.5 |
| A2 | T1_nca | claude-sonnet-4-6 | 10 | 0 | 7 | 0 | 0 | 98.65 ± 0.06 | 98.580302 | 10 | 0.497 ± 0.087 | 3.8 ± 1.4 | 16.6 ± 2.9 | 14.6 ± 2.9 | 1.3 ± 0.7 |
| A2 | T2_case | claude-sonnet-4-6 | 10 | 0 | 11 | 0 | 0 |  |  | 10 | 0.539 ± 0.210 | 3.4 ± 1.3 | 18.8 ± 7.6 | 16.1 ± 6.9 | 1.8 ± 1.0 |
| A2 | T3a_messy | claude-sonnet-4-6 | 5 | 0 | 6 | 0 | 0 | 98.68 ± 0.00 | 98.679472 | 5 | 0.616 ± 0.188 | 3.8 ± 1.4 | 17.4 ± 1.9 | 15.4 ± 1.9 | 0.0 ± 0.0 |
| A2 | T3b_blq | claude-sonnet-4-6 | 5 | 0 | 5 | 0 | 0 | 97.32 ± 0.15 | 97.151253 | 5 | 0.509 ± 0.099 | 2.8 ± 0.7 | 19.2 ± 2.8 | 17.2 ± 2.8 | 1.0 ± 0.0 |
| A2 | T3c_units | claude-sonnet-4-6 | 5 | 0 | 5 | 0 | 0 | 98.21 ± 0.92 | 96.584634 | 5 | 0.431 ± 0.084 | 2.6 ± 0.6 | 16.4 ± 3.6 | 14.4 ± 3.6 | 1.2 ± 0.4 |
| A2 | T3d_oral | claude-sonnet-4-6 | 5 | 0 | 5 | 0 | 0 | 100.00 ± 0.00 | 100.0 | 5 | 0.206 ± 0.057 | 1.3 ± 0.3 | 11.0 ± 3.5 | 9.0 ± 3.2 | 1.2 ± 1.1 |
| A2 | T3e_large | claude-sonnet-4-6 | 5 | 0 | 6 | 0 | 0 | 98.69 ± 0.03 | 98.624667 | 5 | 0.438 ± 0.145 | 2.6 ± 1.3 | 16.6 ± 3.5 | 14.6 ± 3.5 | 0.4 ± 0.5 |
| A3 | T1_nca | claude-sonnet-4-6 | 10 | 0 | 2 | 0 | 0 | 98.64 ± 0.00 | 98.643096 | 5 | 0.198 ± 0.037 | 1.2 ± 0.3 | 12.5 ± 1.6 | 10.5 ± 1.6 | 0.1 ± 0.3 |
| A3 | T2_case | claude-sonnet-4-6 | 10 | 0 | 11 | 0 | 0 |  |  | 10 | 0.239 ± 0.030 | 1.1 ± 0.3 | 16.9 ± 3.6 | 13.1 ± 3.1 | 0.2 ± 0.4 |
| A3 | T3a_messy | claude-sonnet-4-6 | 5 | 0 | 5 | 0 | 0 | 98.68 ± 0.00 | 98.679472 | 5 | 0.536 ± 0.082 | 2.6 ± 0.3 | 26.2 ± 3.6 | 23.2 ± 3.6 | 2.4 ± 1.1 |
| A3 | T3b_blq | claude-sonnet-4-6 | 5 | 0 | 5 | 0 | 0 | 97.43 ± 0.00 | 97.431782 | 4 | 0.178 ± 0.023 | 0.8 ± 0.1 | 11.8 ± 1.6 | 9.8 ± 1.6 | 0.2 ± 0.4 |
| A3 | T3c_units | claude-sonnet-4-6 | 5 | 0 | 5 | 0 | 0 | 98.68 ± 0.00 | 98.679472 | 4 | 0.372 ± 0.110 | 2.1 ± 0.8 | 16.6 ± 4.7 | 14.6 ± 4.7 | 0.8 ± 0.8 |
| A3 | T3d_oral | claude-sonnet-4-6 | 5 | 0 | 5 | 0 | 0 | 100.00 ± 0.00 | 100.0 | 5 | 0.157 ± 0.048 | 0.9 ± 0.2 | 9.0 ± 2.9 | 7.4 ± 2.1 | 0.0 ± 0.0 |
| A3 | T3e_large | claude-sonnet-4-6 | 5 | 0 | 6 | 0 | 0 | 98.64 ± 0.00 | 98.643096 | 2 | 0.226 ± 0.039 | 2.7 ± 0.2 | 14.0 ± 1.0 | 12.0 ± 1.0 | 0.2 ± 0.4 |
| A4 | T1_nca | claude-haiku-4-5-20251001 | 10 | 0 | 1 | 0 | 0 | 98.64 ± 0.00 | 98.643096 | 4 | 0.086 ± 0.018 | 1.1 ± 0.3 | 13.6 ± 3.9 | 11.6 ± 3.9 | 0.9 ± 0.7 |
| A4 | T2_case | claude-haiku-4-5-20251001 | 10 | 0 | 11 | 0 | 0 |  |  | 10 | 0.302 ± 0.129 | 3.3 ± 2.1 | 28.5 ± 14.9 | 31.5 ± 13.6 | 3.0 ± 1.3 |
| A4 | T3a_messy | claude-haiku-4-5-20251001 | 5 | 0 | 5 | 0 | 0 | 92.46 ± 8.51 | 82.962785 | 5 | 0.196 ± 0.031 | 2.2 ± 0.3 | 22.8 ± 7.5 | 20.8 ± 7.0 | 1.4 ± 0.5 |
| A4 | T3b_blq | claude-haiku-4-5-20251001 | 5 | 0 | 5 | 0 | 0 | 97.43 ± 0.00 | 97.431782 | 3 | 0.089 ± 0.024 | 1.0 ± 0.3 | 13.4 ± 4.0 | 11.4 ± 4.0 | 1.2 ± 1.1 |
| A4 | T3c_units | claude-haiku-4-5-20251001 | 5 | 0 | 5 | 0 | 0 | 85.51 ± 0.00 | 85.514206 | 5 | 0.191 ± 0.051 | 2.1 ± 0.4 | 16.0 ± 2.9 | 14.0 ± 2.9 | 1.2 ± 0.8 |
| A4 | T3d_oral | claude-haiku-4-5-20251001 | 5 | 0 | 5 | 0 | 0 | 73.33 ± 14.91 | 66.666667 | 5 | 0.122 ± 0.056 | 1.3 ± 0.5 | 18.0 ± 9.1 | 16.4 ± 8.8 | 3.0 ± 2.9 |
| A4 | T3e_large | claude-haiku-4-5-20251001 | 5 | 0 | 5 | 0 | 0 | 98.64 ± 0.00 | 98.643096 | 3 | 0.072 ± 0.009 | 2.5 ± 0.1 | 11.6 ± 1.5 | 9.6 ± 1.5 | 0.2 ± 0.4 |

## Tokens by model (summed over runs)

| arm | task | tokens |
|---|---|---|
| A0 | T1_nca | `{"claude-sonnet-4-6":{"inputTokens":136,"outputTokens":110005,"cacheReadInputTokens":2804746,"cacheCreationInputTokens":219412}}` |
| A0 | T2_case | `{"claude-sonnet-4-6":{"inputTokens":122,"outputTokens":64599,"cacheReadInputTokens":2177177,"cacheCreationInputTokens":119879}}` |
| A0 | T3a_messy | `{"claude-sonnet-4-6":{"inputTokens":86,"outputTokens":91002,"cacheReadInputTokens":2144734,"cacheCreationInputTokens":145311}}` |
| A0 | T3b_blq | `{"claude-sonnet-4-6":{"inputTokens":75,"outputTokens":70250,"cacheReadInputTokens":1822601,"cacheCreationInputTokens":117644}}` |
| A0 | T3c_units | `{"claude-sonnet-4-6":{"inputTokens":95,"outputTokens":89743,"cacheReadInputTokens":2763835,"cacheCreationInputTokens":164638}}` |
| A0 | T3d_oral | `{"claude-sonnet-4-6":{"inputTokens":42,"outputTokens":14380,"cacheReadInputTokens":616422,"cacheCreationInputTokens":34348}}` |
| A0 | T3e_large | `{"claude-sonnet-4-6":{"inputTokens":72,"outputTokens":88437,"cacheReadInputTokens":1903676,"cacheCreationInputTokens":147787}}` |
| A1 | T1_nca | `{"claude-sonnet-4-6":{"inputTokens":293,"outputTokens":177603,"cacheReadInputTokens":8374208,"cacheCreationInputTokens":354634}}` |
| A1 | T2_case | `{"claude-sonnet-4-6":{"inputTokens":203,"outputTokens":121048,"cacheReadInputTokens":6768866,"cacheCreationInputTokens":464528}}` |
| A1 | T3a_messy | `{"claude-sonnet-4-6":{"inputTokens":1771,"outputTokens":130678,"cacheReadInputTokens":5961767,"cacheCreationInputTokens":307947}}` |
| A1 | T3b_blq | `{"claude-sonnet-4-6":{"inputTokens":126,"outputTokens":112541,"cacheReadInputTokens":3708268,"cacheCreationInputTokens":189433}}` |
| A1 | T3c_units | `{"claude-sonnet-4-6":{"inputTokens":154,"outputTokens":100364,"cacheReadInputTokens":4725767,"cacheCreationInputTokens":198188}}` |
| A1 | T3d_oral | `{"claude-sonnet-4-6":{"inputTokens":63,"outputTokens":18670,"cacheReadInputTokens":978875,"cacheCreationInputTokens":50592}}` |
| A1 | T3e_large | `{"claude-sonnet-4-6":{"inputTokens":175,"outputTokens":100935,"cacheReadInputTokens":5404972,"cacheCreationInputTokens":190889}}` |
| A1b | T1_nca | `{"claude-sonnet-4-6":{"inputTokens":310,"outputTokens":211243,"cacheReadInputTokens":13111021,"cacheCreationInputTokens":503683}}` |
| A2 | T1_nca | `{"claude-sonnet-4-6":{"inputTokens":184,"outputTokens":134471,"cacheReadInputTokens":4237186,"cacheCreationInputTokens":279624}}` |
| A2 | T2_case | `{"claude-sonnet-4-6":{"inputTokens":197,"outputTokens":151617,"cacheReadInputTokens":4921235,"cacheCreationInputTokens":273625}}` |
| A2 | T3a_messy | `{"claude-sonnet-4-6":{"inputTokens":97,"outputTokens":84122,"cacheReadInputTokens":2619879,"cacheCreationInputTokens":172368}}` |
| A2 | T3b_blq | `{"claude-sonnet-4-6":{"inputTokens":106,"outputTokens":61433,"cacheReadInputTokens":2655367,"cacheCreationInputTokens":137864}}` |
| A2 | T3c_units | `{"claude-sonnet-4-6":{"inputTokens":89,"outputTokens":58531,"cacheReadInputTokens":1960068,"cacheCreationInputTokens":115134}}` |
| A2 | T3d_oral | `{"claude-sonnet-4-6":{"inputTokens":65,"outputTokens":24417,"cacheReadInputTokens":1090279,"cacheCreationInputTokens":55946}}` |
| A2 | T3e_large | `{"claude-sonnet-4-6":{"inputTokens":93,"outputTokens":56497,"cacheReadInputTokens":2155951,"cacheCreationInputTokens":116055}}` |
| A3 | T1_nca | `{"claude-sonnet-4-6":{"inputTokens":144,"outputTokens":32888,"cacheReadInputTokens":2399304,"cacheCreationInputTokens":126990}}` |
| A3 | T2_case | `{"claude-sonnet-4-6":{"inputTokens":189,"outputTokens":40661,"cacheReadInputTokens":3216868,"cacheCreationInputTokens":136456}}` |
| A3 | T3a_messy | `{"claude-sonnet-4-6":{"inputTokens":140,"outputTokens":51516,"cacheReadInputTokens":3605840,"cacheCreationInputTokens":137198}}` |
| A3 | T3b_blq | `{"claude-sonnet-4-6":{"inputTokens":68,"outputTokens":13121,"cacheReadInputTokens":1184540,"cacheCreationInputTokens":56082}}` |
| A3 | T3c_units | `{"claude-sonnet-4-6":{"inputTokens":93,"outputTokens":44541,"cacheReadInputTokens":2020997,"cacheCreationInputTokens":97803}}` |
| A3 | T3d_oral | `{"claude-sonnet-4-6":{"inputTokens":55,"outputTokens":16120,"cacheReadInputTokens":873378,"cacheCreationInputTokens":46558}}` |
| A3 | T3e_large | `{"claude-sonnet-4-6":{"inputTokens":80,"outputTokens":18346,"cacheReadInputTokens":1512449,"cacheCreationInputTokens":67047}}` |
| A4 | T1_nca | `{"claude-haiku-4-5-20251001":{"inputTokens":968,"outputTokens":41606,"cacheReadInputTokens":2717377,"cacheCreationInputTokens":189790}}` |
| A4 | T2_case | `{"claude-haiku-4-5-20251001":{"inputTokens":2539,"outputTokens":210883,"cacheReadInputTokens":11694885,"cacheCreationInputTokens":394533}}` |
| A4 | T3a_messy | `{"claude-haiku-4-5-20251001":{"inputTokens":884,"outputTokens":70203,"cacheReadInputTokens":3319650,"cacheCreationInputTokens":147235}}` |
| A4 | T3b_blq | `{"claude-haiku-4-5-20251001":{"inputTokens":508,"outputTokens":26523,"cacheReadInputTokens":1510728,"cacheCreationInputTokens":79178}}` |
| A4 | T3c_units | `{"claude-haiku-4-5-20251001":{"inputTokens":620,"outputTokens":71910,"cacheReadInputTokens":2512352,"cacheCreationInputTokens":171115}}` |
| A4 | T3d_oral | `{"claude-haiku-4-5-20251001":{"inputTokens":712,"outputTokens":41594,"cacheReadInputTokens":2297802,"cacheCreationInputTokens":85903}}` |
| A4 | T3e_large | `{"claude-haiku-4-5-20251001":{"inputTokens":404,"outputTokens":20480,"cacheReadInputTokens":1136617,"cacheCreationInputTokens":70636}}` |
