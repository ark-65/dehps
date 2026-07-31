# M4 Measurement Contract v2 — Design Freeze

Date: 2026-07-31

Role: Engineering Agent

Primary goal: freeze and wire a result-blind hierarchical measurement contract
without changing, stopping, renaming, or inspecting the running P2.6.1
marginal-output acceptance baseline.

## Outcome

M4 Measurement Contract v2 is frozen in source with three incremental
estimands, a complete mechanism-by-estimand role matrix, and a deterministic
Gate Compiler. The canonical Task, capability, artifact projection, unified
status projection, next consumer, and replay implementation exist in source.

The task is deliberately not imported or dispatched in the live control plane.
The current Research Evidence Supervisor is synchronous and is blocked inside
P2.6.1. A concurrent import or second targeted Supervisor could be overwritten
by the old process's captured manifest when P2.6.1 finishes. Therefore this
round is `CODE_COMPLETE / INTEGRATION_PENDING`, not mainline-complete.

No P2.6.1 replicate, aggregate, gate output, or other partial statistical result
was read. Evidence Progress remains zero.

## Authorization

- Engineering Request:
  `engineering-m4-measurement-contract-v2-design-20260731`
- Durable Agent Request id: `229`
- Durable Engineering execution id: `150`
- User approval boundary: keep P2.6.1 running as the Marginal Measurement
  Acceptance Baseline; start M4 v2 as a separate design phase; do not start
  Temporal or Joint formal execution.
- Production action: none.

## Governed task declaration

| Field | Binding |
| --- | --- |
| Mainline problem | The current marginal-output experiment cannot define or credit static marginal, strict-history temporal, and residual joint information as if they were one estimand. |
| Node supported | M4 measurement design alongside, not inside, the immutable P2.6.1 execution. |
| Goal | `M4_INFORMATION_THEORY_EVIDENCE` |
| Task | `m4-v2-measurement-contract-design` |
| Task digest | `e8ad98546025a41803b10acca9fca805b20781b699c78792e1fd05d221cb10a1` |
| Ready condition | Frozen v2 source contract available; Scheme A repair complete; `m4-runtime-slot:p2-6-1-released` available after the synchronous P2.6.1 process exits. |
| Runner | Unified Research Evidence Supervisor capability `m4_v2_measurement_contract_design` |
| Upstream artifacts | Legal six-of-33 contract, P2.2 Metric Kernel, P2.3 harness, Scheme A repair manifest, P2.6.1 source manifest, v2 source contract |
| Downstream artifacts | Estimand, mechanism-role, Gate Compiler, and design-completion artifacts |
| Status projection | `unified_m4_status.measurement_system_v2` |
| Engineering progress | Tracked as v2 lifecycle; current v1 percentage is not rebaselined. |
| Evidence progress | 0% to 0%; design artifacts are not Evidence. |
| Decision consumer | Future branch-specific identifiability preflight and hierarchical Gate Compiler |
| Next consumer | `m4-v2-branch-identifiability-preflight-design` |

## P2.6.1 boundary

P2.6.1 keeps all immutable identities:

```text
task:
  m4-p2-false-positive-and-power-runs

task digest:
  80068e22f5e1c343fd86213faa0d9a411d71f92ad2750fed10449a10151de8fa

measurement manifest:
  a4e46a434a4b2ef9fe56ed0390d58ca5a45bbad21685b81cb983f7261b3abf58

semantic purpose:
  MARGINAL_OUTPUT_MEASUREMENT_ACCEPTANCE_BASELINE

v2 historical branch evidence credit:
  NONE
```

This is not a rename or reinterpretation of its frozen research outcome. It is
a lineage description: P2.6.1 tests 33 marginal outputs with a synthetic-only
pre-target instrument. It does not by itself measure stationary historical
marginals, strict-history temporal gain, or residual joint gain.

## Two measurement axes

The repair separates two concepts that were previously easy to conflate:

| Axis | Values |
| --- | --- |
| Output geometry | Number-event marginal; legal fixed-cardinality joint |
| Conditioning set | Stationary/no history; strict prior history `H<t`; synthetic pre-target instrument for measurement health only |

A synthetic instrument may test measurement health. It may not create
historical evidence.

## Incremental estimands

All outcomes remain on the exact legal space

```text
Omega = {y in {0,1}^33 : sum(y_i) = 6}
|Omega| = C(33,6) = 1,107,568
```

### MARGINAL_STATIC

Candidate: stationary, outer-train-only number-event probabilities.

Baseline:

```text
q_0,i = 6/33
```

Estimand:

```text
sum_i E_t[
  log2 Bern(Y_t,i; q_M,t,i)
  -
  log2 Bern(Y_t,i; 6/33)
]
```

This is a composite marginal score gain in bits per issue, not joint mutual
information.

### TEMPORAL_MARGINAL_INCREMENT

Candidate:

```text
q_T,t,i = P(Y_t,i = 1 | H<t)
```

Baseline: the accepted same-fold `MARGINAL_STATIC` artifact.

Estimand:

```text
sum_i E_t[
  log2 Bern(Y_t,i; q_T,t,i(H<t))
  -
  log2 Bern(Y_t,i; q_M,t,i)
]
```

It may not fall back to legal uniform, because that would credit the static
gain a second time.

### JOINT_RESIDUAL_INCREMENT

Candidate: a future joint probability on legal six-of-33 outcomes conditioned
only on `H<t`.

Baseline: the maximum-entropy legal fixed-cardinality distribution matching the
accepted temporal conditional marginals:

```text
Q_base(y | h)
  = 1[y in Omega] exp(sum_i lambda_i(h) y_i) / Z(h)
```

with:

```text
E_Q_base[Y_i | h] = q_T,t,i(h)
sum_i q_T,t,i(h) = 6
```

An independent Bernoulli product and a uniform fallback are forbidden. The
numerical solver and boundary policy remain
`UNRESOLVED_PENDING_PREFLIGHT`; no Joint probe or solver is implemented in this
round.

The Joint baseline has its own derived artifact identity. Its report must carry
both:

```text
baseline_artifact_digest
baseline_source_model_artifact_digest
```

The first identifies the maximum-entropy legal distribution; the second must
equal the accepted Temporal model artifact from which its conditional
marginals were derived. The two digests must differ. This preserves solver
provenance instead of treating a Temporal marginal model as if it were already
a legal joint distribution.

## No-duplicate-credit rules

- Temporal consumes the accepted same-fold Marginal baseline.
- Joint consumes a distinct Temporal-derived, marginal-matched legal baseline
  whose source-model digest is the accepted Temporal artifact.
- One canonical endpoint digest belongs to exactly one primary branch.
- Leakage sentinels have `decision_credit=false`.
- P2.6.1 has no v2 historical branch evidence credit.
- Branch estimates are not summed into a primary “total information” claim.
- A missing upstream baseline makes the dependent branch `NOT_RUN` with
  `MeasurementHealth=INCONCLUSIVE`.

## Mechanism role matrix

Roles are relative to an estimand, not intrinsic properties of a mechanism.
Every synthetic role has `historical_evidence_eligible=false` and
`decision_credit=false`.

| Mechanism | Marginal Static | Temporal Increment | Joint Residual |
| --- | --- | --- | --- |
| Legal uniform null | Negative | Negative | Negative |
| IS1 single conditional | Negative | Out of scope | Out of scope |
| IS2 local temporal | Negative | Positive | Unresolved preflight |
| IS3 pair conditional | Negative | Leakage sentinel | Unresolved preflight |
| IS4 marginal-preserving | Negative | Negative | Positive |
| V2 stationary marginal control | Positive | Negative | Negative |
| V2 history-conditional marginal control | Negative | Positive | Negative |
| V2 history-conditional joint control | Negative | Negative | Positive |

The three `V2_*` controls are design-only and not implemented. IS3 cannot be
promoted to a Joint positive control until its residual against the new
marginal-matched legal baseline is computed. IS4 is a Joint measurement-health
positive control but its current synthetic instrument remains ineligible for
historical evidence.

## Gate Compiler

Every branch report carries an explicit identifiability-preflight status:

```text
PASS | FAIL | UNRESOLVED
```

`PASS` and `FAIL` require an immutable preflight artifact digest.
`UNRESOLVED` requires no digest and compiles the branch to Health
`INCONCLUSIVE` plus Evidence `NOT_RUN`. A failed preflight compiles Health
`REPAIR`. Therefore the currently unresolved Joint solver cannot be promoted by
submitting an otherwise all-PASS report.

The compiler emits two independent branch statuses:

```text
MeasurementHealth:
  PASS | REPAIR | INCONCLUSIVE

HistoricalEvidence:
  POSITIVE | NEGATIVE | INCONCLUSIVE | NOT_RUN
```

The fixed primary family contains all three branches. Holm familywise control
uses alpha `0.05`; a missing endpoint, p-value, or invalid branch remains in the
family with `p=1`. The practical threshold is frozen at `0.01 bits/issue`.
Canonical endpoint p-values use the one-sided
`H0: Delta <= 0.01` comparison. Intervals use Bonferroni two-sided
family coverage of 95% (total two-sided `alpha/3` per branch and
`alpha/6` per tail). MDE is a nonnegative design-stage quantity computed at
one-sided `alpha/3` and at least 80% power. Negative evidence does not reuse
the two-sided interval's upper endpoint: it consumes a separate one-sided
Bonferroni simultaneous upper bound at `alpha/3`, with the equivalence null
`H0: Delta >= 0.01`, at least 80% power at zero, and immutable interval,
upper-bound, MDE, and equivalence-power provenance artifacts.
Both interval artifacts bind the same canonical endpoint digest and obey
`two_sided_lower <= one_sided_upper <= two_sided_upper`.

Historical evidence also requires an accepted candidate-model artifact whose
identity differs from the scored baseline. A missing candidate or a
baseline-versus-itself report stays in the Holm family with `p=1` and compiles
to `INCONCLUSIVE`; it cannot support either a positive or a negative claim.
NEGATIVE additionally requires Holm-adjusted `p>0.05`. A significant primary
test whose simultaneous lower bound has not crossed the practical threshold is
therefore `INCONCLUSIVE`, never negative.

| Condition | Compiled result |
| --- | --- |
| Failed preflight, validity failure, or completed acceptance failure | Health `REPAIR` |
| Incomplete, underpowered, missing/mismatched baseline, or unresolved preflight | Health `INCONCLUSIVE` |
| Preflight, baseline provenance, and all measurement checks pass | Health `PASS` |
| Healthy, complete, canonical endpoint, Holm-positive, lower bound above 0.01 | Evidence `POSITIVE`; MDE not required |
| Healthy, complete, Holm-adjusted p above 0.05, provenance-complete, equivalence-powered, nonnegative MDE at most 0.01, separate one-sided upper bound at most 0.01 | Evidence `NEGATIVE` |
| Non-significant without sufficient equivalence power | Evidence `INCONCLUSIVE` |
| No historical run | Evidence `NOT_RUN` |

Global compilation:

```text
any healthy POSITIVE
  -> CANDIDATE_INFORMATION_FOUND

all branches healthy + complete + NEGATIVE
  -> NO_DETECTABLE_INFORMATION

otherwise
  -> INCONCLUSIVE
```

A damaged branch reduces coverage to `PARTIAL` and is listed for repair. It
does not erase a healthy positive finding in another branch. Damage propagates
only across an explicit adjacent-baseline dependency: an unaccepted Marginal
baseline blocks Temporal, and an unaccepted Temporal source blocks Joint.

Each branch output embeds a canonical digest of every compiler-consumed report
field and projects the effect interval, MDE, equivalence upper bound, acceptance
flags, and all provenance digests. Consequently, two reports that happen to
produce the same categorical decision cannot collapse to the same Gate
artifact when their statistical inputs differ.

## Result-blindness

The source validator requires:

```text
p2_6_1_partial_replicates_read      false
p2_6_1_partial_aggregates_read      false
p2_6_1_gate_outputs_read            false
real_history_outcomes_read          false
formal_v2_results_existed           false
thresholds_selected_from_results    false
```

Only frozen source contract identities and exact synthetic mechanism
definitions are accepted upstream. Runtime replicate, aggregate, partial-result,
and gate-output paths are forbidden.

## Source identities

| Artifact | Digest |
| --- | --- |
| M4 Measurement Contract v2 | `a0a367c99d7646cadc162bd9ceb0d5d73481cd7c26656bf02b40a99d9180095b` |
| Source control-plane manifest | `c8fbdd8523b0a14e18d6828535b90f7f56c3d1beaf059bf2e4ec687a2465748d` |
| V2 design Task | `e8ad98546025a41803b10acca9fca805b20781b699c78792e1fd05d221cb10a1` |
| Next preflight-design Task | `bf976f6508ba8a1cfc63bd86768b0a1a06d74efb0cceec97aa19573503733693` |
| Projected estimand artifact | `e05c8e49af3417d8649db7a9ca067ac42fe76405adf81a8ebf8d02496e584f0e` |
| Projected role-matrix artifact | `644b4ea6d9c20b336e4d8a56a306b1a6902a90b5cebc2ea58531e13acccbf070` |
| Projected Gate Compiler artifact | `9f9519be92fb5db4a4fb4939d1d5d3d32f7646a6e449f3dd20fd5c63b409f821` |

The first three design artifacts are deterministic projections. They are not
registered mainline artifacts until the canonical task executes.

## Scientific cross-review

The following are historically grounded reasoning lenses, not literal
reconstructions of Gauss or Riemann.

Gauss pass:

- the legal sample space, fixed cardinality, null marginal, adjacent baseline,
  and proof obligations are explicit;
- a Bernoulli-product Joint baseline is rejected because it assigns probability
  outside the legal space;
- IS3 residual Joint information is not guessed from unlike score geometries;
- non-significance cannot be compiled as negative evidence without equivalence
  power and MDE support.

Riemann pass:

- output geometry and conditioning set are represented as separate axes;
- Marginal, Temporal, and Joint are nested incremental comparisons rather than
  three unrelated black-box models;
- the accepted baseline artifact is an explicit edge between adjacent levels;
- branch-local damage changes coverage without collapsing unrelated healthy
  branches.

Shared minimum conclusion:

> Freeze target geometry, conditioning set, and the adjacent baseline before
> implementing a branch. Run identifiability preflight before any Temporal or
> Joint formal workload.

## Runtime isolation audit

The current Supervisor has a single global Ready Queue and synchronously calls
one capability. P2.6.1 owns an internal eight-worker process pool, but this is
not task-level lane concurrency.

Starting a second targeted Supervisor is unsafe:

1. P2.6.1 captured its running manifest at start.
2. It will later finalize from that captured manifest.
3. A concurrently imported v2 task or fact can be lost when the old manifest is
   re-imported.
4. Both processes would also overwrite the same global status files.

Therefore:

- no live manifest import occurred;
- no second control-plane key was created;
- no second Supervisor was started;
- P2.6.1 was not stopped or restarted;
- the source v2 task waits on
  `m4-runtime-slot:p2-6-1-released`.

## Validation

Focused new-contract tests:

```text
25 passed
```

Full Worker suite in the restricted sandbox:

```text
1910 passed, 6 skipped, 1 environment failure
```

The single environment failure was
`test_parallel_coordinator_materializes_plan_and_projects_resumable_progress`:
the sandbox denied the multiprocessing forkserver's AF_UNIX socket bind with
`PermissionError: [Errno 1] Operation not permitted`. The exact test was then
rerun in the approved unrestricted execution environment:

```text
1 passed
```

Thus every collected test assertion passed (`1911 passed, 6 skipped` across
the full sandbox run plus the isolated environment-confirmation run), while no
single unrestricted full-suite run was performed.

The tests cover pinned digest mutation and recursive immutability, exact branch
order, result blindness, role coverage, deterministic artifact projection,
direct and derived adjacent-baseline provenance, missing-baseline compilation,
unresolved preflight, missing-endpoint fail-closed behavior, strong-positive
evidence without an MDE, nonnegative MDE enforcement, duplicate endpoint
rejection, fixed-family Holm behavior, protection from invalid-p-value Holm
contamination, both directions of candidate/baseline self-comparison,
contradictory interval rejection, distinct equivalence-bound endpoint binding,
negative-evidence equivalence requirements, canonical branch-report input
digests, branch-local repair, P2.6.1 task identity, persistent dual v1/v2 status
projection including repair-summary priority, complete Supervisor replay with
registered-child tamper detection, source resolver state, capability registry,
and future readiness after the explicit runtime-release event.

## Integration matrix

| Integration item | Current evidence | Status |
| --- | --- | --- |
| Canonical Goal | Existing `M4_INFORMATION_THEORY_EVIDENCE` unchanged | PASS in source |
| Dependency Graph | V2 design and next preflight-design Tasks defined | PASS in source |
| Ready Queue | V2 resolves `external_wait` until P2.6.1 releases the synchronous Supervisor | PENDING by design |
| Unified Runner | Capability registered in Research Evidence Supervisor | PASS in source |
| Upstream artifacts | Six source-only identities pinned | PASS |
| Downstream artifacts | Four deterministic artifact builders implemented | PASS in source |
| Status projection | `measurement_system_v2` reports design and `INTEGRATION_PENDING`; legacy P2 and v2 execution summaries persist independently across idle heartbeats | PASS in source |
| Engineering Progress | V2 lifecycle tracked without changing v1 percentage | PASS |
| Evidence Progress | Explicit zero increment | PASS |
| Downstream consumer | Preflight-design Task exists and depends on the completion fact | PASS in source |
| Mainline execution | No live execution id or completed event | NOT RUN |
| Artifact registry | No live registrations | NOT RUN |
| End-to-end replay | Capability-specific reconstruction and byte-equivalent parsed-content comparison for every registered design artifact implemented, but no physical execution exists to replay | NOT RUN |
| No old bypass | No manual completion fact and no second control plane | PASS |

## Next acceptance operation

After P2.6.1 exits, a separately approved Operator round must:

1. export the durable live manifest;
2. merge the two v2 source Tasks and contract fact while preserving every live
   Task status, fact, and immutable execution identity;
3. append `m4-runtime-slot:p2-6-1-released`;
4. import the merged manifest;
5. let the same unified Supervisor execute
   `m4-v2-measurement-contract-design`;
6. replay the same execution and artifact identities;
7. verify the next preflight-design Task is the downstream consumer.

That operation must not use the P2.6.1 statistical result to modify this frozen
contract.

## Completion classification

**NO — implementation remains INTEGRATION_PENDING.**
