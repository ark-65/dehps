# Target Weight Inversion Self-Iteration V0

## Summary

This stage defines the scientific boundary and acceptance points for target weight inversion self-iteration. The loop records how the current base configuration ranks known historical target issues, then asks a narrower question: for targets that miss Top10000, what is the smallest bounded weight shift that would move the historical target inside the inspection window?

The output is an advisor source for the next round. It is not a prediction claim and must not be promoted into default training behavior until it survives a full 100-issue regression plus frozen validation and control experiments.

## Per-Target Evidence

For every target issue in the 100-issue evaluation window, persist the base-run evidence:

- `current_rank`: rank of the true target under the unchanged base config.
- `hit_top10000`: whether `current_rank <= 10000`.
- `score`: scoring value assigned to the target combination.
- `rank_margin`: distance to the Top10000 boundary, preserving whether the target is already inside or outside.
- `base_config_hash`: stable hash of the exact base config used for this target issue.

These fields are evidence, not labels for claiming future signal.

## Bounded Inversion For Misses

Only target issues that do not enter Top10000 are eligible for inversion. For each miss, attempt the smallest bounded weight offset that improves the historical target into Top10000 while respecting the configured field bounds.

Record the inversion result with:

- `required_delta_config`: minimal candidate weight delta that was tested.
- `adjusted_rank`: rank after applying the bounded delta.
- `delta_norm`: normalized size of the total weight movement.
- `changed_fields`: weight fields that changed from the base config.
- `success`: whether the adjusted rank entered Top10000.
- `outlier_reason`: explicit reason when no acceptable bounded delta exists, such as bound exhaustion, unstable objective, excessive field count, or rank still outside Top10000.

Failures stay in the dataset. Dropping hard misses would bias the next advisor candidate.

## 100-Issue Aggregation

After the 100 target issues finish, aggregate successful and failed inversion evidence into candidate deltas for the next training round:

- `mean_delta`: simple average over eligible bounded deltas.
- `median_delta`: per-field median to reduce sensitivity to individual targets.
- `trimmed_delta`: trimmed mean after removing the largest delta-norm tails.
- `weighted_delta`: rank-margin-weighted proposal that emphasizes near-boundary misses without hiding outliers.
- `micro_delta`: small conservative step in the dominant stable direction.
- `stable_delta`: fields whose sign and magnitude remain stable across adjacent windows or bootstrap slices.

The next-round candidate should include provenance: source window, base config hash set, aggregation method, number of successes, number of failures, and outlier distribution.

## Scientific Boundary

Target weight inversion is a historical sensitivity probe. It answers whether small bounded config changes can retrospectively move known targets into the Top10000 inspection set. It does not prove the adjusted weights can predict unseen lottery draws.

Candidate deltas may only be consumed as an advisor source. Before promotion, each candidate must pass:

- a complete next-round 100-issue regression;
- frozen validation against the existing frozen baseline;
- same-budget null/control experiments;
- leakage checks confirming the target issue was not used to tune its own forward evaluation;
- stability checks across adjacent historical windows.

Any report or UI copy should describe the result as candidate guidance, response-surface evidence, or advisor input. It must not describe it as predictive power, draw forecasting, or guaranteed rank improvement.

## Acceptance Checklist

- Each evaluated target issue records `current_rank`, `hit_top10000`, `score`, `rank_margin`, and `base_config_hash`.
- Missed targets record bounded inversion fields: `required_delta_config`, `adjusted_rank`, `delta_norm`, `changed_fields`, `success`, and `outlier_reason`.
- The 100-issue report includes mean, median, trimmed, weighted, micro, and stable delta candidates.
- Candidate metadata includes source window, config hashes, success/failure counts, and outlier summary.
- Advisor consumption is opt-in and leaves the base training path unchanged by default.
- Next-round acceptance requires full 100-issue regression plus frozen validation and control experiments.
- The final report states that the artifact is not evidence of prediction ability unless those gates are passed.
- Tests or smoke checks verify schema/write coverage, aggregation determinism, bounded-delta constraints, and no behavioral change when the advisor source is disabled.
