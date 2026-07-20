# M2 Frozen-Future-30 Rolling-History Preregistration

- Status: accepted pre-outcome clarification
- Owner lane: Research and Knowledge
- Protocol: `frozen_future_30_shadow_v1.1_rolling_history_clarification`
- Accepted: 2026-07-20, before issue `2026083` was present in authoritative history

## Task frame

Frozen-Future-30 asks whether one unchanged `static_100` model records at least two exact
Top10000 hits among the first 30 eligible issues strictly after `2026082`. Each issue must have a
complete 10,000-row prediction artifact sealed before its outcome is available. The experiment is
a prospective ranking audit, not evidence that random draws are predictable and not betting advice.

The original v1 preregistration fixed both the initial history fingerprint and the requirement for a
pre-outcome snapshot for every issue. Those statements were ambiguous across issues: a model that
uses newly available history cannot keep the same content-addressed Runtime identity. Before the
first target outcome was observed, the user approved the following append-only clarification:

> Freeze model and contract identity; roll authoritative history between issues; seal every
> content-derived identity before the corresponding outcome.

The original preregistration and the sealed `2026083` evidence are not rewritten or superseded.
This clarification defines how ordinals 2 through 30 continue the same study.

## Frozen identity versus rolling identity

| Frozen for all 30 issues | Recomputed and sealed for each issue |
| --- | --- |
| source worker tree `7a5f305a6162949a157c414d8078649d677c89cf` | authoritative history fingerprint through the issue immediately before the target |
| line `static_100` | Verified Runtime ID and verification digest |
| config hash `4de6114fa68db30ae0ad23ba5f5f515b1b1eabee8d251d83e1b04a6b6ed56385` | Runtime Envelope digest |
| existing Feature and weight definitions | Candidate ABI verification and package digests |
| scoring contract `dehps-scoring-strict-v1` | candidate payload and Prediction Evidence digests |
| ranking contract `strict_v1` | isolated manifest digest |
| Candidate ABI contract `candidate_abi.v1` | as-of issue, target issue, generation time, and seal time |
| legal/ranked/excluded counts `1,107,568 / 1,105,506 / 2,062` | backend-equality comparison bound to that Runtime instance |
| Top-N `10,000`, primary metric, cohort size, null, and decision threshold | outcome artifact and evaluation evidence after the outcome arrives |

A changing content digest is expected when legal inputs change. It is not model drift when the
frozen identity remains exact and the new digest is observed, verified, content-addressed, and
sealed append-only. An unexplained, missing, retrospectively reconstructed, or silently reused
identity is drift and fails closed.

## Per-issue lifecycle

For cohort ordinal `k`:

1. synchronize and validate authoritative history only through the preceding eligible issue;
2. prove `as_of_issue < target_issue` and prove the target outcome is absent;
3. use the frozen model identity to compile one new Verified Runtime instance;
4. verify exactly 10,000 unique ranked candidates and exact backend equality;
5. recheck target absence before and after canonical, content-addressed sealing;
6. after the outcome becomes authoritative, evaluate only the previously sealed artifact;
7. append the result without changing production selection or Promotion Gate state;
8. repeat with the newly legal history for the next target.

No outcome, parser ordering, sync side effect, later issue, or evaluation result may enter the next
prediction before that information is legally part of its as-of history.

## Ordinal 1 binding

Issue `2026083` remains cohort ordinal 1:

- as-of issue: `2026082`;
- initial history fingerprint:
  `0f1fe9ed9668ce2a0a90f67c6d46c2c28806172ea921f28074b40c4c5c5a6ca3`;
- sealed manifest digest:
  `2174a98eb64752396fe369bfad6d303b105ae539624a830ef8cee9485de23419`;
- Prediction Evidence digest:
  `bb5aeb5cb1a0dbf9ab97dc8306be70918af8c540498df420366b25317a1ed291`;
- candidates: 10,000 unique rows, ranks 1 through 10,000;
- production selection changed: false;
- promotion allowed: false.

The first outcome was absent when the v1.1 clarification was approved. No evaluation result or
scientific conclusion existed at that point.

## Null model and decision rule

The amendment changes no scientific parameter. Under the ranked-uniform null, any pre-outcome set
of exactly 10,000 unique rows from the fixed 1,105,506-row ranked universe has conditional hit
probability

```text
p = 10000 / 1105506 = 0.009045631593134727...
```

Allowing the set to depend on earlier authoritative outcomes does not change this conditional
probability: the set is measurable before the next independent null outcome. Consequently the
preregistered 30-issue count retains the same binomial null:

```text
X ~ Binomial(30, p)
E[X] = 0.2713689477940418...
P(X >= 2) = 0.03010070751526635...
```

The primary decision remains `exact_top10000_hits >= 2` after all 30 eligible issues. No interim
Research decision is allowed. Top100, Top1000, Red5, rank distribution, and other diagnostics remain
secondary non-decision metrics.

## Failure and invalidation conditions

The cohort fails closed on any of the following:

- a target lacks a complete snapshot sealed before its outcome;
- Feature, weight, config, source worker tree, contract, universe, exclusion, or Top-N identity
  changes;
- candidate count is not 10,000 or candidate identities are not unique;
- a history fingerprint, Runtime, ABI, candidate, prediction, or manifest identity is missing,
  invented, unexplained, or reconstructed after seeing the target;
- parser, synchronization, duplicate, issue-identity, leakage, or attestation validation fails;
- a retrospective issue is included, or the metric, null, threshold, cohort size, or stopping rule is
  changed after observing outcomes.

## Explicit non-goals

- no Feature, weight, Window formula, scoring, ranking, Candidate ABI, or Runtime change;
- no claim that Runtime equality improves Prediction Quality;
- no production selection change and no automatic promotion;
- no Expected Value claim;
- no acceptance or rejection of the hypothesis before 30 completed future issues.

## Audit record and next verification

- Original preregistration: `research-m2-frozen-future-30-preregistration`.
- Rolling-history clarification: Agent Request
  `research-m2-frozen-future-30-rolling-history-amendment-v1`, request id `151`.
- Human Reviewer decision: `批准滚动历史`.
- Clarification execution: id `73`, completed in the isolated environment.
- Historical boundary: Gauss and Riemann are historically inspired verification lenses, not literal
  minds, evidence, or authority.

The next verification is operational: evaluate the sealed ordinal-1 artifact only after issue
`2026083` is authoritative, then use history through `2026083` to seal ordinal 2 before its outcome.
