# Legacy Prediction Line Retirement + Prediction v2 Shadow Initialization

Date: 2026-08-01
Engineering Request: `engineering-prediction-v2-shadow-initialization-20260801`
Execution role: Engineering Agent
Source state: `CODE_COMPLETE` pending review/merge
Capability state: `INTEGRATION_PENDING`
Evidence Progress: `0`
Promotion Gate: `CLOSED`

## Primary goal

Freeze `static_100`, `dynamic_kdj`, and `dynamic_kdj_near` as preserved legacy baselines and initialize a deterministic Prediction v2 shadow lane without changing M4, reading P2.6.1 statistical results, creating Historical Evidence, or performing a live scheduler/service cutover.

## Implemented source boundary

- Added immutable source contracts for `LegacyPredictionBaselineManifest.v1`, `PredictionV2ShadowContract.v1`, and `PredictionV2SchedulerCutoverPlan.v1`.
- Added a fail-closed activation contract. No source guard changes behavior until a later typed Operator Request publishes a digest-bound activation artifact.
- Added legacy guards for training, KDJ/three-line refresh, forward evaluation, legacy pre-draw mail, and legacy post-draw report compilation/delivery.
- Kept draw synchronization independent. After a valid activation, draw ingestion continues while old evaluation, old reporting, old shadow attestation, and legacy training resume side effects are skipped.
- Added the `dehps.prediction.v2` package with prior-only 30/60/120 state encoding, expert protocols, a forced null route, deterministic 10,000-candidate legal pool, deterministic Top100, diversity diagnostics, immutable pre/post reports, and physical replay.
- Marginal and Temporal experts emit `NOT_AUTHORIZED`; Diversity is `OBSERVATION_ONLY`; selection is forced to `BASELINE_ONLY`.
- Added the isolated `prediction-v2-shadow` Goal/Task DAG and unified Supervisor capabilities for a synthetic reference execution followed by physical replay. The M4 control-plane manifest and M4 status path are not reused.
- Added `--run-once` and `--task-key` to the canonical unified Supervisor entrypoint. No competing completion path was introduced.

## Statistical and interpretation boundary

The emitted Top100 is a deterministic legal-null ordering used to validate pipeline identity and replay. It does not use a signal-bearing expert and does not claim predictive advantage. Every shadow artifact carries:

```text
shadow_only = true
route = BASELINE_ONLY
HistoricalEvidence = NOT_RUN
Evidence Progress delta = 0
promotion_gate_opened = false
```

The reference draw history is a deterministic legal synthetic fixture. It is not a historical measurement and cannot authorize model selection, production replacement, betting advice, P3, or Promotion Gate changes.

## Legacy preservation and cutover boundary

No database row, model artifact, config, weight, prediction history, report history, benchmark artifact, or delivery ledger is deleted or rewritten. The source cutover plan is `DRY_RUN_ONLY`.

This Engineering execution did not:

- stop or restart a service;
- edit cron or systemd state;
- import a live control-plane manifest;
- publish the retirement activation fact;
- send email;
- write prediction/evaluation database rows;
- operate the resident M4 Supervisor;
- read P2.6.1 statistical results.

Consequently, future legacy scheduled entrypoints remain unchanged until a separately approved Operator Request performs the bound cutover. This is intentional: source readiness is not production retirement.

## Validation

Focused Prediction v2 suite:

```text
11 passed
```

Impacted regression suite covering draw sync, forward evaluation, legacy candidate refresh, pre/post mail, training CLI, and unified Supervisor:

```text
97 passed
```

Complete Worker suite in the restricted sandbox:

```text
1944 passed, 6 skipped
1 environment-limited test failed in the restricted sandbox because the
multiprocessing forkserver could not bind its Unix socket (EPERM).
```

The single environment-limited test was rerun unchanged outside the restricted socket sandbox:

```text
1 passed
```

No assertion failure or Prediction v2 regression remained.

The complete Worker suite was then run in the multiprocessing-capable test environment:

```text
1947 passed, 4 skipped, 4 existing Python 3.14 fork deprecation warnings
```

The suite verifies legal sample-space invariants, no duplicates, target/history/contract seed drift, expert non-use, report time boundaries, artifact tamper rejection, activation fail-closed behavior, continued draw ingestion, scheduler dry-run non-mutation, separate status paths, zero Evidence Progress, closed Promotion Gate, and physical Supervisor replay.

## Mainline integration matrix

| Link | Source implemented | Live validated |
| --- | --- | --- |
| Goal | Yes | No |
| Resolver | Yes | No |
| Ready Queue | Yes | No |
| Unified Supervisor capability | Yes | No |
| Immutable artifacts | Yes, synthetic reference test | No live artifact |
| Status projection | Yes, isolated source/test | No live projection |
| Next consumer | Yes, typed Operator boundary | Not authorized |
| Physical replay | Yes, synthetic reference test | No live replay |
| Legacy scheduler cutover | Dry-run only | Not executed |

Final integration answer:

> **NO — INTEGRATION_PENDING.**

The capability may advance only after merge and a separate typed Operator Request bound to the merged commit, contract digests, clean live state, and explicit cutover boundary. Until then, Prediction v2 remains shadow-only and the activation fact remains unpublished.
