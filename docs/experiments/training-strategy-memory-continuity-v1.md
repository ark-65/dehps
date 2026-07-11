# Training Strategy-Memory Continuity v1

## Primary Goal

Preserve same-history self-diagnostic progress across supervisor restarts so a completed observation-only audit can leave the strategy queue instead of restarting from round one forever.

## Non-Goals

- Do not carry historical metrics across a changed issue, history fingerprint, train mode, window, or Top-N.
- Do not use recovered diagnostics for candidate generation, ranking, search-base selection, or promotion.
- Do not change the production objective or select the tail-risk counterfactual Top.
- Do not treat audit maturity as predictive evidence.

## Task Frame

The supervisor already persists each durable round's `self_diagnostics` inside `training_round_results.prefilter`. Search and stagnation guards recover same-history state across restarts, but `build_specialist_strategy_memory` received only current-run rounds. Because accepted code changes require a fresh supervisor, the tail-risk counterfactual audit repeatedly reset its visible progress and could never have a principled exit. Progress means recovering only the already filtered same-history diagnostic records, proving they cannot affect production selection, and advancing after a predeclared eight safe measurements.

## Historical Boundary

Gauss and Riemann are used as historically inspired verification and structural lenses, not literal minds or complete reconstructions.

- Canonical issue: `2026078`.
- Legal red-ball universe: `1,107,568`; ranked universe: `1,105,506`.
- Historical mode: expanding, 900-train, 100-evaluation, current ten-year regime.
- Search/frozen split: 80/20; frozen validation remains promotion-only and quarantined.
- Forward paired evidence remains `0/20`.

## Gauss Pass: Verification

Strongest claim: before this change, seven recent same-history durable records already contained `objective_component_counterfactual.status=measured`; every record had `selection_changed=false` and `selection_uses_frozen_validation=false`, while current strategy memory reported only three measured rounds.

Weakest assumption: eight observations are sufficient to close an observation window. They establish operational stability of the diagnostic and its non-writeback guard, not predictive validity or a superior objective.

Test requested from the structural lens: verify that restart boundaries, rather than model evidence, caused the audit-progress reset and that recovery is scoped to the exact same historical surface.

Historical boundary note: exact persisted-state accounting and proof obligations are Gauss-inspired disciplines, not historical authority for a modern training system.

## Riemann Pass: Structure

Strongest claim: one logical training trajectory was being represented as disconnected run-local charts. The database already provides transition-compatible coordinates through the shared issue, history fingerprint, train mode, windows, and Top-N.

Weakest assumption: all relevant audit state is contained in `self_diagnostics`. This change deliberately carries only diagnostic observations and does not claim full optimizer-state continuity.

Test requested from the arithmetic lens: recover newest persisted records, restore chronological order, exclude the current run, reject legacy protocols, and prove that recovered state remains read-only.

Historical boundary note: chart and trajectory language is a Riemann-inspired modern reconstruction, not a claim about Riemann's historical formalism.

## Cross-Review

- Gauss accepts recovery because the database query already enforces identical issue, fingerprint, train mode, train/eval windows, and Top-N.
- Riemann accepts it because restart boundaries no longer erase one logical diagnostic trajectory.
- Gauss requires eight measured rounds with zero component, scope, selection, or frozen-use violations.
- Riemann requires maturity to advance only the diagnostic queue, never the production search path.

## Disagreement

Eight rounds are an operational review threshold, not a statistical proof threshold. Both lenses accept it only because the outcome is “stop repeating this audit and inspect the next unresolved guardrail,” not “promote a model” or “change the objective.”

## Implementation

- Recover up to eight persisted same-history `dehps-self-diagnostics-v1` records at supervisor startup.
- Exclude the current run and restore chronological order.
- Publish source run ids, oldest/latest record, and explicit no-selection/no-frozen semantics as `strategy_memory_continuity`.
- Combine recovered observations with current-run rounds only inside strategy memory.
- Track an eight-round tail-risk observation window with component, scope, production-selection, and frozen-use guards.
- Mark the window `mature` only when eight measurements are present and every guard violation count is zero.
- On maturity, leave the already completed decision-surface audit and advance to the next unresolved `null_model_forward_audit`.
- If any recovered measurement violates the guard, select a dedicated repair audit and keep promotion disabled.

## Falsification

Reject the change if a different history surface is recovered, the current run is duplicated, chronological order is reversed, legacy diagnostics count toward maturity, any counterfactual observation changed production selection or used frozen data, or maturity changes search/ranking/promotion. Reject any predictive interpretation while forward paired evidence is incomplete.

## Validation

- Supervisor and self-diagnostics targeted suites: `172 passed`.
- Full worker suite: `510 passed`.
- Python compilation, shell syntax, and `git diff --check` passed.

## Live Verification

Fresh supervisor `20260711-121533`, PID `3509956`, started from the updated branch after syncing issue `2026078` with zero inserts, updates, or conflicts. Startup recovered eight same-history diagnostic records in chronological order from runs `20260711-103801`, `20260711-112847`, and `20260711-115338`; seven contain safe measured tail-risk counterfactuals, while the oldest predates that diagnostic. The current run was explicitly excluded. Durable round evidence is recorded below after completion.

Durable round 1 recorded the eighth safe measurement. The observation window became `mature` with `measured_round_count=8`, `remaining_round_count=0`, and zero component, selection, scope, or frozen-use violations. Strategy memory dropped both `decision_surface_stale_champion` and `tail_risk_counterfactual_needs_stability`, then advanced to `null_model_forward_audit` with `promotion_allowed=false`. The persisted production counterfactual still reported `selection_changed=false`, search-only scope, and no frozen use.

Durable round 2 preserved the same mature `8/8` observation window with zero guard violations and kept `null_model_forward_audit`; maturity did not write back into search or promotion. Both durable rounds retained a diverse candidate space with `10/10` unique Top-10 rank signatures, `selection_changed=false`, and `selection_uses_frozen_validation=false`. The database-backed training watch also reported all four advisors current for their declared issue scopes, zero frozen-holdout overlap, passed prefilter isolation, historical holdout quarantine still active, and forward evidence still incomplete at `0/20`.

## Synthesis

The soft stall was partly an orchestration-state bug: computation and diagnostic persistence continued, but the strategy layer forgot its progress at every required restart. Same-history read-only continuity makes the audit queue finite without weakening any prediction or promotion boundary.

## Next Verification

After two live rounds, keep the supervisor running and wait for genuinely forward issue `2026079`. Do not turn null/forward audit maturity into automatic quarantine release.
