# Self-Iteration Report: Hourly Lock Skip Status

Date: 2026-06-26

## Primary Goal

Make the two-hour self-iteration wrapper leave a fresh status artifact when it skips because another self-iteration process already holds the scheduler lock.

## Non-Goals

- No training, scoring, backtest, candidate-generation, or advisor logic changes.
- No generated `data/output` or `runtime` artifacts are promoted.
- No change to DEHPS evidence level, prediction claims, or betting language.

## Change

`scripts/hourly_self_iterate.sh` now writes `runtime/logs/hourly_self_iterate.last.md` with status `lock_held` before exiting successfully from the lock-conflict path.

Previously that branch only printed a stdout line. Operators reviewing the last-message artifact could therefore see a stale prior result after a skipped scheduled run.

## Validation

Focused validation:

```bash
bash -n scripts/hourly_self_iterate.sh
tmp="$(mktemp -d)"
mkdir -p "$tmp/nodebin" "$tmp/logs"
ln -s /bin/true "$tmp/nodebin/node"
exec 8>"$tmp/logs/hourly_self_iterate.lock"
flock -n 8
DEHPS_REPO_ROOT="$PWD" \
DEHPS_LOG_DIR="$tmp/logs" \
DEHPS_CODEX_BIN=/bin/true \
DEHPS_NODE_BIN_DIR="$tmp/nodebin" \
  scripts/hourly_self_iterate.sh
```

The temporary-lock invocation exited successfully and wrote status `lock_held` to the temporary `hourly_self_iterate.last.md`.

The broader worker, API, and web test suites were already green before this operational-script-only change:

```bash
apps/worker-python/.venv/bin/python -m pytest -q
npm test  # apps/api
npm test  # apps/web
```

Result: worker tests passed (`256`), API tests passed (`42`), and web tests passed (`18`).

## Guardrail

This is an operational observability fix only. It does not alter historical ranking behavior, structural scoring, candidate generation, strategy selection, or any claim about predictive ability.
