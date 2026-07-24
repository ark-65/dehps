# M4 Information-Theory Evidence P0 Migration

- Date: 2026-07-24
- Role: Engineering Agent
- Engineering authorization: Agent Request
  `engineering-m4-information-theory-p0-migration-20260724` (request `212`,
  execution `133`)
- Primary goal: migrate the unified control plane from the rejected adaptive
  training mainline to `M4_INFORMATION_THEORY_EVIDENCE`
- Non-goals: no preregistration content, statistical estimator, formal
  real-data analysis, model, feature, ranking, candidate, supervisor, database,
  or production change
- Production impact: none

## Outcome

P0 is represented as complete in one canonical, digest-addressed Research OS
manifest. P1 is the next Ready Queue task. The exact `2026085` draw event is a
task-local forward dependency and does not suppress P1.

The legacy Research OS lifecycle uses `retired`, while its immutable research
and operating statuses are recorded separately as `rejected` and `frozen`.
This preserves the existing accepted lifecycle schema without disguising the
scientific conclusion:

```text
ADAPTIVE_TRAINING_SIGNAL_OPTIMIZATION
  lifecycle = RETIRED
  research status = REJECTED
  mainline status = FROZEN

M4_INFORMATION_THEORY_EVIDENCE
  lifecycle = ACTIVE
  current phase = M4-P1
  current state = READY
```

Canonical artifact:

- path: `configs/research-os/m4-information-theory-evidence-v1.json`
- manifest digest:
  `84e59c1f2c8a556a5c00f9a3e68776e8b07b466d9f0a3292c2055a3c1dd2f4c0`
- last legacy formal commit:
  `3bfc14adeb66f2f320bf51b4dd9a8b6d4d156948`
- `2026084` settlement digest:
  `ef4817983ccc209aa87ff00a12be0e9f0ad263a00d8b008d873d6722d73ff932`

## Audit evidence

The P0 audit found:

- Hypothesis `seven-red-compound-top10-walk-forward-v1` is `rejected` in the
  Hypothesis Registry.
- Legacy supervisor run `20260721-220017` is
  `waiting_for_forward_issue`; its reported PID is inactive.
- No `run_training_supervisor` or `training_supervisor` process is active.
- The `2026084` settlement records `promotion_gate_opened=false` and
  `production_action=none`.
- The continuous research and forward residents remain active; neither is the
  adaptive training supervisor.
- The durable Research OS PostgreSQL migration is not applied to the live
  database. This round deliberately does not apply it. The canonical source
  manifest and read-only resolver are therefore the authoritative P0 surface.

## Einstein pass

- Core question: can the system change what it measures next without
  accidentally resuming the falsified optimization loop?
- Invariant: every legal six-red combination remains equally likely under the
  theoretical null; no engineering completion or historical fit counts as
  forward predictive evidence.
- Hypothesis: a typed Goal/Task migration can make P1 the only schedulable
  research path while leaving future settlement as a local external wait.
- Measurement: resolver state, Ready Queue contents, immutable digests,
  engineering/evidence progress, and gate fields.
- Failure mode: a legacy tuning task becomes ready, `WAIT_FORWARD` suppresses
  P1, code completion raises evidence progress, or a formal run starts before
  preregistration.
- Next experiment: define and review the smallest immutable P1 measurement
  contract before implementing any estimator.

## Dependency graph

```text
P0 migration COMPLETE
  -> P1 contract and preregistration READY
  -> P2 synthetic measurement validation
  -> P3 strict historical walk-forward
  -> P4 negative controls and robustness
  -> P5 cumulative forward evidence
  -> P6 information bound and automatic decision

draw:2026085
  -> forward-evidence intake EXTERNAL_WAIT
  -> P5 cumulative forward evidence
```

The forward intake is deliberately independent of P1-P4 in the resolver. When
the exact draw event arrives, only the intake becomes ready; it still cannot
complete P5 until the prior measurement gates have completed.

## Unified status

```text
Goal: M4_INFORMATION_THEORY_EVIDENCE
Current Phase: M4-P1
Current State: READY
Completed:
- legacy hypothesis rejection/freeze recorded
- final baseline, commit, and 2026084 settlement recorded
- legacy adaptive tuning tasks superseded
- M4 P0-P6 dependency graph activated
Evidence Changed:
- none
Gate Status:
- Promotion Gate: CLOSED
- Adaptive Supervisor: STOPPED
- Production Action: none
Progress:
- Engineering: 5%
- Evidence: 0%
- Historical WF: 0 / not preregistered
- Forward Samples: 0
- Synthetic Scenarios: 0 / 9
- Negative Controls: 0 / 6
- Feature Families: 0 / 7
Current Statistics:
- OOS Log-loss Improvement: not available
- Bits Gain: not available
- Confidence Interval: not available
- Practical Null: NOT_PREREGISTERED
- MDE: not available
- Power: NOT_EVALUATED
Blocked By:
- none
Next Ready Task:
- m4-p1-contract-and-preregistration
Next External Dependency:
- draw:2026085
Stop Condition Status:
- NOT_EVALUATED
```

Engineering progress is calculated only from phase engineering deliverables.
Evidence progress is calculated only from explicit evidence components. P0
therefore raises engineering progress to 5% and leaves evidence progress at
0%.

## Nightly routing

`scripts/hourly_self_iterate.sh` now resolves the canonical M4 status before it
dispatches Codex and writes the verified snapshot to
`runtime/logs/m4-information-theory-status.json`. A failed manifest/digest
preflight stops the iteration. The prompt names M4 as the only mainline, limits
work to `next_ready_task`, and treats the old training checklist only as
conditional defensive guardrails.

## First minimal task slices

1. `P1-A`, Research role: create a typed request that freezes the scientific
   question, legal sample space, null, minimum non-null, primary endpoints,
   practical-null units, failure conditions, feature/target identities, and
   prohibited post-result changes. No file or Shell mutation.
2. `P1-B`, Engineering role after approval: implement only schemas, canonical
   validation, digest generation, and fail-closed preregistration CLI. Do not
   implement estimators or execute real data.
3. `P1-C`, Reviewer role: bind the exact preregistration digest and verify that
   the formal real-data state remains `NOT_STARTED`.
4. Only after P1 completes, create a separate P2 engineering request for the
   smallest synthetic-null and injected-signal measurement harness.

## Validation

Focused validation completed:

```text
apps/worker-python/.venv/bin/python -m pytest -q \
  apps/worker-python/tests/test_information_theory_control_plane.py \
  apps/worker-python/tests/test_research_os_control_plane.py \
  apps/worker-python/tests/test_research_os_cli.py

21 passed
```

Full validation completed:

```text
apps/worker-python/.venv/bin/python -m pytest -q
1572 passed, 4 skipped, 4 warnings

cd apps/api && npm test
117 passed

cd apps/web && npm test
19 passed

cd apps/web && npm run build
production build completed

bash -n scripts/hourly_self_iterate.sh
passed

git diff --check
passed
```

The four Worker warnings are existing Python 3.14 multiprocessing `fork`
deprecation warnings. No training, optimization, advisor, or supervisor code
changed, so no fresh training supervisor was started.
