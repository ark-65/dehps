# Ranking Contract Provenance

## Purpose

DEHPS treats candidate scoring and TopK selection as separate evidence contracts. A score can be unchanged while a tie at the export boundary changes candidate identity. Every new prediction and every derived evaluation therefore records the ranking contract that selected its candidate set.

## Official values

- `legacy_score_partition`: historical score-only `argpartition`; equal-score boundary membership was not stable by lexicographic candidate id.
- `strict_v1`: score greater is better; when scores are equal, the smaller lexicographic candidate id is better.

The Python authority is `dehps.ranking_contract.RankingContract`. The API uses one matching parser in `apps/api/src/ranking-contract.ts`.

## Compatibility rule

Stored null or blank values resolve to `legacy_score_partition`. Unknown non-empty values fail closed. Compatibility is applied on reads; the migration does not update old rows, candidates, fingerprints, timestamps, or evidence documents.

The nullable database boundary is intentional:

- old rows may remain null forever;
- new formal prediction runs must explicitly provide `strict_v1`;
- the application rejects missing contracts and rejects new formal legacy runs;
- the historical current-snapshot bridge is the only path allowed to persist an explicitly labelled legacy run.

## Identity

New forward runs carry a `prediction_fingerprint` using `forward-prediction-fingerprint-v1`. Its payload covers:

- as-of issue, history fingerprint, and snapshot key;
- model config hash and normalized config;
- candidate algorithm/protocol;
- scoring contract;
- ranking contract;
- source Git commit.

The fingerprint is unique when non-null. Existing run keys, config hashes, and fingerprints are not recalculated.

Research task identities include `ranking_contract` only when the task produces rankings or TopK selections. Fixed diagnostics and the analytic null summary omit it. Walk-forward, weight-grid, feature ablation, dynamic KDJ, and stochastic ranking controls include `strict_v1`.

## Evidence propagation

The normalized contract travels with:

- durable prediction reads and the latest-prediction CLI/JSON summary;
- current candidate API responses;
- forward evaluation claims and persisted evaluation results;
- JSON and Markdown evaluation artifacts;
- actual-combination ranking audits;
- watchdog forward-evidence snapshots and wait summaries;
- forward-promotion comparison rows;
- isolated research manifests and reports;
- scoring-kernel telemetry;
- shadow comparison reports.

Evaluation stores `prediction_ranking_contract` per prediction run. Promotion fails closed when paired runs use different ranking contracts.

## Difference classification

Shadow comparison uses this order:

1. score mismatch: `score regression`;
2. candidate-id mismatch with different contracts and equal scores: `ranking-contract difference`;
3. candidate-id mismatch under one contract: `candidate identity regression`;
4. no mismatch: `exact`.

This prevents the known legacy/strict tie-boundary difference from being presented as a scoring-model regression.

## Migration and rollback

`python -m scripts.migrate_ranking_contract_provenance` creates only nullable provenance columns and a partial unique fingerprint index. It performs no historical `UPDATE`.

Rollback is application-level: revert the readers/writers and leave the nullable columns unused. Since no old evidence is rewritten, rollback does not require reconstructing historical state.
