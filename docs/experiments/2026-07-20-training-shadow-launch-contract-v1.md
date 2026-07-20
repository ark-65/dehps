# Training Shadow Launch Contract v1

## Incident

Operator execution 57 replaced the stale training supervisor with merged commit
`b083de59b8742e443d6c5517d5790da1edacd3a7`. The process completed round 1 and
created the missing `dynamic_kdj_near` run for target 2026083, but the run did
not contain `shadow_scoring_evidence`.

The snapshot code correctly gates simultaneous capture on
`DEHPS_FORWARD_SHADOW_CAPTURE`. The production launcher did not define or pass
that variable, so a clean operator shell silently disabled capture. The prior
process happened to have the variable only because its original launch
environment supplied it.

The 2026083 near run remains immutable evidence. It is not rewritten or given a
post-hoc simultaneous marker, and target 2026083 is not eligible for the
three-issue shadow cohort.

## Contract

`scripts/ensure_training_supervisor.sh` is a production launcher, so shadow
capture is mandatory rather than caller-dependent:

- `DEHPS_FORWARD_SHADOW_CAPTURE=true` is injected explicitly;
- `DEHPS_FORWARD_SHADOW_WORKERS` is explicit and must be a positive integer;
- an adopted process must expose the exact expected values in `/proc/PID/environ`;
- a mismatched adopted process is stopped before it can be accepted as current;
- a newly launched process is verified after `exec`, and is stopped if the
  environment contract is absent or mismatched.

This change does not alter scoring, ranking, model selection, prediction
identity, existing candidates, or shadow comparison semantics.

## Validation

```text
bash -n scripts/ensure_training_supervisor.sh
# passed

DEHPS_FORWARD_SHADOW_WORKERS=0 scripts/ensure_training_supervisor.sh
# exit 1 before database or process operations

apps/worker-python/.venv/bin/python -m pytest -q \
  apps/worker-python/tests/test_training_supervisor_watchdog_contract.py \
  apps/worker-python/tests/test_forward_wait_sync_decoupling.py \
  apps/worker-python/tests/test_forward_shadow_capture.py
# 18 passed

apps/worker-python/.venv/bin/python -m pytest -q
# 1271 passed, 4 existing Python 3.14 fork deprecation warnings
```

`shellcheck` was not installed in the execution environment; Bash syntax and
the repository's launcher-contract tests were used instead.
