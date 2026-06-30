# Self-Iteration: Training Artifact Atomic Writes

- Date: 2026-06-30
- Primary goal: prevent monitor readers from observing partial supervisor or training-watch artifacts while a live process writes them.
- Non-goals: no strategy, advisor, scoring, candidate generation, database, or prediction behavior changes.

## Trigger

`apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5` succeeded for run `20260630-142439`, but reported `severity=alert` and `action=prepare_restart_with_more_exploration`. The latest supervisor run was still active under the heavy-job lock.

While inspecting the active `training-supervisor-20260630-142439.json`, a concurrent `jq` read intermittently observed truncated JSON. This is an operational observability issue: monitor readers should see either the previous complete artifact or the next complete artifact, not an in-progress write.

## Gauss/Riemann Diagnostic

Historical boundary: Gauss and Riemann are used here only as historically inspired verification and structure lenses, not as authority or reconstructed minds.

Gauss pass: the object is the runtime artifact write contract. The measurable residual is a partial JSON parse failure during an active write. The proof obligation is that replacement is atomic at the target path and leaves no temp file after success or failure. This makes no performance claim and does not alter the legal sample space, historical window, null baseline, leakage checks, or training objective.

Riemann pass: the shared file path is the boundary surface between live training and monitor readers. The singularity is the non-atomic intermediate state created by direct `Path.write_text`. Writing to a sibling temp file and replacing the target makes the reader-facing state transition discrete: old complete artifact to new complete artifact.

## Change

Added `dehps.artifacts.atomic_write_text` and routed supervisor status/report writes plus training-watch artifact/latest writes through it.

## Guardrail Context

Observed supervisor context only:

- Legal universe size: 1,107,568.
- Ranked universe size: 1,105,506.
- Train window: 900.
- Eval window: 100.
- Watch status: active run with 50+ stagnation rounds.
- Baselines in the report: `null_baseline` and `default_baseline`.

This report makes no prediction or betting recommendation. The training stagnation remains an evidence-labeled operational signal for a future restart with broader exploration controls.

## Validation

Completed checks:

- `apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests/test_runtime_artifacts.py apps/worker-python/tests/test_training_watch.py apps/worker-python/tests/test_training_supervisor.py -q` passed, 121 tests.
- `apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5` ran successfully against the pre-existing run and reproduced the `alert` stagnation state.
- Fresh supervisor `20260630-181946` started with the final updated code and the same run arguments as the prior live process.
- `apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --run-id 20260630-181946 --limit 5` reported `round_count=2`, `severity=ok`, and `action=continue_current_run` after two completed rounds.
