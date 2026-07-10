# Training Weight KDJ Budget Reallocation V1

## Round frame

Primary goal: test whether returning four chronically non-converting Weight KDJ candidate slots to ordinary exploitation/exploration/replay improves search opportunity without removing the advisor or weakening any promotion guardrail.

Non-goals:

- no change to Weight KDJ signal generation, thresholds, offsets, or freshness rules;
- no change to Ridge KDJ, Neural KDJ, recency canary, target-weight inversion, frozen validation, null diagnostics, or leakage checks;
- no source-based promotion quota;
- no model-strength claim from one or two runtime-validation rounds.

## Task frame

Baseline run `20260710-164004` completed eight same-history rounds at issue `2026078`. The configured Weight KDJ share was 0.22, which rounded to 7 of 28 candidate slots per round. Across the eight-round same-run window, Weight KDJ generated 56 candidates, 10 reached full evaluation, none reached full-eval Top5, and none was round best. Recency canary was also zero-Top5, but this experiment changes only Weight KDJ so the result remains interpretable.

Progress means all of the following:

- a fresh supervisor actually records Weight KDJ budget 3 rather than 7;
- Weight KDJ remains enabled with a non-zero candidate path;
- the total candidate budget remains 28 and the returned four slots appear in ordinary search buckets;
- one to two completed rounds finish without runtime, parser/sync/duplicate, advisor freshness, frozen-validation, or leakage failures.

## Historical boundary

The Gauss and Riemann names below denote historically inspired reasoning lenses, not literal minds, trained replicas, or evidence by authority.

## Gauss pass: verification

Strongest claim: with max configs 28 and all other configured shares held fixed, `candidate_budget` maps Weight KDJ share 0.22 to seven slots and share 0.10 to three slots. The exact deterministic allocations are:

- baseline: exploitation 3, exploration 2, replay 1, baseline 1, Weight KDJ 7, Ridge 3, Neural 3, recency 4, target inversion 4;
- experiment: exploitation 5, exploration 3, replay 2, baseline 1, Weight KDJ 3, Ridge 3, Neural 3, recency 4, target inversion 4.

Weakest assumption: zero Top5 conversion over eight rounds means the marginal four Weight KDJ slots are less valuable than ordinary search slots. Source memberships overlap, and Top5 is an eval-slice search diagnostic rather than predictive evidence.

Test for the structural pass: preserve three Weight KDJ candidates, change only the operational share, and compare full source-survival trajectories after enough new-run rounds accumulate.

## Riemann pass: structure

Strongest claim: the experiment changes sampling density within the same candidate space, not the promotion boundary. It keeps a Weight KDJ canary path while giving the broader local geometry four more ordinary probes per round.

Weakest assumption: ordinary exploitation/exploration/replay buckets cover meaningfully different rank geometry rather than generating duplicates of existing candidates.

Test for the verification pass: confirm the generated/refined counts, unique configurations, rank signatures, source survival, and round repetition in the fresh run instead of relying only on the configured share.

## Cross-review

Gauss rejects deleting Weight KDJ or changing two zero-conversion sources at once because that would remove the control path and confound attribution. Riemann rejects interpreting eight local rounds as proof that the Weight KDJ family is globally useless. Both accept a reversible 7-to-3 density reduction with unchanged promotion gates.

## Disagreement

- Evidence: two new rounds are sufficient for runtime acceptance but not for comparative search or predictive conclusions. The new run still needs a longer same-run survival window.
- Scope: improved ordinary-source conversion would show better use of this local budget, not that ordinary candidates are inherently superior.
- Risk: repeated search can overfit the eval slice. Frozen validation, null diagnostics, and forward evidence remain the only model-strength boundaries.

## Synthesis

Smallest shared conclusion: run one reversible operational experiment at Weight KDJ share 0.10, preserve three advisor candidates per round, and return four slots to ordinary search. Accept only runtime and allocation correctness after one to two rounds; defer any stronger conclusion until the new run reaches the same maturity threshold.

## Implementation

`scripts/ensure_training_supervisor.sh` now defaults `DEHPS_WEIGHT_KDJ_BUDGET_SHARE` to `0.10` and passes it explicitly to the supervisor. The environment variable keeps the experiment reversible without changing model or promotion code.

Fresh supervisor:

- run id: `20260710-174409`;
- PID: `2345843`;
- issue: `2026078`;
- historical sync before launch: zero inserts, zero updates, zero conflicts;
- command line includes `--weight-kdj-budget-share 0.10`.

## Live verification

Round 1 completed without runtime error:

- persisted Weight KDJ budget was 3 and the source generated three candidates, so the advisor path remained active;
- total budget remained 28;
- target-weight inversion had no round-1 candidates, so the four returned slots were distributed as exploitation `5→6`, exploration `3→5`, and replay `2→3` relative to the baseline run's first round;
- ordinary candidates generated 15, 11 reached full evaluation, and all five Top5 positions came from the ordinary source;
- Weight KDJ, Ridge KDJ, Neural KDJ, and recency canary remained in `observing` state after one round, as required by the maturity gate;
- frozen promotion was evaluated, did not pass, and was not bypassed; the candidate and incumbent frozen-primary scores both remained `[0, 0, 0]`;
- watcher action remained `continue_current_run`; advisor signals were current through `2026078`; parser/sync/duplicate checks passed.

The first round proves allocation and runtime correctness only. It does not prove improved search efficiency or model strength.

Round 2 also completed without runtime error:

- persisted budget matched the target-available calculation exactly: exploitation 5, exploration 3, replay 2, baseline 1, Weight KDJ 3, Ridge 3, Neural 3, recency 4, and target inversion 4; total 28;
- across the first two rounds, ordinary candidates generated/selected/Top5 were `26/21/10`, versus `18/18/9` in the first two rounds of the 0.22-share baseline run;
- Weight KDJ generated six candidates across two rounds and remained present, while none reached full evaluation; this remains an immature source window, not a starvation conclusion;
- Neural KDJ reached Top5 and was round best in round 2; because source memberships overlap, this is search-pipeline evidence only;
- watcher severity was `ok`, action was `continue_current_run`, advisor freshness was current, parser/sync/duplicate checks passed, and no round repetition alert was active;
- frozen promotion was evaluated in both rounds, passed in neither, and was bypassed in neither;
- static metrics remained `[3, 3, 3]`, Dynamic KDJ remained `[2, 3, 3]`, near-term Dynamic KDJ remained `[0, 0, 0]`, and the incumbent frozen-primary score remained `[0, 0, 0]`.

The returned slots produced eight additional ordinary candidates, three additional prefilter survivors, and one additional overlapping Top5 attribution over the matched first two rounds. This supports continuing the experiment, but it does not yet establish a frozen-validation or predictive benefit.

Validation:

- `bash -n scripts/ensure_training_supervisor.sh` passed;
- `git diff --check` passed;
- the supervisor launch command and both persisted round budgets independently confirmed share 0.10;
- two complete live rounds finished, and PID `2345843` continued into round 3.

## Falsification and next verification

The operational hypothesis is falsified if the persisted candidate budget is not 3 for Weight KDJ, the total budget changes from 28, Weight KDJ disappears, or the fresh supervisor cannot complete rounds cleanly. A search-efficiency benefit remains unproven unless a mature same-run window shows that the returned slots increase distinct/full-eval useful candidates without worse repetition or frozen-validation behavior.

## Guardrail

This is a search-budget experiment, not a prediction claim. No candidate may be promoted without the existing frozen validation, null baseline, leakage, parser/sync, and duplicate checks.
