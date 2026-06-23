# Self-Iteration: Git Helper Current Branch Push

## Goal

Make the auto-git helper's default push target match the operational rule that self-iteration changes should push to the current branch's corresponding `origin` branch, not implicitly to `main`.

## Non-Goals

- No strategy, scoring, backtest, or training behavior changes.
- No generated runtime or data artifacts were added.

## Change

- `git_commit_and_push(..., push=True)` now resolves the push branch only when pushing.
- If `--branch` is provided, the helper still uses that explicit branch.
- Without `--branch`, the helper prefers the current branch's `origin/...` upstream and falls back to the current local branch name.
- Pushes use `HEAD:<branch>` so the committed self-iteration change is pushed even when the local branch name differs from its upstream branch name.

## Validation

```bash
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_git_commit_and_push.py
```

Expected result: focused git-helper regression tests pass.

Actual result:

```text
6 passed in 0.02s
```

Additional worker regression:

```bash
apps/worker-python/.venv/bin/python -m pytest -q
```

```text
205 passed in 20.17s
```

## Evidence Level

Operational guardrail. This reduces an automation footgun and does not change DEHPS scientific scoring or predictive claims.
