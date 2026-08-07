# M4 P2.7 Round 23 single checkpoint-journal replay

Date: 2026-08-07

Role: Engineering Agent

Agent Request:
`engineering-p27-single-checkpoint-replay-round-23-20260807`
(request 290, execution 211)

## Primary goal

Remove the redundant second full checkpoint-journal verification from P2.7
completion assembly while preserving one complete, fail-closed verification for
every persisted replicate.

## Non-goals

- no change to training inputs, folds, seeds, scenarios, features, refit policy,
  statistical calculations, thresholds, Gate, Evidence, or decision logic;
- no skipped journal validation and no trust in an unverified persisted result;
- no mutation or recomputation of the completed 31,000-replicate execution;
- no promotion or reinterpretation of the existing research result.

## Root cause

`assemble_completion` called `_validate_persisted_replicate`, which already
reads and verifies the complete checkpoint journal, and then immediately called
`verify_checkpoint_journal` a second time for the same replicate. A mismatch in
the first pass already aborts assembly, so the second read supplied no additional
acceptance condition.

For the completed P2.6.3 artifact set, each pass reads approximately 40 GB. The
duplicate pass therefore doubled checkpoint I/O during P2.7 replay and accounted
for most of its roughly 23-minute runtime.

## Implementation

Completion assembly now relies on the verified payload returned by
`_validate_persisted_replicate` and records its journal digest without reopening
the journal. The persisted completion contract is unchanged:

- every replicate must still pass full checkpoint-journal verification;
- a missing, reordered, changed, or digest-mismatched journal still aborts;
- successful completion still records `checkpoint_journal_failure_count: 0`;
- ordered journal digest-root construction and all downstream identity checks
  remain unchanged.

A regression test counts verifier invocations and proves both properties: a
valid persisted replicate is verified exactly once, and a verifier failure is
still propagated immediately.

## Validation

```text
pytest -q test_information_theory_measurement_validation_execution.py
  -k 'completion_assembly_verifies_each_checkpoint_journal_once or
      checkpoint_journal_is_persisted_before_target_and_replayable'
2 passed, 29 deselected

pytest -q test_information_theory_measurement_validation_execution.py
  test_research_os_mainline_supervisor.py test_prediction_v2_shadow.py
69 passed
```

The estimated P2.7 replay cost changes from two approximately 40 GB journal
passes to one. Based on the observed 23-minute replay, the expected runtime is
approximately 11-13 minutes on the same host. This is an engineering estimate,
not a new live mainline measurement.

The full main-branch test suite currently has 13 pre-existing failures in frozen
P2.6.3 source-identity expectations. They were present before this round and are
outside its approved result-blind contract; this change neither hides nor
rewrites them.

## Mainline integration matrix

| Requirement | Round 23 status |
|---|---|
| Goal and authorized Engineering request | PASS — request 290 / execution 211 |
| Root cause and bounded implementation | PASS |
| Exactly one complete journal verification per replicate | PASS — regression test |
| Fail-closed journal mismatch behavior | PASS — regression test |
| Relevant execution, Supervisor, and shadow tests | PASS — 69 tests |
| Accepted PR merged to `main` | PENDING |
| Fresh Supervisor running accepted commit | PENDING |
| Canonical mainline execution or replay uses the optimization | PENDING |
| Deterministic replay proof for this implementation | PENDING |

Current completion answer:

```text
NO — INTEGRATION_PENDING
```

The code path and fail-closed behavior are validated locally, but this
performance capability is not complete under the permanent integration rule
until an accepted commit is used by the canonical Supervisor and a downstream
mainline execution or replay supplies immutable proof.
