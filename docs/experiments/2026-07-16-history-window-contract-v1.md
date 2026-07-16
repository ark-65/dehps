# History Snapshot + Window Contract v1 acceptance

## Round contract

- Primary goal: freeze the existing history identity and rolling/expanding window semantics behind executable contracts.
- Source baseline: `4a0fcf2` on `main`.
- Added contracts: `history_snapshot.v1.0.0` and `window.v1.0.0`.
- Added ABI boundary: `dehps.window-stage-abi.v1`.
- Non-goals: Candidate/Feature/Evaluation contracts, feature or score changes, model or weight changes, ranking work, GPU/SIMD, database migration, historical backfill, and production integration.

## Root cause

DEHPS already froze scoring and ranking output but still allowed history and window meaning to be reconstructed from Python list slices. The same `window=100` could not independently prove its source-history revision, cutoff inclusion rule, target leakage boundary, ordering, or selected-row identity. A backend mismatch could therefore be blamed on compute code when the real difference was an upstream input interpretation.

## Implementation

- Added a minimal Contract Runtime with canonical JSON, domain-separated SHA-256, immutable `ContractRef`, explicit `ContractRequirement`, and structured fail-closed compatibility errors.
- Separated semantic identity (`normative_digest`) from executable conformance evidence (`golden_suite_digest`). SemVer is recorded but never treated as implicit compatibility.
- Added canonical `HistoryRecord` and `HistorySnapshotArtifact` values covering issue, draw date, and red numbers.
- Added `WindowSpec`, `WindowArtifact`, and `WindowStageEnvelope` with rolling/expanding, include/exclude-as-of, minimum-history, and target-leakage rules.
- Added Merkle-style parent/payload/artifact digests and tamper checks.
- Added `HistorySnapshotManager.contract_current()` as an opt-in read path. The legacy `current()` implementation and fingerprint are unchanged.
- Added a read-only `scripts.audit_input_contract` command.
- Added executable fixed-output golden suites for snapshot and window behavior.

## Current live evidence

The audit command was run against PostgreSQL without writes:

```text
history contract: history_snapshot.v1.0.0
history snapshot: history_snapshot.v1-2026080-4b3293e50e6eb9d7
history digest: 4b3293e50e6eb9d7789b609f1207130557a0423bb6a790d591b9a1427aea8e51
history range: 2003001..2026080
history draw count: 3477

window contract: window.v1.0.0
mode/size: rolling / 100
as-of/include: 2026080 / true
target: 2026081
selected range: 2025132..2026080
selected draw count: 100
window artifact: 0bbd5a138e27dc2bee9f68558abb6184c33c81cf02fe0e4739026767cbb23fe4
```

The selected latest issue is strictly earlier than the target, so the leakage guard passes.

## Production-state invariant

Before validation:

```text
history rows: 3477, latest issue: 2026080
forward prediction runs: 3 pending
forward candidates: 30000
forward evaluation runs: 0
run-row sha256: 9205765b823d67f11de1b356078461e687de667473b959d35fed4b3960215011
candidate-row sha256: 0d049313927d238b304e1790fc2f0e87f4f239b1407a0fa91cfa923b7c0137d5
```

The same deterministic read-only query is rerun at acceptance. No SQL schema or data write belongs to this round.

## Validation obligations

The focused tests cover:

- canonical serialization determinism and ambiguity rejection;
- explicit compatibility instead of same-major SemVer inference;
- normative-digest mismatch rejection;
- history snapshot stability and revision sensitivity;
- ordering, issue encoding, and red-number canonicalization;
- exact compatibility with existing rolling and expanding slices;
- include/exclude-as-of semantics;
- target leakage, missing cutoff, and insufficient-history rejection;
- artifact/envelope determinism and tamper detection;
- executable golden-suite outputs;
- preservation of the legacy research-runtime fingerprint path.

Focused result before full acceptance:

```text
19 passed in 0.36s
```

Full Python regression:

```text
1051 passed, 4 warnings in 44.70s
```

The four warnings are the existing Python 3.14 `fork()`-from-a-multithreaded-process deprecation warnings in training-supervisor multiprocessing tests. There were no failures.

## Final production-state check

The acceptance query returned the same values and byte-level row digests:

```text
history rows: 3477, latest issue: 2026080
forward prediction runs: 3 pending
forward candidates: 30000
forward evaluation runs: 0
run-row sha256: 9205765b823d67f11de1b356078461e687de667473b959d35fed4b3960215011
candidate-row sha256: 0d049313927d238b304e1790fc2f0e87f4f239b1407a0fa91cfa923b7c0137d5
```

No production row, status, timestamp, candidate, score, historical fingerprint, or evaluation record changed.

## Next migration boundary

Migrate one characterized training or forward call surface to `WindowSpec` at a time, compare every selected issue and downstream packed `WindowState`, and retain the direct-slice implementation as a temporary oracle. Candidate Contract v1 remains a separate round; Feature Contract cannot be frozen until both Window and Candidate inputs are stable.
