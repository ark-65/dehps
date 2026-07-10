# DEHPS Self Diagnostics v1

## Primary Goal

Add a conservative self-diagnostic layer that tells DEHPS when it should distrust dynamic weights, suspect candidate-space collapse, or treat apparent training lift as noise chasing.

## Non-Goals

- No new prediction algorithm.
- No new promoted strategy or weight.
- No betting or future-performance claim.
- No change to supervisor sorting, reward, or candidate promotion behavior.

## Gauss Pass

- Object: historical walk-forward rank evidence and next-candidate snapshots.
- Sample space: legal SSQ red6 combinations, recorded in runtime payloads.
- Null model: uniform red6 rank probability for Top100, Top1000, and Top10000 bands.
- Checks added: leakage status, regression window size, dynamic-offset coverage, binomial null tail, frozen/promotion gate status, duplicate/narrow candidate windows.
- Smallest defensible claim: these diagnostics can reject overconfidence; they do not prove predictive ability.

## Riemann Pass

- Object space: ranked red6 candidate manifold induced by the current scoring function.
- Structural risk: top candidates may collapse into one narrow family even while score changes appear active.
- Checks added: top-window unique red coverage, duplicate combinations, pair-overlap geometry, source survival, and rank-signature diversity.
- Smallest defensible claim: collapse is detectable as a geometric narrowing of the candidate space, not as a new signal.

## Implemented Diagnostics

- Weight trust: marks dynamic weight advice as blocked/caution/trusted based on leakage, regression window size, target coverage, current applied offsets, promotion gate, and advisor rejection/downweight patterns.
- Candidate space: detects collapsed or narrow top-candidate windows and supervisor candidate-source/rank-signature collapse.
- Signal vs noise: compares historical hits to a null binomial baseline, flags small windows, active overfit guardrails, and incomplete forward evidence.

## Operational Effect

- Prediction metadata now includes `self_diagnostics`.
- Near-dynamic line reports render a Self Diagnostics section.
- Supervisor status, compact status, round prefilter info, logs, and markdown reports include round-level self diagnostics.
- The diagnostics are observe/report only in this round; they do not alter promotion, sorting, or search.

## Validation

Targeted tests:

```bash
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_self_diagnostics.py apps/worker-python/tests/test_training_supervisor.py apps/worker-python/tests/test_next_candidates.py
```

Acceptance expectation:

- Leakage or missing dynamic offsets block weight trust.
- Collapsed top windows are detected.
- Small regression windows are labeled noise risk.
- Supervisor-level overfit and rank-homogeneity collapse synthesize into a blocked diagnostic.
