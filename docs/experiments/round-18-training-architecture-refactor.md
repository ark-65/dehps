# Round 18 - Training Architecture Refactor

## Goal

Mechanically separate training runtime responsibilities without changing features, formulas, search shares, advisors, baselines, walk-forward protocol, config hash semantics, or promotion thresholds.

## Non-goals

- No new prediction feature, model, algorithm, strategy, or weight.
- No front-end work or PostgreSQL Store rewrite.
- No bug fix disguised as refactoring.
- Hypothesis Registry is design-only in this round.

## Before

`scripts/run_training_supervisor.py` was approximately 8,600 lines and combined CLI parsing, search constants, objective arithmetic, advisor calls, evaluation, promotion, persistence, events, multiprocessing, reporting, and lifecycle control.

## After

- The executable entry is 13 lines and delegates to `training.cli`.
- `rank_objective_v1` is immutable, canonical-JSON serialized, and SHA-256 identified.
- Search fields, phases, budgets, and rank homogeneity are independent policies.
- Evaluation facts and promotion decisions use different types.
- Weight, Ridge, and Neural KDJ proposals enter a common Advisor Registry with source/protocol metadata.
- `TrainingRoundRunner` has injected repository, search, advisor, evaluator, promotion, artifact, and event boundaries.
- The established algorithm implementation lives in `dehps.training.runtime` while its final production-loop connection to `TrainingRoundRunner` remains an acceptance item.

## Behavior Locked

Characterization tests freeze exact objective components, budget rounding, early/mid/late/stagnation phases, rank homogeneity, frozen promotion/quarantine, run key, config hash, deterministic seed, and candidate order. Float assertions use explicit tolerances.

## Commits

```text
55d9555 test: characterize training architecture behavior
9725a85 refactor: extract versioned objective policy
daaeaeb refactor: extract search phase and candidate budget policies
5dd7e12 refactor: separate evaluation facts from promotion
c1fd21d refactor: add advisor registry adapters
5578b33 refactor: introduce training round runner
a49e33e refactor: reduce training supervisor entry to orchestration
0b1367f refactor: add bounded supervisor smoke lifecycle
```

## Validation

Baseline before extraction:

```text
.venv/bin/python -m pytest -q
658 passed in 20.90s
```

Latest full run before documentation:

```text
.venv/bin/python -m pytest -q
685 passed in 20.91s
```

Final full suite after the bounded smoke lifecycle and structured promotion report:

```text
.venv/bin/python -m pytest -q
685 passed in 21.59s
```

Isolated Supervisor validation used database `dehps_round18_smoke`, copied only the 3,476 history rows and 1,107,568 legal combinations, and wrote ignored output under `data/output/round18-smoke`:

```text
DB_NAME=dehps_round18_smoke .venv/bin/python scripts/run_training_supervisor.py \
  --max-rounds 1 --duration-hours 0 --train-mode expanding \
  --history-scope full_history_audit --train-window 20 --eval-window 2 \
  --top-n 10000 --as-of-issue 2026079 --workers 1 \
  --max-configs-per-round 1 --memory-budget-gb 20 \
  --disable-target-weight-inversion-advisor \
  --output-dir data/output/round18-smoke \
  --event-url http://127.0.0.1:3000/training-events/status
```

Evidence:

- Runs `20260713-115118` and `20260713-115303` each completed exactly one round with no traceback or runtime failure.
- Objective policy was `rank_objective_v1` with hash `c63399d633aa1ae0148df96698df77233458ccbb265db50ed959907bce726387` in result, report, and database columns.
- The second run restored the isolated incumbent and rejected promotion with `objective_not_higher`, `primary_hit_not_higher`, and `missing_forward_evidence`.
- Search/frozen issue overlap was zero; the report contained no new leakage warning.
- `source_survival` recorded every configured source and `advisor_registry` recorded its protocol and candidate count.
- Event publication produced no `training_event_warning`; the local API endpoint was live and accepted POST with HTTP 201.
- Production database queries returned zero rows for both smoke run ids in `training_round_results` and `training_next_candidates_current`, so the frozen production line was unchanged.
- Tiny two-target validation cannot train the dynamic/near-dynamic KDJ lines; those paths emitted bounded warning payloads and refused static fallback as designed. The completed static round and promotion evidence remained valid.

## Known Risks And Remaining Acceptance Work

- The production loop in `dehps.training.runtime` still needs to invoke `TrainingRoundRunner`; existence and unit coverage alone do not prove the requested runtime boundary.
- Ready PR, auto-merge, post-merge restart, new run id, and 1-2 observed live rounds remain pending.

## Next Work

Finish the production runner connection, run the full suite, execute an isolated one-round smoke, then publish the reviewable branch. Round 19 should implement the Hypothesis Registry data model; the following round should enforce Research/Engineering Agent authority separation.
