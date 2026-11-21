# PMxAgent vs Claude Code + Skills benchmark

A controlled benchmark of which ingredient (domain instructions, fixed validated code, or a server stack) gives an
AI agent accurate and reproducible pharmacometric results.

## Benchmark design

**Arm**:
One fixed agent setup compared in the benchmark: A0 plain client, A1 PMxAgent over bare MCP, A1b (secondary arm, T1) PMxAgent over MCP + PMxAgent's shipped `v1.0.0` `CLAUDE.md`, A2 knowledge-only skills, A3 skills with bundled scripts, A4 = A3 on a small model.
_Avoid_: condition, configuration, agent

**Task**:
One benchmark problem: a verbatim prompt plus its input files (T1 NCA benchmark, T2 case study, T3a–e stress tasks).
_Avoid_: test, job, benchmark (for a single task)

**Reference**:
The values a task's results are scored against: PKanalix output for NCA tasks, the analytical solution for T3d. Never
shown to an agent.
_Avoid_: ground truth (PKanalix is a reference, not the truth), answer key

**Rep**:
One attempt by one arm at one task, started fresh with no memory of other reps.
_Avoid_: run (for an attempt that may not count), trial, iteration

**Valid run**:
A rep that finished without error, or ended in an **arm failure**, and is not in `results/exclusions.csv`. It is scored; every valid run counts, whatever its score.
_Avoid_: successful run, good run

**Usage-limit stop**:
A rep ended by the subscription's usage limit (HTTP 429). Not scored and repeated (`n_invalid_excluded`); distinct from arm failures, infrastructure failures and setup/protocol exclusions (`results/exclusions.csv`).
_Avoid_: failure, crash, rate-limit error

**Arm failure**:
A rep in which the agent did real work (cost or tool calls > 0) and then crashed, hit the time limit or ended in error, with no API/auth error behind it. A valid run, scored on whatever it left (no scorable output → 0); never repeated (`n_arm_failed`, deviations §22).
_Avoid_: crash, invalid run

**Infrastructure failure**:
A non-429 rep that ended on an API/auth error, did no work, or carries a harness-bug status. Not scored and repeated (`n_infra_failed`, deviations §22).
_Avoid_: crash, timeout

**Preflight**:
A short probe rep (rep 0) that lists what the agent can see, used to check isolation. Never scored.
_Avoid_: smoke test, dry run

**Top-up**:
Running further reps of an arm × task until it has the target number of valid runs.
_Avoid_: re-run, retry

## Conditions held fixed

**Isolation regime**:
What instructions from outside the arm reach a rep: *user* (the user's global CLAUDE.md loaded, as in T1 runs) or
*isolated* (none).
_Avoid_: leak (for the regime itself), sandbox

**Pin**:
The one Claude Code version all arms of a task run on.
_Avoid_: toolchain version, harness version

**Freeze**:
The fixed, hashed state of the skills before any benchmark rep; any later change is logged and affected arms re-run.
_Avoid_: lock, release

## Execution

**Session**:
One running Claude Code process. At most two run at once.
_Avoid_: agent, instance

**Lane**:
A queue of reps run one after another in one session slot.
_Avoid_: worker, thread, track

## Results

**Overall accuracy**:
The paper's NCA metric: percentage of subject-parameter values within 1% of the reference, averaged over 7 parameters.
_Avoid_: score, accuracy (alone)

**Internal consistency**:
For T2: whether the group means an agent reports match those recomputed from its own simulated data.
_Avoid_: correctness, accuracy (T2 has no reference)

**Distinct value sets**:
The number of different sets of scored parameter values across an arm's valid runs; 1 means run-to-run identical results.
_Avoid_: distinct outputs (that counts files, not values)
