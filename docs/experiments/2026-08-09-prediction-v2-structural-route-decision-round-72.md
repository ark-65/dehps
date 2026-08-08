# Prediction v2 Structural Route Decision — Round 72

## Task frame

- Goal: `M4_INFORMATION_THEORY_EVIDENCE`
- Task: `prediction-v2-structural-route-decision`
- Primary objective: assign the replay-verified B176 structural portfolio a bounded, transparent role without treating structural construction quality as predictive usefulness.
- Non-goals: no new optimizer, comparator, historical measurement, model, Evidence, activation, promotion, P3 authorization, or production action.
- Upstream identities: the registered structural evaluation execution plus its decision, route handoff, and completion artifact.
- Downstream consumer: `prediction-v2-structural-baseline-comparison-preregistration`.

## Frozen evidence boundary

The only positive result available to this decision is:

`SUPPORTED_AT_FROZEN_B176_AGAINST_UNIFORM_RANDOM_ONLY`

At B=176, the selected portfolio was structurally better than all 4,096 frozen uniform-random samples under the registered comparison. This remains descriptive evidence for the fixed optimizer against that single weak comparator. It is not a calibrated p-value, global-optimality result, predictive probability, decision-usefulness result, or activation authorization. Historical predictive Evidence remains `INCONCLUSIVE`.

## Einstein review

The smallest defensible conclusion is that the registered optimizer constructs an unusually balanced offline portfolio relative to uniform random at the frozen budget. The falsifying check for an operational role is a result-blind comparison against stronger simple, same-budget, label-symmetric, transparent baselines with complexity accounted for. Because that check has not been preregistered or executed, the present artifact cannot be activated.

## Gauss–Riemann cross-review

Gauss pass:

- The finite-design ideals, selected statistics, comparator count, and four registered upstream identities are fixed.
- The uniform comparator does not establish superiority to simple structured alternatives.
- No additional sampling or arithmetic is required for this route decision.

Riemann pass:

- The portfolio has a coherent role as a structural diversification reference, not as a probability model.
- The next meaningful comparison space must preserve budget and label symmetry and expose the effect of comparator complexity.
- Moving directly from uniform-random dominance to operational use would cross an unjustified structural-to-predictive boundary.

Shared conclusion:

`ROUTE_TO_NON_PREDICTIVE_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION`

The artifact role is:

`OFFLINE_STRUCTURAL_DIVERSIFICATION_REFERENCE_ONLY`

Archive condition:

If a result-blind preregistration cannot freeze stronger simple same-budget label-symmetric baselines and an observed-result-independent failure rule, archive the portfolio as engineering evidence only.

## Engineering implementation

The route capability:

- reads only the four registered evaluation artifacts plus its frozen source contract;
- performs no historical database query, fold, bootstrap child, optimizer proposal, or null replicate;
- emits exactly three immutable children: route decision, baseline-comparison preregistration handoff, and completion;
- registers those children plus the unified mainline execution;
- projects the next Ready task through unified status;
- deterministically reconstructs the same registered content during replay;
- does not add a second-pass repetition or uniqueness scan.

The additive manifest migration revises the existing route placeholder, adds only `prediction-v2-structural-baseline-comparison-preregistration`, and preserves all prior state and facts.

## Validation

- Targeted Python suite: `83 passed`.
- Formatting and linting: passed for every touched Python surface.
- Direct registered-parent build: passed against the durable evaluation execution and its three registered children; replay reported `REPLAY_VERIFIED` with zero workload.
- Full worker suite: `2,249 passed, 4 skipped, 42 failed`. All 42 failures are on intentionally retired legacy prediction/training/mail paths and fail at `legacy_prediction_line_retired:*`; none touches this round's route capability. They are reported rather than bypassing the retirement guard or weakening legacy tests in this round.
- Live merged-main Supervisor execution: pending PR merge.

## Integration matrix

| Mainline link | State before merged-main operation |
| --- | --- |
| Goal | bound |
| Resolver | implemented; live migration pending |
| Ready Queue | implemented; live migration pending |
| Supervisor | implemented and locally tested |
| Capability | code complete |
| Immutable artifacts | deterministic local construction verified |
| Status projection | implemented and tested |
| Next task | declared as baseline-comparison preregistration |
| Replay | locally verified; durable merged-main replay pending |

Integration answer at PR publication: **NO — INTEGRATION_PENDING**.

The answer may become **YES — validated by unified mainline execution and replay** only after the ready PR is merged, the additive migration is imported into the durable control plane, a fresh merged-main Supervisor completes the task, and deterministic replay verifies the registered identities.
