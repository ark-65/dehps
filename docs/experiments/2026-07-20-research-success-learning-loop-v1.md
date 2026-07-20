# Research Success Learning Loop v1

## Primary goal

Keep DEHPS learning during a production forward wait. The research lane must search for a challenger and validate it against the incumbent on the same most-recent 100 historical issues. Production prediction creation, production candidate storage, shadow-period accounting, and backend promotion remain separate operations.

The recent-100 backtest is the declared historical learning objective for this round. It demonstrates whether the search learned a configuration that improves the declared historical success metrics. It is not, by itself, independent proof of future predictive generalization.

## Non-goals and invariants

- Do not create another formal prediction for the pending target issue.
- Do not write research candidates into `training_next_candidates_current`.
- Do not promote a production model or backend.
- Do not count shadow evidence.
- Do not change prediction, evaluation, ranking, feature, or candidate contracts.
- Do not treat a different run id, timestamp, or seed as research novelty.

## Root cause

The previous waiting path conflated three independent concerns:

1. the production lock correctly prevented duplicate forward predictions;
2. the isolated research suite was predominantly a finite static diagnostic suite, so an identical suite fingerprint stopped useful work;
3. the training supervisor used the production frozen-selection gate to decide whether an observability-only challenger was a research improvement.

As a result, `WAITING_FOR_DRAW` behaved too much like a global training stop. The production lock, shadow evidence gate, and production promotion gate were incorrectly allowed to block research iteration even though none of them is part of the research execution interface.

## Implemented contract

The default waiting research lane now runs:

- `training-diagnostics`;
- `analytic-null-baseline`;
- `adaptive-success-training`.

`adaptive-success-training` is deterministic and observability-only. Each round searches candidate configurations, evaluates incumbent and challenger on the same recent-100 issue identity, and records:

- Top100, Top1000, and Top10000 hit deltas;
- median, best, and worst actual-combination rank deltas;
- paired issue count and evaluation identity;
- research-selection and production-selection decisions separately;
- explicit failure reasons when learning is not demonstrated.

The waiting supervisor launches a long-running 512-round adaptive job. A new history issue preempts that job so the production/evaluation path can proceed. An unchanged history snapshot does not stop internal research rounds. Exact continuation identity is based on evaluated configurations, current research champion/search base, code, history, and effective configuration—not a run id or clock value.

Research output remains local and read-only with respect to PostgreSQL. The compact status and isolated-lane report now carry the latest learning comparison and a deduplicated research candidate state so the next run can continue meaningfully without persisting full per-issue target arrays.

## Replay and success semantics

A challenger is eligible to become the local research champion only when:

1. its effective configuration hash differs from the incumbent;
2. the declared search objective improves;
3. incumbent and challenger use the same 100-issue evaluation identity;
4. the full recent-100 success contract improves.

An identical configuration is classified as `incumbent_replay`. It cannot be reported as learning even if unrelated diagnostic metadata changes.

## Validation

### Automated

```text
apps/worker-python/.venv/bin/python -m pytest -q
1285 passed, 4 warnings in 40.31s
```

The warnings are the existing Python 3.14 process-fork deprecation warnings in parallel tests. Targeted research-lane and supervisor coverage reported 193 passing tests before the full worker suite.

Coverage includes deterministic continuation fingerprints, waiting-lane defaults, observability-only lock ownership, full recent-100 paired rank evidence, replay rejection, compact status propagation, and production-selection isolation.

### Live round 1: runtime acceptance and defect discovery

- Run id: `20260720-115336`
- Output: `data/output/optimization/research-lane/adaptive-success-acceptance-v1`
- Result: completed in 1,340.715 seconds
- Effective workers: 16
- Main recent-100 evaluation: 100/100 issues
- Observed incumbent success: Top100 `3`, Top1000 `3`, Top10000 `4`

This round found two acceptance defects: compact status did not propagate the learning evidence, and an unchanged configuration could be labelled `retained_new_best` because production-oriented metadata differed. Both defects were fixed before the second round.

### Live round 2: corrected acceptance

- Run id: `20260720-121911`
- Output: `data/output/optimization/research-lane/adaptive-success-acceptance-v2`
- Result: completed in 1,349.917 seconds
- Main recent-100 evaluation: 100/100 paired issues
- Incumbent/challenger Top100: `3 / 3`
- Incumbent/challenger Top1000: `3 / 3`
- Incumbent/challenger Top10000: `4 / 4`
- Median actual rank: `496,383 / 496,383`
- Best actual rank: `44 / 44`
- Worst actual rank: `1,099,047 / 1,099,047`
- Decision: `no_learning_lift`
- Reasons: `no_success_objective_lift`, `incumbent_replay`, `full_evaluation_window_success_not_improved`
- Research selection changed: `false`
- Production selection changed: `false`

The second run proves that an unchanged configuration is rejected as replay and that the complete learning evidence reaches the isolated-lane artifact. A failed round is therefore evidence, not an invented success; the long-running supervisor may continue with meaningfully different candidate configurations.

### Stage timings from live round 2

| Stage | Wall time | Workers |
| --- | ---: | ---: |
| Candidate generation | 1.104 s | 1 |
| Prefilter | 103.940 s | 16 |
| Main recent-100 evaluation | 188.259 s | 16 |
| Post-evaluation diagnostics | 0.047 s | 1 |
| Target inversion evaluation | 47.444 s | 16 |
| Near-miss inversion | 1.817 s | 1 |
| Dynamic KDJ training | 628.990 s | 16 |
| Near dynamic KDJ training | 28.671 s | 9 |

CPU work is active in the principal training stages. Dynamic KDJ is now the dominant single-stage cost and is a future performance target, not a correctness blocker for this round.

## Production-state verification

After both live runs, `training_next_candidates_current` remained:

```text
next_issue=2026083, rows=30000, lines=3
```

The live persistence policy also reported:

```text
database_writes=false
prediction_refresh=false
training_event_posts=false
database_guard=postgres_default_transaction_read_only
```

No formal prediction, pending candidate, production selection, shadow evidence, or production backend state was changed.

## Operational result

The state semantics are now:

```text
WAITING_FOR_DRAW
  production: duplicate prediction locked
  research: adaptive recent-100 learning continues
  shadow: unchanged
  promotion: unchanged
```

This restores the intended separation: recent-100 learning is the research main line, while future draw evaluation remains a separate out-of-sample evidence stream.
