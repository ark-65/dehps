# Training Null Family-Wise Audit v1

## Primary Goal

Replace the selected training line's unadjusted null-tail interpretation with a conservative Bonferroni adjustment over the minimum observable family: every unique fully evaluated configuration and every reported Top band in the current round.

## Non-Goals

- Do not change the objective, sort key, candidate generation, source budgets, search navigation, or promotion gate.
- Do not claim that Bonferroni adjustment solves adaptive sequential-search multiplicity.
- Do not use frozen validation to select a candidate or compute the search-slice null statistic.
- Do not treat a historically small adjusted p-value as forward predictive evidence.

## Task Frame

Run `20260711-112847` completed four durable rounds with current advisors, exact legal-universe checks, zero search/frozen overlap, passed prefilter isolation, a diverse current Top10, and continued promotion quarantine. Its `signal_vs_noise` diagnostic nevertheless exposed only raw binomial tail probabilities and explicitly reported `multiple_testing_unadjusted`, even though each round selected from multiple evaluated configurations and reported three nested Top bands. Progress means making that minimum observed selection family explicit and using its adjusted probability for diagnostic status.

## Historical Boundary

Gauss and Riemann are used as historically inspired verification and structural lenses, not literal minds or complete reconstructions.

- Canonical issue: `2026078`.
- Legal red-ball universe: `1,107,568`; ranked universe: `1,105,506`.
- Historical mode: expanding, 900-train, 100-evaluation, current ten-year regime.
- Search/frozen split: 80/20; frozen validation remains promotion-only and quarantined.
- Forward paired evidence: `0/20`; one complete pending snapshot exists for `2026079`.

## Gauss Pass: Verification

Strongest claim: a selected round-best p-value must account for at least the unique configurations actually compared and the three Top bands actually reported. Bonferroni gives a valid family-wise upper bound without assuming independence between the nested bands.

Weakest assumption: the current round is the whole selection family. It is not; prior adaptive rounds, advisor tuning, source generation, and repeated objective changes create a larger and partly unrecorded family.

Test requested from the structural lens: verify that the reported family is labeled a minimum observed family and cannot be confused with complete sequential-search correction.

Historical boundary note: exact counting and conservative error bounds are Gauss-inspired disciplines, not historical authority for a modern training decision.

## Riemann Pass: Structure

Strongest claim: the raw p-value is local to one selected coordinate chart, while the training process traverses a larger adaptive path of candidate configurations and bands. The diagnostic should expose both the local family and the unresolved global path.

Weakest assumption: multiplying current unique configurations by reported bands captures enough geometry to describe the search. It only describes the smallest directly observed layer.

Test requested from the arithmetic lens: prove that duplicate summaries do not inflate the candidate count, the adjusted value is bounded by one, and status uses the adjusted rather than raw value.

Historical boundary note: chart and path language is a Riemann-inspired modern reconstruction, not a claim about Riemann's own formal toolkit.

## Cross-Review

- Gauss accepts Bonferroni because it remains valid under the dependence of nested Top bands and has a directly countable family.
- Riemann accepts it only when named `bonferroni_minimum_observed_family` and paired with `sequential_search_multiplicity_counted=false`.
- Gauss rejects using the raw p-value for `candidate_signal` after candidate selection.
- Riemann rejects presenting the new adjusted value as global evidence across the adaptive search trajectory.

## Disagreement

The full sequential family size is unresolved. A literal count of every generated configuration would overstate independence yet still miss adaptive choice, while a single-round count understates the path. Both lenses accept the current change only as a conservative minimum-family guardrail with frozen and forward evidence still mandatory.

## Implementation

`signal_vs_noise_diagnostic` now:

- accepts the unique fully evaluated configuration count for the current round;
- multiplies that count by the three reported Top bands;
- records raw and Bonferroni-adjusted tail probabilities for every band;
- uses the adjusted probability for the `candidate_signal` threshold;
- persists the family method, family size, per-test alpha, and the explicit fact that sequential multiplicity remains uncounted.

`training_round_self_diagnostics` deduplicates evaluated summaries by configuration hash before passing the count. The generic single-line diagnostic still counts one candidate and three bands. The hourly self-iteration checklist now forbids raw-p-value signal claims.

## Falsification

Reject this implementation if duplicate summaries inflate the configuration family, adjusted values exceed one, status still reads the raw probability, the live family size differs from `unique evaluated configurations × 3`, or any selection/promotion field changes because of the diagnostic. Reject any broader statistical claim until adaptive sequential-search multiplicity has a separately registered protocol.

## Validation

- Supervisor and self-diagnostics suites: `168 passed`.
- Full worker suite: `506 passed`.
- Python compilation, shell syntax, and `git diff --check` passed.

## Live Verification

Fresh supervisor `20260711-115338`, PID `3487713`, started from the updated branch after syncing issue `2026078` with zero inserts, updates, or conflicts.

Durable round 1 fully evaluated 16 unique configurations and therefore reported a minimum family of `16 × 3 = 48` hypotheses. For the selected static line:

- raw / adjusted Top100 tail probability: `0.0000000605 / 0.0000029037`;
- raw / adjusted Top1000 tail probability: `0.0000577194 / 0.0027705306`;
- raw / adjusted Top10000 tail probability: `0.0363443352 / 1.0`;
- `sequential_search_multiplicity_counted=false`;
- signal status remained `noise_risk` because the eval-slice overfit guard was active and forward evaluations remained zero.

Durable round 2 fully evaluated 19 unique configurations and reported a minimum family of `19 × 3 = 57`. Its adjusted Top100, Top1000, and Top10000 probabilities were `0.0000034481`, `0.003290005`, and `1.0`. The signal remained `noise_risk`; the round synthesis remained blocked by the existing promotion and overfit guardrails.

Across both rounds, the current candidate space remained `diverse` with 10/10 distinct Top rank signatures. Search/frozen overlap remained zero, prefilter isolation passed, parser/sync/duplicate checks passed, promotion remained quarantined without bypass, forward paired evidence remained `0/20`, and both rounds completed without runtime errors. The supervisor remains active.

## Synthesis

The prior null diagnostic was under-corrected for the selection that was visibly performed in each round. The new value is a stronger local guardrail, but it remains a lower bound rather than a full solution to adaptive search multiplicity and cannot release promotion quarantine.

## Next Verification

Keep the minimum-family adjustment as an interpretation guard while the forward snapshot for `2026079` remains pending. A later round may register a sequential-search correction protocol, but it must not invent an independence count from adaptive historical trials or weaken the frozen/forward quarantine.
