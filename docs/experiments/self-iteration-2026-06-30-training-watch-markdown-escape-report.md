# Self-Iteration: Training Watch Markdown Escaping

- Date: 2026-06-30
- Primary goal: keep training watch Markdown structurally readable when runtime text contains Markdown delimiters or line breaks.
- Non-goals: no strategy, advisor, scoring, candidate generation, database, or prediction behavior changes.

## Change

`scripts/watch_training_progress.py` now normalizes inline Markdown text emitted in the training watch report. Table and list fields collapse embedded line breaks, escape Markdown table pipes, and render inline code fields with a backtick fence long enough for unusual run ids or actions.

## Rationale

Training watch output is operational evidence. If a run id, phase, advisor key, selected field, or note contains a newline or `|`, the report should stay reviewable instead of silently breaking list or table structure. This improves observability without changing any training decision logic or making predictive claims.

## Validation

- `apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests/test_training_watch.py -q` passed, 11 tests.
- `apps/worker-python/.venv/bin/python -m pytest -q` passed, 312 tests.
