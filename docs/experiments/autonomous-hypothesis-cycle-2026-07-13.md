# Autonomous Hypothesis Cycle — 2026-07-13

## Task frame

The user asked DEHPS to continue training through independent analysis rather than repeat an already stalled optimizer. This round tests two distinct nonlinear hypotheses and strengthens the self-iteration prompt so a parked system must formulate, falsify, reject, and change mechanism.

## Historical boundary

Einstein, Gauss, and Riemann are used as historically inspired reasoning lenses, not literal minds or evidence for prediction.

## Invariants

- Every legal six-red combination remains equally likely under the lottery null absent measured physical bias.
- Current inputs do not include ball mass, initial placement, air flow, machine state, or other causal draw-state variables.
- The legal and ranked universes, history boundary (`2026079`), static baseline, null controls, and frozen promotion quarantine remain unchanged.
- All artifacts in this round are research-only and do not rewrite the three frozen `2026080` lines.

## Hypothesis 1: nonlinear structural separability

Core question: do the existing 61 transparent structural features contain a stable nonlinear signal separating historical combinations from same-budget uniform negatives?

- Null: validation AUC 0.5.
- Minimal non-null: a fixed 16-unit CPU MLP trained for 10 epochs.
- First test, random split, seeds 17/37/20260713: final validation AUC 0.519047 / 0.529725 / 0.529677.
- Easiest deception: random splitting mixes early and late historical positives, measuring global structural separability rather than temporal continuation.

The neural feasibility probe now supports `--split-mode temporal-positive`: the first 80% of ordered historical positives train the model, the last 20% validate it, negative samples are disjoint, and standardization is fitted only on training rows.

Temporal-positive results for the same seeds were 0.515995 / 0.502767 / 0.522363. This signal is weak and seed-unstable. Hypothesis 1 is rejected for promotion and does not enter walk-forward prediction.

## Hypothesis 2: nonlinear KDJ weight interaction

Core question: did linear dynamic KDJ fail because weight-signal interactions are nonlinear?

- Candidate: fixed neural-KDJ advisor v0, seed 17, 8 hidden units, 400 epochs, joint mode.
- Baselines: current frozen best, structural, frequency, omission, null, random same-budget and constant perturbations.
- Failure: reject unless frozen objective beats every control and tail risk is no worse than the current frozen best.

Result: candidate frozen objective `-22.875520` versus current frozen best `4147.179414`; Top100/Top1000 were `0/0` versus `3/3`, and tail risk was worse (`42.145605` versus `38.438831`). Hypothesis 2 is rejected. Increasing neural depth, epochs, or nearby KDJ parameters on the same history is not an allowed recovery.

## Gauss pass

Both hypotheses preserved the legal sample space and used explicit null/baseline comparisons. The temporal split fixes the most immediate validation-boundary weakness. Neither result supports a predictive claim.

## Riemann pass

The random-split and temporal-split tasks are different spaces: global structural separability is not temporal continuation. The observed drop and seed dispersion show that the apparent nonlinear structure does not yet define a stable continuation across time.

## Synthesis

DEHPS is currently an auditable scientific execution system with bounded ML components, not an autonomous general intelligence. The agent layer supplies hypothesis generation; code supplies deterministic falsification; history and forward evidence judge survival. Stronger autonomy requires preserving rejected hypotheses as decision memory and forcing the next cycle to change mechanism, rather than merely changing parameters.

## Self-iteration change

The two-hour Codex prompt now requires:

- reading the stall root-cause dossier;
- addressing separate evidence/search/model/compute/data dimensions;
- registering exactly one new hypothesis with invariant, null, non-null, baseline, metric, failure condition and self-deception check;
- marking failed hypotheses rejected and changing mechanism next round;
- explicitly allowing the conclusion “no stable signal found”; and
- never repeating a rejected family just to consume CPU.

## Next experiment

The next distinct mechanism should test residual structure over time rather than another KDJ or generic MLP variant: partition misses by transparent feature layer and ask whether residual signs persist across preregistered, non-overlapping temporal blocks. It must compare against same-budget shuffled block labels and stop if direction reverses across blocks.
