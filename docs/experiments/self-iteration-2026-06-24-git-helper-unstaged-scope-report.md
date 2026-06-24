# Self-Iteration Report: Git Helper Unstaged Scope Guard

Date: 2026-06-24

## Primary Goal

Prevent the auto-git helper from committing allowed generated evidence while unrelated unstaged source or user changes are present in the same working tree.

## Non-Goals

- No training, scoring, backtest, candidate-generation, or prediction logic changes.
- No generated `data/output` or `runtime` artifacts are promoted.
- No change to DEHPS evidence level, prediction claims, or betting language.

## Change

`apps/worker-python/scripts/git_commit_and_push.py` now parses NUL-delimited `git status --porcelain -z` paths before staging allowed paths. If any changed path falls outside the existing allowed auto-git scope, and it was not already caught as a disallowed staged path, the helper returns `blocked_disallowed_worktree_changes` and skips `git add`, `git commit`, and `git push`.

This closes the gap where an automated data/report commit could proceed while unrelated unstaged source changes remained in the worktree.

## Validation

Focused validation:

```bash
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_git_commit_and_push.py
```

Result: 7 passed.

Broader worker validation:

```bash
apps/worker-python/.venv/bin/python -m pytest -q
```

Result: 217 passed.

## Guardrail

This is an operational safety fix only. It does not alter historical ranking behavior, strategy selection, candidate scoring, or any claim about predictive ability.
