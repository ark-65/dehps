# M4-P3 Forward Prequential Confirmatory Successor — Launch Readiness

Date: 2026-08-22

Role: Engineering Agent

Primary goal: implement the frozen successor mainline and prepare the isolated Operator cutover.
Non-goals: no old-P3 repair, recovery lineage, schema registry, generic framework, model change, P4 execution, P5, Promotion, or production betting action.

## Immutable history and result-blind boundary

The existing `m4-v2-bounded-operational-forward-study-preregistration` Reviewer decision, task, and artifacts remain unchanged. A live preflight found an old-lineage pre-draw checkpoint for issue `2026097`; it has no settlement and no forward outcome read. It is excluded from the successor and is projected as `IMMUTABLE_HISTORY_NOT_CURRENT_ROUTE`.

The old P3 record remains exactly:

- practical target: `0.01 bits/issue`;
- power target: `80%`;
- disposition: `INCONCLUSIVE_DUE_TO_POWER`.

## Frozen successor contract

Research Request `640`, Research Execution `524`, and Reviewer Decision `2697` froze the result-blind successor before its first prediction. The content-addressed successor source contract is `139ddc97ce1d81ea4e6182359f8391532ed1911090db004bcdf9ebcdea5f9493`.

- Lineage: `M4_P3_FORWARD_PREQUENTIAL_CONFIRMATORY_SUCCESSOR_V1`
- Model: mechanically refit `MARGINAL_STATIC`; history is strictly limited to issues before target `t`.
- Primary endpoint: paired OOS Bernoulli log-loss gain against the same-issue legal-uniform `2/11` red-number baseline, in bits per issue.
- Practical threshold: `0.05 bits/issue`.
- Looks: `20 / 40 / 60 / 90 / 120`.
- Multiplicity: one-sided Bonferroni across five fixed looks; per-look alpha `0.005`; critical z `2.5758293035489`.
- Maximum N: `120` valid successor settlements.
- PASS: integrity passes, mean gain is at least `0.05`, and `mean / (frozen_sd / sqrt(n)) >= 2.5758293035489`.
- Harm failure: the corrected upper bound is below zero.
- Futility failure: at an interim look, conditional power to the N=120 efficacy boundary under true mean `0.05` is below `0.10`.
- Precedence: invalid execution, PASS, failure, then continue or max-N inconclusive.
- Legal decisions: `PASS_TO_P4`, `FAIL_NO_FORWARD_ADVANTAGE`, `CONTINUE_TO_NEXT_LOOK`, `INVALID_FORWARD_EXECUTION`, plus `INCONCLUSIVE_AT_MAX_N` only at 120.

Frozen historical long-run variance is `0.05302208982040761` (`sd=0.23026525969066114`), derived before successor results from the registered 2,581-fold historical score sequence. The 80%-power detectable effects are:

| N | Frozen SE | MDE, bits/issue |
|---:|---:|---:|
| 20 | 0.05148887735249605 | 0.17596069156408684 |
| 40 | 0.036408134331632404 | 0.12442299822724032 |
| 60 | 0.02972711719973522 | 0.10159095264131825 |
| 90 | 0.024272089554421606 | 0.08294866548482689 |
| 120 | 0.021020246157060024 | 0.07183565151987753 |

## Mainline and automation contract

The additive DAG uses the canonical `m4-information-theory-mainline` control plane and a successor-specific subclass of the unified Research Evidence Supervisor. Each issue has one ordered chain:

`refit -> pre-draw seal -> registered pre-draw replay -> audited draw event -> settlement -> registered settlement replay -> next issue`

The pre-draw artifact set contains the trained model and 33 probabilities, exactly 100 ranked model tickets, exactly 100 deterministic legal-uniform random-baseline tickets, the same deterministic blue number at each paired rank, a checkpoint, and a report. Ticket-support metrics are secondary and receive no primary-decision credit.

The timer invokes Python every 15 minutes. Python performs audited draw synchronization, settlement, the next mechanical refit, and the next pre-draw seal. Routine per-issue Codex invocation is zero. Aggregate outcomes are exposed only by the frozen review capability at registered looks or by anomaly handling.

Formal P4 preregistration is emitted with the P3 preregistration, but its executable task depends on both the successor `COMPLETE` fact and the successor-specific `PASS_TO_P4` fact. Its capability is intentionally not registered before that gate.

## Validation evidence before Operator release

- `python -m ruff check` on all new Python files: PASS.
- `python -m py_compile` on the new capability and scripts: PASS.
- Successor focused tests: `5 passed`.
- Successor plus applicable old-lineage tests, excluding one stale live-manifest fixture: `10 passed, 1 deselected`.
- Research OS control-plane, mainline-supervisor, and repository tests: `32 passed`.
- Additive live-manifest dry-run: `VERIFIED`; 114 existing tasks unchanged; 12 new tasks; zero deletions, rewrites, regressions, production actions, or Promotion effects; sole new Ready task is successor preregistration; formal P4 is `dependency_wait`.
- Old source identity verification: `VERIFIED`, artifact `d441052f517c562f6550942ca6ff2b5a5c2143e9a467644773476bd03d1ef68f`, source-set `8c6c3202994c2c1af53e74b19508c17479ff4ca7f65869dc633a29d06bca7bcb`.

The excluded old test is `test_manifest_keeps_formal_p4_waiting_and_registers_one_ready_preregistration`. It expects obsolete live manifest digest `f457868...`, while durable current mainline is already `227b495...`. No pinned old file was changed, and the content-addressed old-source verification above passes.

## Integration matrix at this engineering checkpoint

| Link | Evidence | Status |
|---|---|---|
| Goal | additive successor Goal in verified dry-run | VERIFIED |
| Resolver | sole successor preregistration Ready in dry-run | VERIFIED |
| Ready Queue | deterministic preregistration first | VERIFIED |
| Supervisor | successor capabilities registered through unified-supervisor subclass | CODE_COMPLETE |
| Capability | prereg/refit/seal/replay/settle/review implementation | CODE_COMPLETE |
| Artifacts | content-addressed contracts and deterministic unit replay | VERIFIED_LOCALLY |
| Status | compact autonomous status projection | CODE_COMPLETE |
| Next Task | dormant P4 dependencies and per-issue continuation | VERIFIED_LOCALLY |

Launch readiness conclusion: **NO — INTEGRATION_PENDING**. This report records the engineering checkpoint before the approved Operator release. Completion requires merged code, one successful canonical mainline preregistration/refit/pre-draw execution, registered replay, scheduler activation, and live status verification.
