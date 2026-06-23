# Self-Iteration Report: Git Helper Missing Allowed Paths

Date: 2026-06-23

## Primary Goal

Fix the auto-git helper so missing allowed directories do not make `git add` fail before valid allowed changes can be staged.

## Non-Goals

- No training, scoring, backtest, candidate-generation, or prediction logic changes.
- No generated `data/output` or `runtime` artifacts are promoted.
- No change to DEHPS evidence level or betting/prediction language.

## Change

`apps/worker-python/scripts/git_commit_and_push.py` now filters `ALLOWED_PATHS` to paths that exist under the repository root before calling `git add`.

This avoids the current local failure mode where absent `data/raw` and `data/processed` directories can produce:

```text
fatal: pathspec 'data/raw' did not match any files
```

## Validation

Focused validation:

```bash
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_git_commit_and_push.py
```

Result: 3 passed.

Broader worker validation:

```bash
apps/worker-python/.venv/bin/python -m pytest -q
```

Result: 198 passed.

## Guardrail

This is an operational reliability fix. It does not affect historical ranking behavior, strategy selection, or any claim about predictive ability.
