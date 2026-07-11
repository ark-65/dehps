# Training Forward Evidence Ledger V1

## Primary Goal

Make genuinely forward, post-isolation prediction evidence visible and auditable in the training watch and hourly self-iteration loop.

## Non-Goals

- Do not add a model, advisor, candidate source, weight, or search heuristic.
- Do not change the live supervisor or its training budget.
- Do not use historical frozen-holdout results as forward evidence.
- Do not automatically promote a model or release the historical holdout quarantine.

## Task Frame

The current training loop can continue computing while historical round metrics repeat. The system already freezes three next-issue snapshots and evaluates them after draw sync, but the main watch did not count this evidence. The smallest safe change is an evidence ledger, not another search mutation.

Success means the watch:

1. finds the fixed first activation boundary of `search_slice_frozen_promotion_v1`;
2. excludes evaluations at or before that boundary;
3. counts an issue only when `static_100`, `dynamic_kdj`, and `dynamic_kdj_near` are all evaluated with `as_of_issue < predicted_issue` and leakage checks passing;
4. exposes pending snapshots without counting them as evaluated evidence;
5. fails closed on leakage, duplicate line/issue rows, incomplete evaluated triples, or database-read errors;
6. treats 20 paired issues as a human-review threshold only.

## Historical Boundary

- Isolation protocol: `search_slice_frozen_promotion_v1`
- Fixed activation boundary found from the earliest persisted protocol record: after issue `2026078`
- Search/frozen historical split: `80/20`
- Historical overlap: `0`
- Frozen role: `promotion_only`
- Historical frozen results remain quarantined.

## Gauss Pass

- Legal red-ball sample space is fixed at `C(33,6) = 1,107,568`.
- Exact-hit null expectation is reported as `paired_issues * top_n / 1,107,568` for Top100, Top1000, and Top10000.
- No red5 null is invented; it is explicitly `not_estimated` because the hit geometry needs a separate combinatorial derivation.
- Each prediction issue is a single independent accounting unit. Multiple lines for the same issue are paired comparisons, not three independent draws.
- Protocol-era proof obligation is explicit: `predicted_issue > 2026078`, `as_of_issue >= 2026078`, `as_of_issue < predicted_issue`, status `evaluated`, and persisted `leakage_passed=true`.
- Duplicate line/issue evaluation rows and incomplete evaluated triples invalidate the ledger instead of being silently selected or averaged.

## Riemann Pass

- The three lines are treated as a common issue-indexed fiber: comparisons are only meaningful when all lines sit over the same unseen draw.
- Pending snapshots and completed evaluations are different states; continuity between them is not assumed.
- Historical optimization rounds and forward draws occupy different evidence spaces. A plateau in the former cannot be repaired by relabeling it as success in the latter.
- The ledger retains the issue structure and per-line totals, avoiding a scalar score that could hide line collapse or missing observations.

## Cross-Review

The exact accounting view and the structural pairing view agree that post-isolation, issue-paired evidence is the smallest defensible unit. They also agree that more compute, a looser frozen gate, or a new heuristic would not answer whether the current model generalizes forward.

## Disagreement

There is no mathematical basis yet for choosing 20 issues as a power-complete promotion threshold. It is a predeclared operational checkpoint that limits repeated peeking. Gauss therefore treats it as insufficient for automatic promotion; Riemann treats it as enough to inspect whether the line relationships remain stable. The implementation adopts the smaller shared conclusion: human review only.

## Synthesis

The watcher and hourly self-iteration prompt now require a paired forward-evidence ledger. Reaching 20 paired issues sets `review_ready=true`, while `promotion_eligible=false` and `automatic_quarantine_release=false` remain invariant. Any later promotion rule requires a separate, reviewed experiment with a null/baseline comparison and explicit failure criteria.

## Live Validation

Run `20260711-020627` was observed while the unchanged supervisor remained active:

- fixed activation boundary: `2026078`;
- pre-activation evaluations excluded: `3` (all three lines for predicted issue `2026078`);
- paired post-activation issues: `0/20`;
- pending issue: `2026079`, with all three line snapshots present and `10,000` candidates per line;
- ledger status: `not_started`;
- review ready: `false`;
- promotion eligible: `false`;
- automatic quarantine release: `false`;
- parser/sync/duplicate checks: passed;
- current supervisor PID: `2868765`, still active during validation.

The first live watch showed six durable rounds and a seventh target-complete round awaiting its database/report flush. A later database check observed nine durable rounds with the same isolation protocol, zero overlap, and `search_uses_frozen_validation=false`. Historical round repetition remained active; this change does not misrepresent that plateau as model improvement.

## Validation

```text
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_training_watch.py
68 passed

cd apps/worker-python && .venv/bin/python -m pytest -q
479 passed

apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py \
  --run-id 20260711-020627 --limit 12 --output-dir /tmp/dehps-forward-watch
live ledger matched the values above without runtime errors
```

## Next Verification

After issue `2026079` is synced, verify that exactly one paired issue appears, all three line evaluations share the same predicted issue, leakage remains passed, and the dynamic-minus-static deltas equal the persisted line hit flags. Continue this check until 20 independent paired issues exist; then open a human review without changing quarantine automatically.
