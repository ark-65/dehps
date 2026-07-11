# Training Sequential Null Ledger v1

## Primary Goal

Replace the run-local null interpretation with a persisted same-history lower-bound ledger so repeated adaptive rounds cannot keep presenting a small local p-value as if only the current round had been searched.

## Non-Goals

- Do not claim a complete correction for data-adaptive hypothesis generation.
- Do not infer independence between candidates, nested Top bands, or rounds.
- Do not change candidate generation, weights, objective, search navigation, frozen validation, or promotion.
- Do not convert historical significance into predictive or betting evidence.

## Task Frame

The strategy queue has advanced to `null_model_forward_audit`. The current diagnostic adjusts each selected round-best over the unique fully evaluated configurations and three reported Top bands in that round, but explicitly leaves `sequential_search_multiplicity_counted=false`. The same historical surface has been searched for hundreds of durable rounds. Progress means counting the exact candidate-by-band family exposed by persisted diagnostics across runs, using that larger family for an additional Bonferroni bound, and refusing `candidate_signal` while legacy rounds or adaptive hypothesis generation remain outside the ledger.

## Historical Boundary

Gauss and Riemann are used as historically inspired verification and structural lenses, not literal minds or complete reconstructions.

- Canonical issue: `2026078`.
- Legal red-ball universe: `1,107,568`; ranked universe: `1,105,506`.
- Historical mode: expanding, 900-train, 100-evaluation, current ten-year regime.
- Search/frozen split: 80/20; frozen validation remains promotion-only and quarantined.
- Forward paired evidence remains `0/20` before this round.

## Gauss Pass: Verification

Strongest claim: the database initially contained 306 same-history durable rounds across 33 runs. Twelve rounds exposed a valid candidate-hypothesis count, summing to 217 candidate tests; over three reported Top bands this is an exactly observed family of 651 tests. The other 294 legacy rounds are not reconstructable from persisted diagnostics.

Weakest assumption: counting each candidate-band evaluation once is a sufficient description of the adaptive procedure. It is not. Bonferroni remains valid for the counted observed tests without independence, but the uncounted legacy path and outcome-dependent generation make 651 only a lower bound on the relevant family.

Test requested from the structural lens: verify that restarts remain on one same-history statistical path, that the ledger grows monotonically with durable rounds, and that run boundaries cannot reset the count.

Historical boundary note: exact test counting, union bounds, and proof obligations are Gauss-inspired disciplines, not historical authority for a modern adaptive optimizer.

## Riemann Pass: Structure

Strongest claim: the current-round p-value is local to one chart while supervisor restarts and rounds form one global adaptive trajectory on the same data surface. A persisted ledger supplies a transition-compatible coordinate for the observed portion of that path.

Weakest assumption: the durable database is the entire search space. Candidate generators use the same outcomes to choose later hypotheses, and older rounds predate the diagnostic, so the global path still has singular missing regions.

Test requested from the arithmetic lens: prove the ledger uses the exact same issue, history fingerprint, mode, windows, and Top-N; excludes the new run at startup; and reports legacy and adaptive omissions rather than filling them with an invented multiplier.

Historical boundary note: chart, path, and singular-region language is a Riemann-inspired modern reconstruction, not a claim about Riemann's historical formalism.

## Cross-Review

- Gauss accepts the persisted count because it is queried from durable same-history records and does not assume independence.
- Riemann accepts it because supervisor restarts no longer reset the statistical path to a fresh local chart.
- Gauss requires separate current-round and observed-sequential adjusted p-values plus exact integer family counts.
- Riemann requires the ledger to expose missing legacy regions and adaptive generation as unresolved, global obstructions.

## Disagreement

The observed family is not the complete adaptive family. Summing durable candidate counts is deliberately conservative for the tests it includes, but it cannot repair hypotheses generated after repeatedly observing the same evaluation outcomes. Both lenses therefore require `sequential_search_multiplicity_counted=false`, `adaptive_hypothesis_generation_counted=false`, and `noise_risk` until genuinely frozen or forward evidence exists.

## Implementation

- Aggregate all same-history durable rounds from PostgreSQL, not the 80-row navigation window.
- Count only `dehps-self-diagnostics-v1` rows with a valid positive candidate-hypothesis count.
- Persist total rounds, observed diagnostic rounds, legacy uncounted rounds, candidate tests, and candidate×band family size.
- Extend the startup ledger with every completed current-run round and the current fully evaluated configuration count.
- Add `sequential_observed_bonferroni_adjusted_p_value` to every Top band while retaining the current-round value.
- Keep `candidate_signal` ineligible whenever the supplied sequential family is incomplete.
- Publish the ledger in compact supervisor status, round diagnostics, reports, and the scheduled self-iteration checklist.
- Keep selection and promotion write paths disabled.

## Falsification

Reject the change if a different historical surface is counted; the current run is duplicated at startup; malformed or legacy rows silently become zero-count diagnostics; the family is not `candidate tests × three bands`; the ledger decreases across durable rounds; status uses a local adjusted p-value despite an incomplete sequential family; or any ranking, search, frozen, or promotion behavior changes because of the audit.

## Validation

- Self-diagnostics, PostgreSQL, and supervisor targeted suites: `204 passed`.
- Full worker suite: `523 passed`.
- Python compilation, shell syntax, and `git diff --check` passed.

## Live Verification

Fresh final-code supervisor `20260711-132111`, PID `3579268`, started after syncing issue `2026078` with zero inserts, updates, or conflicts. Startup recovered 309 same-history durable rounds across prior runs. Fifteen diagnostic rounds exposed 271 candidate tests and therefore an observed family of `271 × 3 = 813`; 294 legacy rounds remained explicitly uncounted. The ledger also recorded `adaptive_hypothesis_generation_counted=false`, `sequential_search_multiplicity_counted=false`, `selection_changed=false`, and `promotion_allowed=false`.

Durable round 1 evaluated 19 unique configurations. The ledger increased monotonically to 310 total rounds, 16 observed diagnostic rounds, 290 candidate tests, and an observed family of 870; the 294 legacy-unaccounted rounds did not change. Top1000's current-round adjusted p-value was `0.003290005`, while the observed-sequential lower-bound adjustment was `0.0502158666`. Signal status remained `noise_risk`; candidates remained diverse with `10/10` unique Top-10 rank signatures, and strategy memory stayed on `null_model_forward_audit`.

Durable round 2 evaluated 21 unique configurations. The ledger increased again to 311 total rounds, 17 observed diagnostic rounds, 311 candidate tests, and an observed family of 933. Top1000's current-round adjusted p-value was `0.0036363214`, versus `0.0538521879` under the observed sequential family. The database-backed watch reported `target_complete_round_recorded`, all advisor signals current for their declared scopes, zero search/frozen overlap, passed prefilter isolation, no frozen use by search, historical holdout quarantine still active, and forward evidence still incomplete at `0/20`. Promotion remained disabled and candidate geometry remained diverse at `10/10`.

## Synthesis

The existing null check was locally conservative but globally incomplete. The smallest defensible improvement is a monotone observed-family lower bound that makes repeated search visible and blocks signal interpretation when the path is still incomplete; it is not a statistical cure for adaptive reuse of the same outcomes.

## Next Verification

Keep supervisor `20260711-132111` running until a genuinely later issue supplies the next frozen/forward snapshot. Recheck the monotone round/candidate/family counts, current advisors, candidate diversity, zero holdout overlap, active quarantine, and paired forward evidence before allowing any interpretation beyond `noise_risk`.
