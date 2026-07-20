# Forward Line Completion v1

## Round contract

- Engineering Request: `engineering-forward-line-completion-5aa4b14`
  (request 134).
- Primary goal: make multi-line production persistence independently idempotent.
- Non-goals: no production backfill, existing-run rewrite, strategy change,
  systemd deployment, backend switch, or promotion.

## Live reproducer

After issue 2026082 synchronized, target 2026083 contained:

| Line | State | Candidates | Simultaneous capture |
| --- | --- | ---: | --- |
| `static_100` | pending | 10,000 | yes |
| `dynamic_kdj` | pending | 10,000 | yes |
| `dynamic_kdj_near` | missing | 0 | no run |

Training rounds 73, 74, and 75 completed near-line training, then each logged:

```text
active_forward_prediction_exists:line_key=static_100:target_issue=2026083
```

The fixed-order batch stopped at the first line, so near-line persistence was
unreachable.

## Change

- Add explicit `reuse_active=True` completion semantics to the storage boundary.
- Serialize completion by line and target with a transaction-scoped advisory
  lock.
- Return immutable existing identity without any DELETE, INSERT, UPDATE, or
  supersede action for reused lines.
- Let the multi-line refresh continue to later missing lines.
- Report created and reused lines separately.

## Validation

Focused storage, candidate, supervisor, and daily-pipeline tests cover:

- default fail-closed behavior remains unchanged;
- an active line produces `reused_active` and no candidate/dashboard writes;
- a missing line follows the normal create path;
- static and dynamic reuse does not block near creation;
- repeated multi-line refresh reports structured idempotent results.

Validation commands:

```text
apps/worker-python/.venv/bin/python -m pytest -q \
  apps/worker-python/tests/test_postgres_store.py \
  apps/worker-python/tests/test_next_candidates.py \
  apps/worker-python/tests/test_training_supervisor.py \
  apps/worker-python/tests/test_daily_pipeline.py
# 225 passed

apps/worker-python/.venv/bin/python -m pytest -q
# 1270 passed, 4 existing Python 3.14 fork deprecation warnings
```

This engineering round does not call the live refresh function and does not
change target 2026083. Production completion requires a separate approved
Operator execution after merge.
