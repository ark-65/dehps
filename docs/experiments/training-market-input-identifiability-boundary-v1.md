# Training Market-Input Identifiability Boundary v1

## Primary Goal

Make the red-ball training input boundary fail closed so aggregate market observations cannot silently enter draw-probability scoring, advisors, objective selection, search navigation, or promotion.

## Non-Goals

- Do not add sales, jackpot, prize-tier, regional-winner, or ticket-count data to the prediction model.
- Do not infer individual or combination-level betting popularity from aggregate winner counts.
- Do not create a fourth draw-prediction line or change any existing weight, candidate source, objective, or promotion rule.
- Do not claim that market aggregates predict the physical draw.

## Task Frame

The user identified the missing observation that makes a proposed popularity model underdetermined: public draw reports do not expose which exact combinations each ticket purchased. The current repository stores only draw outcomes in `ssq_history`, and the supervisor loads only `issue`, `draw_date`, and `red_numbers`; however, that isolation was implicit. Progress means turning it into an executable contract that stops training before expensive computation if a market aggregate or ambiguous record shape enters the draw-prediction surface.

## Historical Boundary

Gauss and Riemann are used as historically inspired verification and structural lenses, not literal minds or complete reconstructions.

- Canonical issue: `2026078`.
- Legal red-ball universe: `1,107,568`; ranked universe: `1,105,506`.
- Historical mode: expanding, 900-train, 100-evaluation, current ten-year regime.
- Search/frozen split: 80/20; frozen validation remains promotion-only and quarantined.
- Forward paired evidence remains `0/20` before this round.

## Gauss Pass: Verification

Strongest claim: the live `ssq_history` schema contains draw identifiers, dates, realized balls, source metadata, and timestamps, but no sales amount, jackpot, prize-tier count, winner-count, betting-density, or ticket-distribution column. The dated history loaders select exactly `issue`, `draw_date`, and `red_numbers`.

Weakest assumption: a field-name and record-shape allowlist catches every future semantic alias. It is a fail-closed code boundary for declared inputs, not a proof that an intentionally mislabeled field is harmless.

Test requested from the structural lens: show that market aggregates can remain visible in a separate storage/observation space while the prediction projection excludes them, and that exclusion has no selection or promotion side effect.

Historical boundary note: exact projection checks, counterexamples, and identifiability proof obligations are Gauss-inspired verification disciplines, not historical authority for a modern data pipeline.

## Riemann Pass: Structure

Strongest claim: realized draw outcomes and population betting behavior are observations on different data spaces. Prize-tier counts are a many-to-one aggregate projection of hidden tickets, so they cannot be continued back to a unique ticket-level combination distribution without additional observations and assumptions.

Weakest assumption: keeping market data observation-only is sufficient for every future research use. A separate market-risk model may eventually be valid, but only with an explicit target, provenance, identifiability analysis, and no write path into draw probability.

Test requested from the arithmetic lens: construct two different ticket populations compatible with the same aggregate winner counts; this counterexample proves non-uniqueness and prevents combination-popularity claims from aggregate counts alone.

Historical boundary note: data-space and many-to-one projection language is a Riemann-inspired modern reconstruction, not a claim about Riemann's historical formalism.

## Cross-Review

- Gauss accepts the structural split only because the actual SQL projection, database catalog, record shapes, and startup behavior are measurable.
- Riemann accepts the allowlist only because it represents a real separation of spaces rather than a warning string attached after training.
- Gauss requires a blocked startup when any extra or market field is selected or a history tuple gains an ambiguous component.
- Riemann requires market aggregates to remain a separate observation-only surface even if those columns become available later.

## Disagreement

Field names cannot prove semantic provenance. The executable boundary prevents accidental wiring and creates an audit point, but deliberate relabeling still requires code review and provenance tests. Both lenses therefore reject any claim that this mechanism alone certifies all future features.

## Implementation

- Add `dehps-draw-outcome-input-boundary-v1` with an exact three-field prediction allowlist.
- Validate every dated history record before the supervisor builds the ranked universe.
- Treat sales, jackpot, market, prize, ticket, wager, and winner fields as market aggregates; they may be available but must remain excluded.
- Block supervisor startup on missing required fields, unexpected selected fields, selected market aggregates, empty history, or ambiguous/invalid record shapes.
- Publish the boundary, non-identifiability statement, selection status, and promotion status in compact JSON and the supervisor report.
- Make the dated PostgreSQL loader use the shared allowlist and expose catalog columns for the runtime audit.
- Require the same boundary in the scheduled self-iteration prompt.

## Falsification

Reject the change if a market aggregate can enter the selected training projection without a blocked startup; if a four-element history record is accepted; if the boundary runs only after ranking begins; if availability alone blocks a separately stored market field; or if the audit changes candidate selection, objective, search base, frozen validation, or promotion.

## Validation

- Input-boundary, PostgreSQL, and supervisor targeted suites: `190 passed`.
- Full worker suite: `518 passed`.
- Python compilation, shell syntax, and `git diff --check` passed.

## Live Verification

Fresh final-code supervisor `20260711-124741`, PID `3545400`, started after syncing issue `2026078` with zero inserts, updates, or conflicts. Before universe construction, it logged `prediction_input_boundary=passed`, fields `issue/draw_date/red_numbers`, no selected market aggregates, and `ticket_distribution_observed=false`. The static universe and cached ranked matrix then loaded normally.

Durable round 1 preserved the passed boundary over 1,498 three-field history records with zero invalid records, missing fields, unexpected fields, or selected market aggregates. The static line remained `[3,3,3]`, candidate space remained diverse, strategy memory stayed on `null_model_forward_audit`, and no selection or promotion state changed.

Durable round 2 preserved the same passed boundary and static `[3,3,3]` result. Current candidates remained diverse with `10/10` unique Top-10 rank signatures while the historical round-best path remained explicitly stale. The database-backed watch reported `target_complete_round_recorded`, all advisor signals current for their declared scopes, zero search/frozen overlap, passed prefilter isolation, no frozen use by search, historical holdout quarantine still active, and forward evidence still incomplete at `0/20`. Promotion remained disabled; no market field affected draw probability, candidate selection, objective, search base, or promotion.

## Synthesis

The current system was not using market aggregates, but the boundary was implicit and therefore fragile. The smallest shared conclusion is an enforceable negative capability: aggregate prize and sales observations cannot become draw-prediction evidence by accident, and their inability to identify hidden ticket selections is explicit in runtime state.

## Next Verification

Complete at least two durable rounds and confirm candidate diversity, advisor freshness, holdout isolation, null/forward status, and promotion quarantine are unchanged. Any future market-risk research must use a separate dataset and target, and cannot feed draw probability without a new reviewed protocol.
