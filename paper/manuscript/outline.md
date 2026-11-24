# Outline (rewrite of `main.tex`)

Word budget for the main text, ~4,500 (now 4,927): Intro 300 · Methods 1,450 · Results 1,300 · Discussion 850 · Limitations 450 · Conclusions 90. Abstract 573 → ≤ 350. Evidence: `facts.md` macros (`\num…`) or citations. No claim, number or limitation is dropped; material moves or merges.

## Title
Keep the question title, add the design word: *Do agentic pharmacometrics tools need server infrastructure? A controlled benchmark of an MCP platform versus Agent Skills for noncompartmental analysis and PK workflows* ("and PK workflows" because T2/T3d are not NCA; SPEC working title).

## Abstract (≤ 350, structured, written last)
Background 2 sentences · Methods 4 · Results 6 (T1 primary, A1 tool use, A1b, reproducibility, cost; T3; T2) · Conclusions 3. Every number a macro already in the body.

## Introduction (4 paragraphs)
1. LLMs across the pharmacometrics workflow; code written afresh each request is not reproducible. — shin2024nonmem, zheng2025nonmemcoding, cha2025nonmemoutput, saini2025qspcopilot, shin2023chatgptpk, tosca2025vision.
2. PMxAgent's answer (fixed R functions behind Plumber + Docker + MCP) and its result: 98.3% vs 91.6–98.2%, identical across runs. — bloomingdale2026pmxagent, pknca, mrgsolve, mcp, pkanalix; facts design table.
3. The gap: that comparison changes client, model, domain rules and fixed code at once. Agent Skills offer a server-free way to give rules and fixed code separately. — agentskills, pritchardbell2026context.
4. **Aim sentence (new, explicit):** we asked which of three ingredients (domain instructions, a fixed script, a server stack) gives PMxAgent's accuracy and reproducibility, holding client, model and prompt fixed, on its own benchmark and six further tasks. — Fig 1.

## Methods (past tense; order the reader needs)
1. **Benchmark and reference.** T1 as is. Merge the prompt-suffix sentence.
2. **Scoring.** Metric, λz filter, calibration (0.00 pp). Shorten the file-selection and unscorable-run rules to one sentence each; keep "decided after scores were seen" for the per-parameter zero.
3. **Arms.** Client, pins, models; A0–A4 description list kept. A1b item cut to three sentences (what it adds, why it is post hoc, who wrote the file).
4. **Skills.** Five skills, independence from PMxAgent's endpoint code, testthat against analytical solutions, SHA-256 freeze, runner refusal.
5. **Infrastructure count.** One sentence shorter: what was counted, from which tag.
6. **Run protocol and isolation.** Fresh process and worktree, disabled settings, audit result, the one known leak.
7. **Valid runs.** Rep numbers, A1 top-up and regime split, 429/infrastructure vs arm failure, every counted run scored, cost definition. T2/T3 accounts and the shared-folder exclusion.
8. **Further tasks: T2.** Task, added `results.json` sentence, endpoints, the parser hand check (shortened: n, fixed rule, fix, agreement).
9. **Further tasks: T3.** Five variants; BLQ gate; subject identifier stated; T3d outside A1's tools.
10. **Statistics.** Pre-specified comparisons, bootstrap, permutation, ±1 pp, reproducibility measures, terminal-point match.
11. **Analyses decided after the data (new paragraph, gathered from four places).** One paragraph listing each post hoc choice and when it was fixed: T1 comparisons after T1 runs; unscorable-run analysis; A1b; λz error split; T2 EC50 spread summary, unit conversion and 1% rule. Labels them all in one place; text elsewhere says only "(post hoc)".

## Results (numbers first, no interpretation)
1. **T1 accuracy.** Cmax/tmax at 100% in every scorable run; per-arm overall accuracy and SD. — Table 1, Fig 2.
2. **A1 tool use and unscorable runs.** Tool calls 0 of 10; own PKNCA code; 2 runs with drug-only rows; regime split; post hoc 98.x.
3. **Pre-specified comparisons.** A2−A1 (not equivalent; driven by two zero runs), regime-restricted, post hoc; A3−A2; A4−A3. — Table 2.
4. **Terminal-phase match and where the λz errors fall.** Match % for A3 and A0; error split given for A3 in the text, other arms in the table footnote or one sentence (**moved here only; removed from Discussion**).
5. **A1b (post hoc).** Accuracy, tool calls, unscorable runs, A1b−A1, Skills−A1b. — Table 3.
6. **Reproducibility.** A3/A4 one value set; file sets differ only in extras; A0, A2, A1 distinct counts.
7. **Effort and cost.** PMxAgent arms longest/most turns; emulation note; A1b most expensive; A3/A4 cheapest. — Table 4, Fig 3.
8. **T2 completion and consistency.** All complete; A1 tool use; consistency per arm; either-rule sensitivity. — Table 5.
9. **T2 EC50 agreement.** A3 identical in runs that used the packaged set; A2 own code; A1 same parameters and seed but distinct values; A0/A4.
10. **T2 vs published EC50.** Descriptive; per-arm matches.
11. **T3 NCA tasks.** A3 one set; A2 equivalent on three; A0 lower on all; A3 vs A1; A1 tool use. — Tables 6, 7.
12. **T3 small model and T3d.** A4 on T3a/T3c; T3d per arm, tmax as the failing value.
13. **T2/T3 cost.** — Table 8.
14. **Infrastructure.** Services, containers, ports, setup steps, lines; what PMxAgent's extra code provides. — Table 9.

## Discussion
1. **Principal finding (2 sentences).** Accuracy from instructions (93 → 98.7), identical values from a fixed script; neither needed the server stack; footprint numbers.
2. **Comparison with PMxAgent's published results (new, named).** Our A0 (`\numToneAzeroAcc`) vs their Sonnet 4.6 without tools (94.5): same model, close result, so the no-tool baseline replicated; our A2/A3 (98.65/98.64, macros) vs PMxAgent's 98.3: Skills reached the published level without the server. Why the residual gap is λz selection (refer to Results ¶4, no repeat of counts).
3. **Comparison with code-writing reproducibility studies (named).** Shin 2023/2024 found run-to-run variation when code is regenerated; A0 and A2 reproduce that (7 and 9 distinct value sets in 10 runs) even when accuracy is high; A3/A4 remove it by fixing the code, the same route PMxAgent took, without the server.
4. **The agent rarely used the offered tools.** 0/10 T1, 1/30 over NCA tasks; so PMxAgent's own endpoint and its run-to-run identity were not tested here; zero-scoring outputs show a second cost of agent-written code; A1b did not fix accuracy. Why (hypothesis, labelled): the API description omits multi-drug input.
5. **Harder inputs and the limit of the reproducibility claim.** T3 same picture; T2 shows fixed code gives identical values only when the surrounding steps are fixed; T3d tested the agent, not a tool.
6. **The small model.** Matched on T1, T3b, T3e; failed on T3a, T3c, T3d; script made T3c reproducible, not correct; work around the script still depends on the model.
7. **What MCP still gives.** Any-client, typed validation, one controlled deployment; much of PMxAgent's code pays for that; matters for regulated multi-user use.

### Limitations (grouped; each with its likely direction of bias)
1. **Reference and ceiling.** One benchmark, PKanalix not analytical truth, ceiling near 98.7% → small true differences between Skills arms cannot be detected.
2. **Who wrote the Skills.** Our own, with an AI assistant, frozen before any run, not tuned on PKanalix → could favour A2–A4 if our NCA conventions happen to match PKanalix's; T3d and T2 do not depend on PKanalix.
3. **A1 as observed.** Rarely used tools; prompt did not name them; A1b post hoc and its file written by PMxAgent's authors for this benchmark → A1 understates what PMxAgent's endpoint can do.
4. **Timing and isolation.** T1 comparisons specified after T1 runs; user-global file in all T1 arms except A1 4–10 and A1b; A1 4–10 and A1b about eight weeks later (see facts conflict) → regime split pre-specified, shown in Results.
5. **One client, one model family, cost and wall time.** List-price estimate; emulation lengthened A1 wall time → effort differences for A1 are overstated in time, not in turns or tool calls.
6. **T2 and T3.** No reference for T2; post hoc EC50 summary; hand check on a subset; A0 permission-mode drift; T3 at 5 runs (wide CIs), T3d exploratory; T3 prompts named the subject identifier; shared-folder exclusions; later Claude Code version and two accounts.

### Implications / next study (new, one paragraph, inside Discussion before Limitations)
The design to run next: the same arms on a second client (an MCP-capable client other than Claude Code) and a second model family, with a prompt that names PMxAgent's tools, so that the server's own accuracy and run-to-run identity are measured rather than the agent's choice to bypass it.

## Conclusions (≤ 90 words)
Instructions give accuracy, a fixed script gives identical values, neither needs the server; the agent rarely used offered tools; whole-workflow fixing needed for simulation; test the three ingredients separately before adopting the heavier stack.

## Declarations
Unchanged, except the AI-use statement, which adds that the rewrite used Claude Code for editing on 2026-11-24 (draft wording at build step, for your confirmation).
