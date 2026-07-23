# Frozen Validation Plateau Stop V1

Date: 2026-07-23

## Decision

Adaptive success training now has an optional frozen-validation plateau stop. The
default isolated research lane enables it with a patience of 40 completed rounds.
When enabled, the supervisor stops with `stopped_plateau` after the frozen
frontier has failed to improve for the configured number of durable rounds.

This is a runtime-governance change. It does not add a feature, model, candidate
source, objective, selector, prediction, or promotion path. Promotion remains
closed.

## Primary Goal

Stop unbounded adaptive search when search-side movement does not produce a
strict improvement on the independent frozen-validation frontier.

## Non-goals

- Do not claim predictive lift.
- Do not change the production selection.
- Do not change the Promotion Gate.
- Do not alter feature weights, candidate generation, or objective scoring.
- Do not implement the 2026084 acceptance pipeline, feature ablation, score
  calibration, negative controls, or champion-collapse audit in this round.

## Authorization

- Engineering Agent Request: `engineering-frozen-plateau-stop-20260723`
  (request 191, execution 112).
- Bounded live-validation Operator Request:
  `operator-validate-frozen-plateau-stop-20260723`
  (request 192, execution 113).
- Persistent legacy-search pause Operator Request:
  `operator-pause-unbounded-research-relaunch-20260723`
  (request 193, execution 114).

The reviewer Decisions cite the user's explicit approval of subsequent
approvals. Each request still freezes its own scope and rollback conditions.

## Contract

The plateau counter uses a frontier independent of the search incumbent.
All evaluated summaries with a complete frozen-validation payload are eligible.
A candidate advances the frontier only when the existing unquarantined frozen
gate accepts it:

1. the primary tuple is strictly higher;
2. frozen objective is strictly higher; and
3. frozen tail risk is not worse.

The first eligible round initializes the baseline and does not count as an
improvement. A raw search improvement without frozen lift is recorded as
`selection_overfit` and does not reset frozen stagnation. Stop is requested only
after a completed round is durable. Disabled patience preserves the previous
runtime behavior.

The status and report expose:

- patience and stagnation rounds;
- frontier identity and compact metrics;
- last frozen and raw-search improvement rounds;
- selection-overfit count;
- one compact history event per completed round;
- stop reason and stopped round.

The isolated research-lane fingerprint includes the configured patience, so a
governance change cannot silently reuse an artifact from a different stop
contract.

## Historical Math Cross-review

### Gauss pass

The stop rule uses explicit invariants: a fixed patience, a strict ordered
primary comparison, a strict objective comparison, a non-worsening tail
obligation, and one state transition per completed round. Tests cover baseline
initialization, frozen lift, raw-only lift, stagnation, missing frozen payloads,
disabled behavior, CLI propagation, and compact persistence.

### Riemann pass

Search movement and frozen evidence are treated as separate state coordinates.
This prevents motion inside the search geometry from being mistaken for movement
toward the production evidence boundary.

### Disagreement

A single advancing frontier is simpler and operationally auditable, but it is
not a full Pareto frontier. A candidate that fails against the current frontier
could be non-dominated in another metric direction.

### Smallest shared conclusion

For a stop-governance rule, the strict frozen gate is sufficient and safer than
allowing search-side movement to reset patience. A Pareto redesign would be a
separate research contract and is not justified by this round.

### Next verification

Use the forthcoming feature-ablation, score-decile, and negative-control rounds
to determine whether any stable forward ranking gradient exists. Do not infer
signal from this stop-rule validation.

## Validation

Automated validation:

```text
apps/worker-python/.venv/bin/python -m pytest -q
1544 passed, 4 skipped
```

The four warnings were the existing Python multiprocessing/fork deprecation
warnings. `compileall` and `git diff --check` also passed. Ruff was not installed
in the project environment.

Bounded live validation:

```text
run_id: 20260723-175514
mode: observability_only
as_of_issue: 2026083
max_rounds: 2
frozen_plateau_patience: 1
completed_rounds: 2
terminal_status: stopped_plateau
stop_reason: frozen_validation_plateau
stopped_at_round: 2
database_writes: false
prediction_refresh: false
production_selection_changed: false
promotion_gate_passed: false
```

Round 1 initialized the frozen baseline. Round 2 produced no strict frozen lift,
raised stagnation to one, and stopped only after `round_completed`. The compact
history contains exactly two events: `baseline_initialized` and
`frozen_plateau`. The heavy-job lock was released and no training supervisor was
left running.

Live artifacts:

- `data/output/optimization/plateau-smoke-20260723/training-supervisor-20260723-175514.json`
  (`sha256 d22d2bd6894316b8d70dfa043cb824740523bb648b4b953f483fafddfb59fc1b`)
- `data/output/optimization/plateau-smoke-20260723/training-supervisor-20260723-175514.md`
  (`sha256 6d5e2fac66b1890d5c74842c14c278df6c2154c98841e808ee4a4effb1dc2e50`)

The live run did not exercise the raw-search-only improvement branch on its
second round; that branch is covered by the focused and full automated suites.

## Operational Finding

The first legacy stop was not persistent: the ten-minute training watchdog
relaunched the old 512-round isolated lane at 17:40. The exact watchdog cron
block was therefore paused before terminating the relaunched process group.
The separate draw-sync cron, two-hour self-iteration cron, pre-draw mail cron,
continuous research runtime, and forward-validation runtime were preserved.
The pre-change crontab is retained as a runtime recovery artifact.

The 18:00 watchdog boundary passed without another legacy relaunch. Continuous
unbounded training remains stopped after the bounded validation run.

## Acceptance

This round accepts only the plateau-stop mechanism and persistent pause of the
legacy unbounded search. It provides no evidence for a production strategy
upgrade. The Promotion Gate remains closed, and 2026084 remains a frozen
old-architecture forward comparison rather than a post-collapse-fix production
result.
