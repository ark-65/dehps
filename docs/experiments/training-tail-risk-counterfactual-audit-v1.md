# Training Tail-Risk Counterfactual Audit v1

## Primary Goal

Measure whether the repeatedly selected local champion depends on the `tail_risk_penalty` contribution by removing only that contribution from a copied sort tuple, without changing production sorting, search-base selection, promotion, weights, budgets, or candidate generation.

## Non-Goals

- Do not remove or rescale tail risk in the production objective.
- Do not select the counterfactual Top as a search base or prediction line.
- Do not use frozen validation to compute or order the counterfactual.
- Do not claim that a counterfactual flip predicts future lottery outcomes.

## Task Frame

The component-residual audit predeclared an eight-round maturity window before any counterfactual. Run `20260711-103801` completed that window with 32 exact objective-first comparisons. `tail_risk_penalty` was the largest absolute component delta in 26/32 comparisons and in at least 3/4 comparisons in every round; `red5_reward` led the remaining 6/32. Progress in this round means measuring the local ordering sensitivity to tail risk while proving that the production path is unchanged.

## Historical Boundary

Gauss and Riemann are used below as historically inspired verification and structural lenses, not literal minds or complete reconstructions.

- Canonical issue: `2026078`.
- Legal red-ball sample space: `1,107,568`; ranked universe: `1,105,506`.
- Historical mode: expanding, 900-train, 100-evaluation, current ten-year regime.
- Search/frozen split: 80/20; counterfactual scope: search slice only.
- Historical holdout remains quarantined; paired forward evidence remains `0/20`.

## Gauss Pass: Verification

Strongest claim: the mature 8-round/32-comparison baseline had exact component reconstruction, zero missing fields, zero mismatches, maximum residual `0.0`, and tail-risk dominance `26/32`. In the two fresh counterfactual rounds, subtracting only the direction-normalized tail-risk contribution changed the copied local Top and flipped 3/4 challengers each time.

Weakest assumption: the persisted Top5 is a sufficient local neighborhood. The counterfactual exactly answers a local ordering question but cannot identify how an altered production objective would change future candidate generation or outcomes.

Test requested from the structural lens: distinguish a local coordinate sensitivity from a globally better objective, and preserve candidate/search geometry as an unresolved boundary.

Historical boundary note: exact residual reconstruction and single-variable control are Gauss-inspired verification disciplines, not authority for changing a modern model.

## Riemann Pass: Structure

Strongest claim: tail risk acts as a decisive local chart coordinate. Removing it exposes a neighboring branch (`53da...`) that is hidden by the production scalar objective even though the current candidate space remains diverse.

Weakest assumption: the newly visible branch is meaningful outside this historical chart. It may be another overfit path, and its geometry is not validated by frozen or forward outcomes.

Test requested from the arithmetic lens: prove that the copied counterfactual changes no production summary, sort key, search base, or promotion field.

Historical boundary note: chart and branch language is a Riemann-inspired modern reconstruction, not a claim about Riemann's own formal machinery.

## Cross-Review

- Gauss accepts the control because it changes one predeclared component in a copied tuple and exposes exact production/component/counterfactual gaps.
- Riemann accepts only the local structural conclusion: the stale champion is sensitive to tail-risk geometry.
- Gauss rejects promotion because forward evidence is `0/20` and the frozen set is quarantined.
- Riemann rejects replacing the production chart because the counterfactual branch has no global or future validation.

## Disagreement

Gauss would require a registered forward comparison before considering any objective experiment. Riemann would also want candidate-space trajectories generated under the alternative chart. Both agree that neither should be attempted automatically from this historical counterfactual.

## Implementation

`run_training_supervisor.py` now builds an observation-only counterfactual after component reconstruction passes:

- it copies each production sort tuple;
- removes only the `tail_risk_penalty` contribution from the objective coordinate;
- preserves all other production sort fields;
- records production and counterfactual Top hashes, flip/retain/tie counts, and per-challenger gaps;
- explicitly persists `selection_changed=false`, `selection_scope=search_slice_only`, and `selection_uses_frozen_validation=false`.

Strategy memory advances to `tail_risk_counterfactual_audit` but keeps `promotion_allowed=false`. The hourly self-iteration checklist forbids feeding the counterfactual Top into production ordering, search, promotion, or prediction output.

## Live Verification

Old supervisor `20260711-103801` was stopped only after durable round 10. Fresh supervisor `20260711-112847`, PID `3461721`, then completed two durable rounds from updated code.

Both rounds reported:

- production Top: `91052aa056bf4554f0b25bc952deb2c0e6a82c4387a52b6b0736142495ab706f`;
- counterfactual Top: `53da5fd781ee7cc634504c328337a4838bd077026fbe795ef77c4b66f3bb81eb`;
- `counterfactual_top_changed=true`;
- challenger flips / baseline retained / ties: `3 / 1 / 0`;
- diagnostic selection changed: `false`;
- frozen validation used: `false`.

Production search bases were instead `a1189bcf...` and `24a408e4...`, selected by the existing holdout-isolated navigation path. Neither equals the counterfactual Top, which confirms that the control did not write back into search.

Static exact Top100/1000/10000 remained `[3,3,3]`, Dynamic KDJ `[2,3,3]`, and Near Dynamic KDJ `[0,0,0]`. Advisors were current through `2026078`; parser/sync/duplicate checks passed; 80/20 holdout overlap was zero; prefilter isolation passed with zero frozen/outside overlap; promotion remained quarantined without bypass; forward evidence remained `0/20`.

## Falsification

Reject the control if the selected component is not predeclared, reward reconstruction is incomplete, a copied tuple is not used, any production summary mutates, or counterfactual state influences search/promotion. Reject any claim that tail-risk removal is beneficial unless a separate registered protocol produces genuinely forward paired evidence and preserves null, leakage, duplicate, and quarantine boundaries.

## Validation

- Supervisor and self-diagnostics suites: `167 passed`.
- Full worker suite: `505 passed`.
- Python compilation, shell syntax, and `git diff --check` passed.
- Two fresh durable live rounds completed without runtime or leakage errors.

## Synthesis

The stale local champion is mechanically sensitive to the tail-risk term in the implemented historical ordering: removing that single contribution flips the copied Top in both observed rounds. This is an objective-sensitivity diagnosis, not evidence that the counterfactual candidate predicts better and not permission to change the production objective.

## Next Verification

Keep the counterfactual observation-only while accumulating genuinely forward paired issues. Do not open a production objective experiment from repeated historical rounds alone. A future human-reviewed experiment would need a predeclared forward comparison, unchanged candidate budget and isolation protocol, and explicit rollback if frozen/forward performance or tail safety degrades.
