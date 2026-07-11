# Training Watch Prediction-Input Boundary Audit — 2026-07-11

## Primary Goal

Make the existing draw-outcome input boundary directly auditable from the training watcher so long-running self-iteration cannot mistake published sales, jackpot, prize-tier winner counts, or other market aggregates for ticket-level number-selection evidence.

## Non-Goals

- No new model, advisor, feature, scoring rule, source budget, or promotion threshold.
- No claim that aggregate prize counts identify individual ticket choices or population combination popularity.
- No supervisor restart while the current run is durably parked for the next unseen issue.
- No automatic promotion or release of historical holdout quarantine.

## Change

The watcher now:

- reads `prediction_input_boundary` from the authoritative supervisor status file;
- independently checks the protocol, exact draw-training field list, absence of selected market aggregates, absence of ticket-distribution observations, separate observation-only market role, zero draw-probability effect, unchanged selection, and disabled promotion;
- marks missing records as `missing` and contradictory records as `invalid` with a stop-and-fix action;
- exposes the normalized result at the watcher top level, operator summary, Markdown report, and leakage-check summary.

The independent watcher check is intentional: a supervisor record that merely claims `passed` is insufficient when its fields contradict the boundary.

## Validation

Targeted watcher suite:

```text
86 passed in 2.32s
```

Full worker suite:

```text
552 passed in 20.02s
```

Live watcher against run `20260711-132111`:

```json
{
  "action": "await_new_forward_issue",
  "status": "passed",
  "source_status": "passed",
  "watcher_invariants_passed": true,
  "training_fields": ["issue", "draw_date", "red_numbers"],
  "market_selected": [],
  "ticket_distribution_observed": false,
  "identifiability": "aggregate_prize_counts_do_not_identify_ticket_level_number_selection",
  "draw_probability_effect": "none",
  "promotion_allowed": false,
  "leakage_status": "passed",
  "leakage_invariants": true
}
```

## Operational State

- Supervisor run `20260711-132111` remains `waiting_for_forward_issue`.
- Pending complete three-line snapshot: issue `2026079`, 10,000 candidates per line.
- Forward evidence: `0/20`; review-only and not promotion-eligible.
- Advisor freshness: current, with no missing or stale enabled advisor.
- Same-history training remains parked; restarting would add sequential search multiplicity without new evidence.

## Interpretation

Published prize-tier counts are low-dimensional aggregates conditioned on the realized draw. They do not reveal the high-dimensional distribution of combinations purchased by individual bettors, and multiple incompatible ticket distributions can produce the same published counts. Such fields may remain in a separate observation or audit surface, but they cannot enter draw-probability scoring, candidate ranking, advisors, search-base selection, or promotion without a separately identified and predeclared data source.
