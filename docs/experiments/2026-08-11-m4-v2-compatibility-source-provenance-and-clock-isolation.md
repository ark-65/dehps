# M4-v2 compatibility: source provenance and clock isolation

Date: 2026-08-11

Primary goal: remove environment-dependent compatibility failures without
changing production prediction, retirement, scheduling, or routing semantics.

The predictive-route historical audit now reads ordinary `100644` blobs from
the pinned Git object database with `GIT_NO_REPLACE_OBJECTS=1`. It validates the
frozen v1 source anchor and its per-file digests independently of current
worktree bytes. The audit API is not called by production or control-plane
paths and has no fallback to live files, replacement objects, aliases, latest
lookups, or filesystem history.

Prediction compatibility tests use explicit, non-autouse, per-file fixtures to
isolate the legacy-retirement activation path. They do not mutate global time,
sleep, skip, xfail, delete assertions, or relax completion classification and
route distinctions. The legacy topology remains a historical compatibility
surface; this round does not reactivate it or alter the active predictor.

No Supervisor, workload, replay, P3/P4, Promotion, production action, runtime
publication, or scientific result read occurred. Validation is limited to
static/focused/full Worker tests under Engineering Request 513.

MAINLINE INTEGRATION: **NO — INTEGRATION_PENDING**.

