# Prediction v2 Structural Baseline Comparison Route Decision — Round 81

## Round contract

- Primary goal: bind the valid frozen-baseline failure to one result-aware, zero-work mainline route decision.
- Non-goals: no new algorithm, hypothesis, candidate, seed, threshold, baseline, model, historical run, repeated comparison, legacy-route fallback, prediction claim, promotion, P3, betting output, or production action.
- Task: `prediction-v2-structural-baseline-comparison-route-decision`.
- Completion fact: `prediction-v2-structural-baseline-comparison-route-decision:COMPLETE`.
- Decision: `ARCHIVE_B176_FROM_ACTIVATION_AND_WAIT_FOR_NEW_RESULT_BLIND_RESEARCH_CONTRACT`.
- Downstream consumer: `prediction-v2-next-result-blind-research-intake`.
- External dependency: `research-contract:prediction-v2-next-result-blind-program:approved`.
- Research Request: 408; research execution: 329.
- Engineering Request: 409; engineering execution: 330.

## Registered result boundary

The capability reads only the previously registered full-comparison mainline execution and its result index, frozen gate outcome, and completion artifact:

| Input | Registered digest |
| --- | --- |
| Full comparison execution | `ca8b04b63f7295744b41fa2b33fcbec4a2c3e70e115a7662e04ec2cc3d9f233f` |
| Result index | `cb49d823118f682e585e1395a7124083c9c86ca36476cd975f563aca44187877` |
| Frozen gate outcome | `73ca03f93b2a9149d265502b75fd747370c3e493095d3a555b72c8ed6546bc20` |
| Comparison completion | `830513d1c77b6669a8e1ed2bd45d965f6644e0bb8dd543920de918e36e4b7541` |

The registered comparison was valid and replay-verified. It executed 384 baseline replicates and 17,301,504 candidate considerations. The candidate strictly dominated 0 of 128 replicates in every class; 14 singleton-first, 0 pair-first, and 5 distance-first replicates strictly dominated the candidate. The frozen acceptance rule required at least 122 candidate dominances and allowed no baseline dominance in every class.

## Decision and claim boundary

The exact route decision is:

1. archive B176 from any activation path;
2. preserve it only as `ARCHIVED_NON_PREDICTIVE_ENGINEERING_REFERENCE_ONLY`;
3. keep Prediction v2 in `SHADOW_ONLY / BASELINE_ONLY`;
4. keep historical Evidence `INCONCLUSIVE`;
5. wait for a separately approved result-blind research contract;
6. do not automatically generate a replacement hypothesis, relax the threshold, retry a seed, mutate the portfolio, or reactivate a legacy line.

This capability performs zero database queries, reads zero historical rows, executes zero folds, bootstrap children, or candidate considerations, creates no Evidence or model, and takes no production action. Its replay reconstructs registered content without rerunning the 17.3-million-consideration workload. The repetition marker remains `ABSENT_BY_CONSTRUCTION`; no duplicate, membership, uniqueness, or post-hoc repetition scan is added.

## Scientific cross-review

Einstein pass: the failed frozen test changes the state of the specific B176 candidate, not the definition of success after seeing the result. The smallest falsifiable conclusion is that B176 did not clear these three preregistered same-opportunity structural baselines.

Gauss pass: all four candidate coordinates, replicate counts, dominance counts, and thresholds remain exact integers. Because every class has candidate-dominated count 0 against a required 122, threshold relaxation would be a result-aware contract rewrite rather than evidence.

Riemann pass: failure at one point in a four-coordinate Pareto partial order does not prove that every structural representation is useless. It does prove that this point has no accepted route under the frozen comparison geometry.

Shared conclusion: archive B176 from activation, retain its immutable engineering reference, and require a new independently approved result-blind contract before any new structural program is introduced.

## Implementation

- one source-byte-pinned route-decision capability;
- three deterministic child artifacts: bounded decision, result-blind research-intake handoff, and completion;
- one immutable mainline execution artifact;
- exact five-input identity validation and parent semantic validation;
- additive manifest migration from 69 to 70 tasks;
- one new external-wait intake with no requested capability before contract approval;
- unified status projection for the archived route and exact external dependency;
- deterministic registered-output replay with zero workload;
- latest-completed summary precedence for the new route.

## Validation

- Source bytes and frozen-contract digest: verified.
- Real registered-parent artifact build: verified.
- Exact durable additive migration dry-run: 69 to 70 tasks, one revised task, one new task, zero state regressions, zero fact deletions, and zero unallowlisted definition rewrites.
- Focused route-decision tests: 6 passed.
- Full Prediction v2 structural chain plus mainline Supervisor regressions: 94 passed.
- Full worker regression: 2,270 passed, 4 skipped, and the unchanged 42 failures confined to deliberately retired legacy training, old three-line, old forward-evaluation/mail, and related legacy entrypoints; no new failure remains.

## Mainline integration matrix

| Link | Round 81 implementation state |
| --- | --- |
| Goal → Resolver | source DAG binds the route task to `M4_INFORMATION_THEORY_EVIDENCE` |
| Resolver → Ready Queue | exact 69→70 additive migration dry-run verified |
| Ready Queue → Supervisor | singular capability registered and latest-summary precedence added |
| Supervisor → Capability | zero-work implementation and real parent validation verified |
| Capability → Artifacts | deterministic decision, intake handoff, completion, and execution defined |
| Artifacts → Status | archive state and external-wait intake projected |
| Status → Next Task | exact result-blind research-intake task and external event defined |
| Deterministic replay | zero-work registered-content reconstruction defined and tested |
| Merged-main durable execution | pending PR merge and separate Operator Request |

Final integration answer for this implementation round: **NO — INTEGRATION_PENDING**. Completion requires the ready PR to merge, followed by a fresh merged-main Supervisor execution, deterministic replay, and durable external-wait status verification.
