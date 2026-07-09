# Self-Iteration Report: Watch Navigation Candidate Presence

- Date: 2026-07-09
- Branch: `fix/self-iterate-20260709-1002-watch-nav-source`
- Primary goal: make the training watch machine summary explicit when no experimental navigation candidate is present.
- Non-goals: no model changes, no advisor changes, no candidate-source changes, no supervisor restart logic changes, and no predictive or betting claim.

## Context

The active supervisor run `20260709-093003` was readable through `watch_training_progress.py --limit 5`. The watch status was `ok` with action `continue_current_run`, while the experimental navigation summary used an empty `source` alongside `reason=no_experimental_navigation_candidate`.

## Change

`apps/worker-python/scripts/watch_training_progress.py` now emits `candidate_present` for `experimental_navigation_candidate` summaries. The field is computed from source/config-hash/search-base evidence or an explicit eligible flag. Restart readiness context and the CLI/operator summary preserve the same field so automation can distinguish "no candidate" from "candidate present but ineligible" without inferring from an empty string.

## Validation

- `apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_training_watch.py`
- `apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5`
- `git diff --check`

Live watch validation produced `candidate_present: false` for the current no-candidate state and kept severity `ok` with action `continue_current_run`.

## Evidence Boundary

This is an operational observability fix only. It does not modify the SSQ legal sample space, historical window, baseline/null model, leakage checks, scoring weights, candidate generation, or betting-oriented behavior.
