# Training Navigation Arbitration Audit V1

## Primary Goal

Preserve experimental-navigation eligibility evidence when probability focus wins search-base arbitration, so operators and self-iteration can distinguish “ineligible” from “eligible but preempted.”

## Non-Goals

- Do not change which search base wins arbitration.
- Do not add a model, advisor, source, objective, hold period, or budget.
- Do not weaken frozen promotion, null, leakage, parser, sync, duplicate, or forward-evidence gates.
- Do not treat rank movement or Top5 entry as predictive lift.

## Task Frame

Run `20260711-033806` completed five durable rounds after restoring promotion-only search-slice navigation. Search bases alternated:

```text
experimental_navigation -> probability_focus -> experimental_navigation
-> probability_focus -> experimental_navigation
```

All five rounds retained the same global-best config, metric vector, objective, and round-best rank signature. Restart champions still changed all 80 search targets and ranked 9–14; non-normal exploration champions reached rank 5 in rounds 2–5.

The persisted watcher state was contradictory on probability-focus rounds: the raw restart navigation candidate existed, but `search_base` lacked its counterfactual eligibility metadata, so the watcher reported `no_experimental_navigation_candidate`. Progress means preserving the same selected focus config while recording whether the navigation alternative was eligible, selected, and which source preempted it.

## Historical Boundary

Gauss and Riemann are used as historically inspired verification and structural-reframing lenses only. They are not literal minds, trained replicas, or evidence. Persisted code, tests, database rows, and live runs remain authoritative.

## Gauss Pass: Verification

- Legal red-ball space remains `C(33,6) = 1,107,568`; the live ranked universe remains `1,105,506` after existing exclusions.
- Evaluation remains 80 search issues plus 20 frozen promotion-only issues with zero overlap.
- Before the change, probability-focus selection returned metadata without `exploration_navigation_*` fields even though the same round had a restart champion with `rank_vector_changed=true` and `changed_target_count=80`.
- The repair computes the existing fallback/navigation decision exactly once, preserves the existing probability-focus result when it succeeds, and copies only the `exploration_navigation_*` audit fields into the selected metadata.
- Required invariants:
  - selected config hash and source remain probability focus;
  - eligible navigation is marked `selected=false`;
  - `preempted_by=probability_focus`;
  - promotion-only navigation records frozen-use `false`;
  - a non-preempted experimental selection still records `selected=true`.

Strongest claim: the old state could not distinguish ineligibility from arbitration preemption.

Weakest assumption: the counterfactual call is pure and deterministic; tests and code inspection cover this, but live hash equality remains required.

Test requested from the structural lens: confirm that copied evidence describes an alternative branch without changing the selected trajectory.

## Riemann Pass: Structure

- Search-base choice is a branch over multiple candidate manifolds: probability calibration and rank-geometry escape are not the same coordinate.
- Collapsing an unselected alternative to “no candidate” destroys information about the local branching structure and makes later causal review impossible.
- The correct state is a small arbitration record: candidate present, eligible, selected, and preempted by which branch.
- This does not claim the unselected branch would have performed better; it only preserves the counterfactual that existed at decision time.

Strongest claim: explicit branch-state observability is necessary before testing dwell time or priority changes.

Weakest assumption: eligibility metadata is sufficient to characterize the counterfactual; downstream performance remains unobserved because the branch was not selected.

Test requested from the verification lens: compare fresh-run selected source/hash against the prior behavior while checking the new fields.

## Cross-Review

Gauss rejects a new navigation-priority or dwell heuristic because five rounds show no global improvement and no predeclared causal baseline for such a change. Riemann rejects the old watcher output because it erases a real alternative branch. Both accept a behavior-preserving arbitration audit as the smallest defensible next step.

## Disagreement

- `scope`: It remains unresolved whether alternating bases need longer dwell time.
- `evidence`: A preserved counterfactual is not the outcome of taking that branch.
- `risk`: Future self-iteration could still overreact to eligibility unless it also checks `selected` and `preempted_by`.

## Synthesis

The verified local claim is observability-only: probability-focus rounds must preserve the eligibility state of a real experimental-navigation alternative without changing arbitration. Strategy changes remain deferred until a separately predeclared experiment exists.

## Implementation

- `select_next_search_base` records `exploration_navigation_selected` and `exploration_navigation_preempted_by`.
- The supervisor computes the fallback/navigation audit before probability-focus arbitration.
- A successful probability-focus selection retains its config and merges only experimental-navigation audit fields.
- The watcher exposes eligibility, frozen use, selected state, and preempting source in gate, Markdown, operator, and recommendation output.

## Live Validation

Controlled handoff:

- prior run/PID: `20260711-033806` / `2960838`, stopped after five durable rounds;
- fresh run/PID: `20260711-041601` / `3002210`;
- same as-of issue and training arguments;
- guard continuity resumed at effective stagnation `114` rather than resetting;
- continuity replay used `search_slice_revalidated` with frozen use `false`.

Round 1 persisted an actually selected experimental branch:

- selected source/hash: `experimental_navigation` / `78b99187e024...`;
- restart candidate eligible: `true`;
- selected: `true`;
- preempted by: empty;
- eligibility basis: `search_slice_rank_geometry`;
- selection uses frozen validation: `false`.

Round 2 persisted behavior-preserving probability-focus arbitration:

- selected source/hash: `probability_focus` / `234f030c39be...`;
- eligible restart alternative: `4a5ec9d0ec7a...`, full-eval rank `10`, `80/80` targets changed;
- alternative eligible: `true`;
- alternative selected: `false`;
- preempted by: `probability_focus`;
- eligibility basis: `search_slice_rank_geometry`;
- selection uses frozen validation: `false`;
- config distance: `0.95` versus minimum `0.08`.

The watcher reproduced the same state in gate, operator, Markdown, and recommendation output. Both rounds kept holdout overlap at `0`, search frozen use `false`, promotion blocked by `historical_frozen_holdout_quarantined`, advisor freshness current, and forward evidence at `0/20` with automatic quarantine release disabled. No runtime or database-read error was observed. The historical global best still did not improve.

## Validation

```text
apps/worker-python/.venv/bin/python -m pytest -q \
  apps/worker-python/tests/test_training_supervisor.py \
  apps/worker-python/tests/test_training_watch.py
218 passed

cd apps/worker-python && .venv/bin/python -m pytest -q
483 passed
```

## Next Verification

Use the new arbitration state to predeclare any later priority or dwell-time experiment. Do not infer how the unselected restart branch would have performed. Continue accumulating genuinely forward paired evidence independently of historical search behavior.
