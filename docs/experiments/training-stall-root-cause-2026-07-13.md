# Training Stall Root-Cause Dossier — 2026-07-13

## Task frame

The continuous supervisor reached 137 same-history stagnation rounds while all three prediction lines had a complete frozen snapshot for `2026080`. The goal of this round is to turn a parked state into an auditable diagnosis and bounded recovery plan, not to claim that another historical search is model improvement.

## Historical boundary

The Gauss and Riemann passages below are historically inspired reasoning lenses, not literal reconstructions or authority for a predictive claim.

## Gauss pass: verification

- Legal ranked universe: 1,105,506 combinations from a legal universe of 1,107,568.
- Data boundary passed: outcome inputs are issue/date/red numbers; ticket-level number selection is not observed and prize aggregates remain excluded from draw-probability training.
- Forward evidence is 1 paired issue out of 20 required for review. `2026080` is a complete frozen three-line snapshot but remains unobserved.
- The latest five rounds repeat one configuration hash and one complete metric signature; current-run stagnation is 137 rounds and the adaptive familywise hypothesis count is 8,163.
- Dynamic KDJ's isolated 100-target frozen audit failed: static objective 4147.179414, dynamic objective 1557.61588, null objective -0.790322. It did not beat static or null, had worse tail risk, and exceeded offset-coverage limits. Leakage and negative controls passed, so the rejection is evidence about the model source rather than a parser or leakage failure.
- OpenCL GPU probing is not eligible: end-to-end speedup 0.851318 with nine rounded score-cell differences. CPU remains the deterministic backend (16 configured workers on 22 logical CPUs).

## Riemann pass: structure

The failure was previously represented as a single operational state: “wait for a forward issue.” It actually has distinct spaces:

1. forward evidence, which moves only when an unseen draw is synced;
2. search geometry, which can collapse into repeated configurations;
3. model-source quality, which can fail a frozen audit independently of the search;
4. compute equivalence, where a faster-looking accelerator is unusable if it changes rank inputs; and
5. data identifiability, which must stay separate from market aggregate observations.

The read-only stall dossier makes these spaces visible rather than allowing a parked supervisor to hide the cause.

## Cross-review

- Gauss challenge: no diagnostic may change selection, promotion, candidates, or the legal sample space.
- Riemann challenge: a single `await_new_forward_issue` label hides materially different recovery actions.
- Shared conclusion: halt same-history adaptive search; retain frozen candidate evaluation; treat dynamic KDJ as research-only; keep GPU disabled; and continue data/leakage checks.

## Implementation

- Added `scripts/diagnose_training_stall.py` with versioned JSON/Markdown artifacts and a state fingerprint so unchanged diagnoses are not rewritten.
- Dimensions: forward evidence, search geometry, dynamic KDJ frozen audit, compute equivalence, and data/leakage boundary.
- The watchdog runs the dossier while the main supervisor is parked.
- The research-lane launcher now compares the as-of issue and history fingerprint before starting. This prevents repeated process launches after a completed audit, while still re-running after a corrected historical record.

## Validation

- Focused diagnostic, isolated-lane, watchdog-contract, forward-wait, and training-watch tests.
- Shell syntax and Python bytecode checks.
- Live watchdog run with a parked supervisor: it reported an unchanged diagnosis, skipped the completed research lane for unchanged history, and left main training parked.

## Next verification

When `2026080` is synced, evaluate the existing snapshot before allowing a fresh main supervisor. Any future dynamic-KDJ proposal must first pass a newly preregistered frozen static/null/tail-risk audit; it must not be advanced solely because it changed historical ranks.
