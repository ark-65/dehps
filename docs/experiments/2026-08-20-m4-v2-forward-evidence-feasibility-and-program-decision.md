# M4-v2 Forward Evidence Feasibility and Program Decision

Date: 2026-08-20 (Asia/Shanghai)

## Round contract

Primary goal: make exactly one zero-compute forward-program decision after the
closed power-inconclusive predictive P3 and the clean diagnostic P4.

Non-goals: no model training or refit, no historical P3 fold, no prediction,
no forward checkpoint, no settlement, no forward collection, no formal P4,
no P5, no Promotion, and no modification of an old registered artifact.

Governance is frozen by Research Request 634 / Execution 518 / scientific
Reviewer Decision 2667 and Engineering Request 635 / Execution 519 / approval
Decision 2672. The Research analysis digest is
`c84543098541d9697707ed3013984bb03217616ae07f00e1c3c3fa63f778eada`.

## Immutable scientific state

| Field | Frozen value |
| --- | --- |
| Existing independent folds | 2,581 |
| Required independent folds | 4,676 |
| Missing independent folds | 2,095 |
| Current MDE | 0.013459908060402983 bits/issue |
| Practical threshold | 0.01 bits/issue |
| Current equivalence power | 0.5311893549808094 |
| Target power | 0.8 |
| Unused independent historical holdout | No |
| P3 scientific disposition | `INCONCLUSIVE_DUE_TO_POWER` |
| P3 governance status | `CLOSED_NOT_AUTHORIZED_AFTER_DEEPER_VALIDATION` |
| Diagnostic P4 | `NEGATIVE_CONTROLS_CLEAN` |
| Formal P4 | `DEPENDENCY_WAIT` |
| PASS_TO_P4 | `NOT_EMITTED` |

## Calendar feasibility

The project schedule and the official rule agree on three issues per week,
drawn Tuesday, Thursday, and Sunday. The official 2026 closure notice removes
known National Day slots from the next-anchor-year calendar. The official
method enumerates dates after 2026-08-20; it does not substitute a fixed annual
constant.

| Cohort | Official completion | Historical-rate completion |
| ---: | --- | --- |
| 20 | 2026-10-11 | 2026-10-11 |
| 60 | 2027-01-12 | 2027-01-13 |
| 120 | 2027-06-01 | 2027-06-07 |
| 2,095 | 2040-01-12 | 2040-07-02 |

The trailing five-year date-only estimate contains 755 unique issues over
1,825 inclusive days, or 151.10032191780823 issues/year. Of 783 expected
weekday slots, 28 were missing or delayed, a rate of 0.035759897828863345;
there were no off-schedule issue dates. At that rate the complete missing
cohort requires 5,065 days, or 13.86496053356912 years.

Official evidence:

- Ministry of Finance rule: https://zhs.mof.gov.cn/zhengcefabu/201404/t20140421_1069579.htm
- Ministry of Finance 2026 closure notice: https://zhs.mof.gov.cn/zhengcefabu/202512/t20251225_3980205.htm

## Resource, token, and aging feasibility

Registered event timestamps give 2.730749 seconds of wall time for the prior
2,581-issue historical execution, or 0.0010580197597830298 wall seconds/issue.
Component CPU telemetry is unavailable. The preregistered planning ceiling is
therefore 60 CPU-seconds each for refit, checkpoint serialization, and
settlement: 7.7 CPU-hours/year at 154 scheduled issues and 104.75 CPU-hours for
2,095 issues. Storage ceilings are 1 MiB filesystem and 64 KiB database per
issue, or about 2.046 GiB filesystem and 130.94 MiB database for the complete
program. These are ceilings, not measurements.

Normal issue operation requires zero Codex calls and zero tokens. Frozen
planning envelopes are <=300,000 tokens at launch, 100,000 tokens/year for two
exceptional investigations, 100,000 per milestone review, and <=300,000 for
the final decision. No monetary conversion is made without a frozen price
source.

The current Python is 3.14.4, the project declares Python >=3.11 without a
Python dependency lock, and PostgreSQL uses unpinned `postgres:17`. Python
3.14 reaches upstream end of life in 2030-10, well before a 2040 complete-cohort
decision. Computation and storage are not binding; calendar duration and
scientific-identity maintenance are.

## Frozen four-program comparison

Weighted maximum: 84. No program hard-failed its own stated claim.

| Program | Score | Main tradeoff |
| --- | ---: | --- |
| `LONG_HORIZON_CONFIRMATORY_FORWARD` | 57 | Directly addresses the power deficit, but yields no permitted conclusion for roughly fourteen years and has high identity-aging risk. |
| `BOUNDED_OPERATIONAL_FORWARD_STUDY` | 67 | Cannot repair old P3, but gives a preregistered operational decision within one year with genuinely new issues. |
| `REDESIGN_PROSPECTIVE_RESEARCH_QUESTION` | 56 | May be shorter, but currently lacks a frozen estimand, threshold, sample-size proof, and legal P4 dependency. |
| `TERMINATE_PREDICTIVE_ROUTE` | 58 | Ends cost and aging risk immediately, but discards the only direct prospective-evidence route before a bounded test. |

Opportunity cost is decisive: the long program's first formal resolution is
estimated at 2040-07-02 and has no interim scientific decision, whereas the
bounded 120-issue study makes one valid continue/stop/invalid/inconclusive
decision around 2027-06-07.

## Scientific Reviewer decision

Decision: `LAUNCH_BOUNDED_OPERATIONAL_FORWARD_STUDY`

- Selected program: `BOUNDED_OPERATIONAL_FORWARD_STUDY`
- Target = maximum: 120 valid independent issues
- First eligible issue: 2026-08-23
- Official best case: 2027-06-01
- Historical-rate estimate: 2027-06-07
- Data reuse: `STAGED_INDEPENDENT_SAMPLES`
- Next task: `m4-v2-bounded-operational-forward-study-preregistration`
- Next-task execution authorized: no

Cohort A is used only for the bounded operational gate. It may not enter model
or threshold selection, long-horizon confirmation, or a later predictive P3.
If the decision is to continue, all confirmatory evidence begins with a wholly
new cohort B.

At 20 and 60 issues, only integrity may be inspected: checkpoint timeliness,
identity/digest continuity, missing or duplicate issues, settlement
completeness, runtime failures, storage, and security. Aggregate outcome
metrics must not be calculated or exposed. The sole outcome-bearing review is
at exactly 120 valid issues.

Frozen terminal rules at issue 120:

- `INVALID_OPERATIONAL_STUDY`: any late checkpoint, future access, duplicate
  issue, identity drift, unregistered semantic repair, missing immutable
  artifact, replay mismatch, or unprovable cohort identity.
- `STOP_PREDICTIVE_RESEARCH`: mean <= -0.01 bits/issue or the preregistered
  two-sided 95% interval upper bound is < 0.
- `CONTINUE_LONG_HORIZON_RESEARCH`: every integrity gate passes, mean >= +0.01
  bits/issue, and the preregistered two-sided 95% interval lower bound is > 0.
- `OPERATIONALLY_INCONCLUSIVE`: neither continue nor stop; cohort A is not
  extended and no alternative window is selected post hoc.

## Mainline integration matrix

| Link | Declared binding | Current proof |
| --- | --- | --- |
| Goal | `M4_V2_FORWARD_EVIDENCE_FEASIBILITY_AND_PROGRAM_DECISION` | Registered in durable manifest `f4578685…` |
| Resolver | Frozen old route plus clean diagnostic facts | Decision task completed; successor is the sole Ready item |
| Ready Queue | Decision task first; successor after completion | Snapshot `ca501081…` contains exactly the bounded-study preregistration successor |
| Supervisor | `m4_v2_forward_evidence_feasibility_and_program_decision` | Execution `621e3b91…` completed once at merged commit `422a7aca…` |
| Artifacts | Feasibility, decision, replay | Three capability artifacts and the execution artifact are registered |
| Status | One completed task, one Ready unexecuted successor | Durable states are `COMPLETE` and `INTEGRATION_PENDING`/Ready respectively |
| Next task | `m4-v2-bounded-operational-forward-study-preregistration` | Capability is `None`; execution remains unauthorized and count is zero |

Implementation validation before PR:

- `python -m pytest -q apps/worker-python/tests/test_m4_v2_forward_evidence_feasibility.py`: 5 passed.
- Governance binding check: `GOVERNANCE_VERIFIED`.
- Ruff on the five touched Python surfaces: passed.
- Repository import dry verification passed for both the initial decision-ready
  and simulated decision-completed/successor-ready manifests.
- Capability dry execution resolved all 12 exact registered parents and built
  exactly three artifacts with zero folds and `workload_rerun=false`.

The broader predecessor diagnostic test currently detects the intentional
change to shared `supervisor.py` / `repository.py` bytes through its old frozen
source contract. This round does not rewrite that old source artifact because
the goal and Engineering authorization forbid old-artifact mutation. The old
registered diagnostic decision and replay payloads remain unchanged.

## Registered mainline outcome

Operator Request 636 / Execution 520 imported one manifest and dispatched one
task. The immutable execution identity is
`621e3b9107ec3651f53bc93e8bc825ba60dd3a42fc1308ba4a6e0b704e527b62`;
its execution artifact is
`9006b081ce0134309eebbc2188bc60207c225a0d4fb8df7a2e499967d9ae33d5`.
The event stream contains exactly sequence 0 `started` and sequence 1
`completed`.

Registered capability artifacts:

| Artifact | Digest | Registration digest |
| --- | --- | --- |
| `M4V2ForwardEvidenceFeasibilityArtifact` | `253c4a625de3babdd0fefb0776cf5d9760e608957bcd71f6850075571ebba49b` | `ed20bdc0c7bb96a3ff4c0e6b6b56000760ce1cc5ce8a79c4519864821d2775a7` |
| `M4V2ForwardEvidenceProgramDecisionArtifact` | `cf3863b244407fb56f45b2b158291e69d14745f438223723aded079419a1a791` | `634a1ef340898742dc5ed524794ba54efb84c1bdf553d8dc2e4469a35a20d2c4` |
| `M4V2ForwardEvidenceProgramDecisionReplayArtifact` | `9392782e38bb325e99eb45da50ca3c53e092173c94f12eb1dc1fde873ecfcd97` | `fb4bd968fb40470b0584ad459e2535f1bd5ff7d5005b56286e24446e0c024a7d` |

Generic replay returned `REPLAY_VERIFIED` and capability replay returned
`REGISTERED_REPLAY_VERIFIED`, with identical registered content,
`workload_rerun=false`, zero scientific computation, and zero actual folds.
All 12 frozen parent artifact digests still have their original registrations.

Final durable state:

- Manifest: `f45786853f1da9e74c7bb269d05b2544c9780b1c64d0864ebaa3ed82bd2e8141`
- Snapshot: `ca501081b7b26b489d072bedab3a2769f02d589c0d6240bf961d9f6747190acf`
- Goal count: 6; task count: 109
- Decision task: `COMPLETE`
- Ready Queue: only `m4-v2-bounded-operational-forward-study-preregistration`
- Formal P4: `DEPENDENCY_WAIT`
- `m4-p3-predictive-decision:PASS_TO_P4`: absent
- Model training/refit, historical P3 folds, forward samples, checkpoints, and
  settlements: zero / not started
- P5: `NOT_AUTHORIZED`; Promotion: `NOT_TRIGGERED`

Mainline answer:

`YES — validated by unified mainline execution and replay.`
