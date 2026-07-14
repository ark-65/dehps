# Round 28 - Autonomous Pattern Discovery and Strategy Synthesis

Status: implemented, pending human acceptance.

## Goal

Allow DEHPS to autonomously discover interpretable historical patterns, screen them against formal nulls, synthesize declarative feature/strategy contracts, and submit a Research Proposal Request without changing production code, training, rankers, objectives, or the Registry.

## Implemented

- Added `apps/worker-python/dehps/pattern_discovery/`.
- Added a machine-readable pattern catalog with more than 30 pattern types.
- Added AP detection for 6/5/4/3-term arithmetic progressions with explicit start and difference.
- Added legal-universe and matched-null comparison.
- Added significance review with adjusted p-values, CI, effect size, multiplicity count, and non-interpretable blockers.
- Added novelty detection for formula duplicates, renamed/reparameterized duplicates, and rejected-family retries.
- Added declarative feature synthesis and allow-listed strategy synthesis.
- Added pattern memory tables for discovered patterns, observations, validations, features, strategies, and cycles.
- Added scheduler actions for pattern discovery sequencing.
- Added `dehps pattern ...` CLI commands.
- Added read-only API under `/pattern-discovery`.
- Updated architecture docs and roadmap.

## Non-goals preserved

- No production training changes.
- No Objective, Candidate Source, Promotion Gate, or ranker changes.
- No arbitrary code generation from patterns.
- No Registry update from pattern discovery.
- No automatic commit, PR, merge, or deployment from runtime pattern discovery.
- No profit or single-draw hit claims.

## Validation

Targeted worker tests:

```bash
cd apps/worker-python
.venv/bin/python -m pytest -q \
  tests/test_pattern_models.py \
  tests/test_pattern_catalog.py \
  tests/test_arithmetic_progression_extractor.py \
  tests/test_pattern_null_comparison.py \
  tests/test_pattern_significance.py \
  tests/test_pattern_multiplicity.py \
  tests/test_pattern_novelty.py \
  tests/test_feature_synthesis.py \
  tests/test_strategy_synthesis.py \
  tests/test_pattern_budget.py \
  tests/test_pattern_lifecycle.py \
  tests/test_pattern_scheduler.py \
  tests/test_pattern_cli.py
```

Result: `21 passed`.

Targeted API tests:

```bash
cd apps/api
npm test -- pattern-discovery
```

Result: `102 passed`.

Full worker:

```bash
cd apps/worker-python
.venv/bin/python -m pytest -q
```

Result: `900 passed`.

Disconnected database mode:

```bash
cd apps/worker-python
DB_PORT=1 .venv/bin/python -m pytest -q
```

Result: `900 passed`.

API:

```bash
cd apps/api
npm test
npm run build
```

Result: `102 passed`; TypeScript build passed.

Isolated smoke:

```bash
DB_NAME=dehps_round28_smoke dehps pattern cycle --persist --submit --requested-by research:round28-smoke
```

Smoke result:

- history rows copied into smoke DB: `3476`
- discovered patterns: `83`
- pattern observations: `5733`
- validations: `83`
- synthesized features: `50`
- synthesized strategies: `30`
- pattern search cycles: `1`
- submitted Research Proposal Requests: `1`
- submitted request key: `research-proposal-pattern-440767addb399de1`
- production database check: `discovered_patterns` remained absent in production DB

## Notes

Pattern strategies are research candidates only. They are not production strategies and cannot replace frozen validation, Evidence, Decision, Reviewer approval, or the existing Promotion Gate.
