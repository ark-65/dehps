# Isolated Historical Research Lane — 2026-07-13

## Round goal

Separate bounded historical research from the continuous, forward-evidence main supervisor. The change must keep the three public prediction lines (`static_100`, `dynamic_kdj`, and `dynamic_kdj_near`) frozen while there is an unobserved prediction issue, while still permitting fixed and reviewable historical diagnostics.

## Non-goals

- No new prediction algorithm, score, or selection rule.
- No promotion based on historical results.
- No mutation of `training_next_candidates_current` or the main supervisor's candidate/selection state.
- No claim that an isolated historical result predicts future draws.

## Gauss–Riemann cross-review

These are historically inspired reasoning lenses, not literal reconstructions.

### Gauss pass: verification

- The observed forward ledger has one paired issue and a completed three-line snapshot for `2026080`; it does not yet have a new independent label.
- Repeating adaptive search on that fixed history changes the number of tested hypotheses, but not the independent sample size. It therefore cannot establish additional forward evidence.
- The research lane uses a fixed suite version and records the exact as-of issue and history fingerprint. A completed suite is skipped unless either changes.
- It invokes only read-only historical scripts, writes under `data/output/optimization/research-lane`, and is prohibited by tests from invoking `run_training_supervisor.py` or candidate generation.

### Riemann pass: structure

The prior system treated two different spaces as one process: (1) operational prediction state, which advances only when a new draw is observed; and (2) bounded diagnostic state, which may analyze a fixed historical surface. The new lane makes that boundary explicit through separate lifecycle, lock, output namespace, and manifest.

### Cross-review and disagreement

- Shared conclusion: fixed research can run independently, but cannot feed selection or promotion without the usual frozen and forward gates.
- Remaining risk: the initial suite is historical and finite; it must not be expanded adaptively merely to keep hardware busy.
- Required verification: confirm a completed live suite leaves the three current prediction snapshots and supervisor lifecycle unchanged.

## Implementation

- Added `scripts/run_isolated_research_lane.py`.
  - fixed suite: dynamic KDJ frozen backtest plus KDJ advisor frozen controls;
  - non-blocking process lock;
  - manifest deduplication by suite version, as-of issue, and history fingerprint;
  - generated artifacts isolated from main optimization outputs;
  - explicit `selection_changed=false`, `promotion_allowed=false`, and `main_candidate_write_allowed=false` metadata.
- Updated `scripts/ensure_training_supervisor.sh` so a parked forward supervisor launches the isolated lane, while an active main supervisor never does.

## Validation

- Focused tests: isolated-lane policy, watchdog contract, training-watch and forward-wait guard.
- Shell syntax and Python bytecode checks.
- Live suite: launched against `2026079`; results are recorded only after completion under the research-lane runtime directory.
- Watchdog integration: with the main supervisor parked, the watchdog re-synced `2026079` without changes, accepted a zero-item forward-evaluation batch, detected the existing research process, and did not launch a duplicate or restart the main supervisor.

## Acceptance condition

The main supervisor remains `waiting_for_forward_issue` and its three `2026080` snapshots remain intact. The research manifest must report `completed`, then a repeated watchdog invocation with unchanged history must skip rather than repeat the suite.
