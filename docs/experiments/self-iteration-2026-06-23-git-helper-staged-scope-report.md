# Self-Iteration Report: Git Helper Staged Scope Guard

Date: 2026-06-23

## Primary Goal

Prevent the auto-git helper from committing pre-staged files outside its allowed path scope.

## Non-Goals

- No training, scoring, backtest, candidate-generation, or prediction logic changes.
- No generated `data/output` or `runtime` artifacts are promoted.
- No change to DEHPS evidence level or betting/prediction language.

## Change

`apps/worker-python/scripts/git_commit_and_push.py` now inspects the cached git index before staging allowed paths. If any pre-staged path falls outside the existing allowed auto-git paths, the helper returns `blocked_disallowed_staged_changes` with the offending paths and does not run `git add` or `git commit`.

The helper also uses cached path lists after staging to decide whether allowed changes exist, instead of relying only on `git diff --cached --quiet`.

## Validation

Focused validation:

```bash
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_git_commit_and_push.py
```

Result: 4 passed.

Broader worker validation:

```bash
apps/worker-python/.venv/bin/python -m pytest -q
```

Result: 203 passed.

## Guardrail

This is an operational safety fix. It does not affect historical ranking behavior, strategy selection, or any claim about predictive ability.
