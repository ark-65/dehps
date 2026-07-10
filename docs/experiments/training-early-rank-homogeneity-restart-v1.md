# Training Early Rank Homogeneity Restart V1

## Round frame

Primary goal: let the supervisor begin its existing bounded restart exploration after four consecutive stagnant rounds with one exact round-best rank signature, instead of waiting at least sixteen rounds before reacting to an already reproduced local attractor.

Non-goals:

- no new model, advisor, feature, weight, objective, candidate family, or promotion rule;
- no reduction of the global 16-round stagnation threshold used by other recovery and overfit controls;
- no removal of the existing 16-round, 12-signature, at-most-four-signature low-diversity cycle detector;
- no claim that restart candidates are predictively stronger without frozen-validation lift;
- no change to null diagnostics, parser/sync/duplicate checks, advisor freshness, history scope, or leakage boundaries.

## Task frame

Runs `20260710-174409` and `20260710-181537` used the same issue `2026078` and the same persisted incumbent while changing only the Weight KDJ candidate share from 0.10 back to 0.22. Each run repeated the same round-best config `0169605b...`, metric signature, and objective `5083.940308` in all four observed rounds. The source-budget change altered pipeline throughput but not the attractor. In both runs, the existing rank-homogeneity guard remained inactive because its stagnation threshold was 16 and its observation window was 12; restart budget and generated restart candidates therefore remained zero.

Progress in this round means:

- four exact, consecutive, observed rank signatures plus four stagnant rounds activate the rank-homogeneity guard;
- varying recent signatures, fewer than four stagnant rounds, or a missing signature do not activate it;
- the original slower low-diversity-cycle detector still activates independently;
- a fresh supervisor reaches the trigger boundary, reserves five of 28 slots for the existing bounded `stagnation_restart` source, and completes the triggered round without runtime error;
- frozen promotion remains evaluated, not bypassed, and unchanged.

## Historical boundary

The Gauss and Riemann names below denote historically inspired reasoning lenses, not literal minds, trained replicas, or evidence by authority.

## Gauss pass: verification

Strongest claim: two same-history, same-incumbent four-round observations produced eight exact config/metric repetitions across both candidate-budget settings, while the restart mechanism received zero candidates solely because its 16/12 activation boundary had not been reached.

Weakest assumption: four consecutive signatures are enough to identify a local attractor rather than a transient plateau. The early trigger therefore requires one exact signature, not merely low diversity, and changes only a bounded exploration budget.

Verification test: assert exact activation at stagnation/window `4/4`, rejection at `3/4`, rejection when fewer than four consecutive signatures are observed, rejection when the recent four contain two signatures, and preservation of the legacy `16/12/≤4` activation path.

## Riemann pass: structure

Strongest claim: the matched budget experiment indicates that the bottleneck is downstream of source allocation. The current local candidate geometry can vary configuration coordinates while repeatedly mapping to one rank vector and one objective point.

Weakest assumption: the existing deterministic restart anchors are far enough away in rank geometry, rather than only in parameter coordinates. A generated restart candidate that leaves the rank vector unchanged is not evidence of escape.

Structural test: after live activation, inspect restart generation, full-eval survival, `changed_target_count`, rank-vector change, source-frontier diagnostics, and search-base navigation. Do not infer benefit from candidate count alone.

## Cross-review

Gauss rejects lowering the global stagnation threshold or weakening frozen promotion because the evidence concerns search recovery, not generalization. Riemann rejects replacing the older 12-round low-diversity detector with an exact-repeat-only detector because a short exact-repeat test would miss longer multi-signature cycles. Both accept a two-stage guard: strict early exact repetition plus the unchanged slower cycle fallback.

## Disagreement

- Evidence: four rounds can justify a reversible restart probe, but not model promotion or a predictive-performance claim.
- Structure: parameter-distance bounds do not guarantee changed target ranks; live rank movement is the decisive structural observation.
- Risk: repeatedly searching the same eval slice can overfit even when rank signatures change. Frozen validation and null/leakage diagnostics remain the promotion boundary.

## Synthesis

Smallest shared conclusion: add an early `4/4/1` exact-repeat trigger that reserves the existing bounded restart budget, retain the legacy `16/12/≤4` low-diversity trigger, and expose which mode activated. Do not alter the incumbent unless the existing frozen-validation promotion gate passes.

## Implementation

- Added early rank-homogeneity constants: stagnation threshold 4, window 4, and maximum unique signatures 1.
- Required all four most recent rounds to contain an observed signature, preventing missing telemetry from being bridged by older rounds.
- Preserved the existing 16-round, 12-observation, at-most-four-signature fallback.
- Added `trigger_mode` and fallback counters to supervisor metadata and watcher summaries.
- Kept the existing restart budget calculation, which reserves five candidates when the round cap is 28.

## Validation

- focused supervisor guard/restart tests: `9 passed`;
- watcher suite: `53 passed`;
- full worker suite: `443 passed`;
- `git diff --check` passed.

## Fresh supervisor

- run id: `20260710-190058`;
- PID: `2431886`;
- issue: `2026078`;
- Weight KDJ share: recorded baseline `0.22`;
- historical sync before launch: zero inserts, zero updates, zero conflicts;
- live trigger verification: passed in round 5 after four consecutive completed signatures.

Preflight run `20260710-185556` was deliberately stopped during its first round after review found that fallback-mode telemetry would display the early threshold rather than the threshold that actually fired. The activation logic was already correct, but accepting contradictory operator output would violate the audit goal. The metadata was corrected, focused tests were rerun, and the fresh run above was started from the final code.

## Live verification

Rounds 1–4 completed without runtime error and all persisted the same rank signature `d43d9d633505f974...` with `improved=false`. The guard correctly remained inactive with restart budget zero before the boundary:

- round 1: stagnation/observed/unique `0/0/0`;
- round 2: `1/1/1`;
- round 3: `2/2/1`;
- round 4: `3/3/1`.

Round 5 then activated from the four completed prior rounds:

- trigger mode `exact_repeat`, active threshold/window/unique `4/4/1`;
- legacy fallback metadata remained `16/12/≤4`;
- restart budget 5, generated 5, prefilter-selected 2, and total full-eval candidates increased to 19;
- the selected restart champion was full-eval rank 13 and changed ranks for all 100 targets, with maximum absolute rank delta 886,866;
- its primary pattern was structural/frequency/omission `0.05/1.15/0.05`, with five context fields moved;
- its frozen-primary score `[0,0,1]` exceeded its recorded baseline `[0,0,0]`, so the source-frontier diagnostic classified the movement basis as primary rather than secondary;
- the supervisor selected it as the decision-round recovery candidate while routing its primary-lift navigation through the standard search path;
- the round still finished `no_improvement`; the actual round-best promotion gate was evaluated, failed with `frozen_validation_not_better`, and was not bypassed.

The triggered round completed its Static, Dynamic KDJ, near-term Dynamic KDJ, strategy-memory, database, and status writes without error. The watcher reported severity `ok` and action `continue_current_run`. Advisor signals were current through `2026078`. Parser/sync/duplicate checks passed, including 3,475 history rows with no duplicate issues or invalid balls and the complete legal red-ball universe of 1,107,568 combinations.

This passes both runtime falsification tests and the rank-movement structural test. It does not pass a model-strength test: the latest static line remained `[3,3,3]`, Dynamic KDJ was `[0,1,2]`, near-term Dynamic KDJ was `[0,0,1]`, the promotion gate did not pass, and round-best config/metric repetition remained active at five of five rounds.

## Outcome and next verification

The early recovery mechanism now reacts after four exact stagnant rank signatures instead of waiting sixteen rounds, and live evidence shows that it generated, retained, and fully evaluated a materially different rank geometry without weakening promotion. The immediate soft-stall diagnosis is therefore narrower: the search loop can now produce a structurally different recovery candidate, but it has not yet converted that candidate into a better frozen-validated incumbent.

Keep supervisor `20260710-190058` running. The next audit should check whether rounds 6–7 break the repeated round-best signature, whether the new standard search path preserves candidate diversity, and whether any lift survives frozen validation and the ranked-uniform null discipline. Continued repetition is not a reason to lower promotion thresholds; it is evidence for the next bounded search-geometry experiment.

## Predeclared falsification

- If the fifth round begins after four exact stagnant signatures but does not persist `trigger_mode=exact_repeat`, restart budget 5, and generated restart candidates, the implementation fails.
- If a triggered round errors, fails to persist, or bypasses frozen validation, the runtime change fails and must be fixed in a fresh run.
- If restart candidates do not change any target rank in one to two triggered rounds, escape from the local geometry remains unproven; candidate generation alone is not success.
- If frozen validation does not improve, this round must not be described as a stronger model even when the search base moves.

## Guardrail

This change accelerates bounded search recovery only. Historical lift or rank movement is hypothesis evidence; no candidate is promoted without the existing frozen validation, null baseline, leakage, parser/sync, and duplicate checks.
