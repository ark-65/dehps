# Bounded Experimental Navigation V1

## Primary Goal

Let a stalled training supervisor keep exploring when the frozen-primary guardrail blocks promotion, without weakening frozen validation requirements for accepted best configs.

## Non-Goals

- Do not add a new model, algorithm, advisor, feature, or betting recommendation.
- Do not change the legal sample space, historical window, reward function, or frozen promotion gate.
- Do not allow no-frozen-lift candidates to become accepted best summaries.
- Do not commit generated runtime artifacts from `data/output` or `runtime`.

## Diagnostic Constraint

Gauss pass:

- Frozen primary lift remains mandatory for promotion and accepted decision evidence.
- A no-lift exploratory candidate may only steer the next search base, never the accepted best.
- The exploratory navigation path requires a changed target-rank vector and sufficient config distance, so it cannot simply replay the incumbent.

Riemann pass:

- The previous guardrail correctly rejected local eval-slice wins as evidence, but it also collapsed navigation back onto the incumbent during long stalls.
- This change separates validation from search geometry: frozen validation still judges claims, while bounded exploratory navigation can probe a different local basin.

## Change

- `select_next_search_base` now accepts `exploration_navigation_candidate`.
- When frozen-primary navigation is required and no frozen-lift challenger is available, a candidate can be used as `experimental_navigation` only if:
  - it has no frozen primary lift over the baseline;
  - it is not recently excluded;
  - it clears the current minimum config distance;
  - it changes the target-rank vector versus the current base.
- The main supervisor loop passes the existing stagnation exploration champion into search-base selection.
- Metadata records `exploration_navigation_*` fields for auditability.

## Validation

```bash
apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests/test_training_supervisor.py -q
```

Result: `104 passed in 0.78s`.

```bash
apps/worker-python/.venv/bin/python -m pytest -q
```

Result: `298 passed in 22.62s`.

## Live Smoke

- Stopped old supervisor PID `1388459`, which was still running pre-change code.
- Archived stale heavy-job locks:
  - `runtime/logs/dehps-heavy-job.lock.stale-20260629-143126`
  - `runtime/logs/dehps-heavy-job.lock.json.stale-20260629-143126`
- Fresh supervisor run id: `20260629-143206`
- Running PID: `1498905`
- Status JSON: `data/output/optimization/training-supervisor-20260629-143206.json`

Observed completed rounds:

- Round 1 completed `100/100` target evaluation, selected `search_base_next=search_challenger`, `changed=True`, and ended with `no_improvement best_top10000=3`.
- Round 2 completed `100/100` target evaluation, selected `search_base_next=round_best`, `changed=True`, and ended with `no_improvement best_top10000=3`.
- No `Traceback`, `Error`, or `failed` lines were observed during the two-round live smoke.

The live smoke did not yet trigger `experimental_navigation` because the fresh run had low stagnation and the frozen-primary gate was not active. The regression test covers the gated path where frozen lift is required and only a bounded exploratory navigation candidate is available.

## Positioning

This is a training-navigation change, not a prediction claim. It keeps frozen validation as the acceptance boundary while reducing the chance that long-running exploration keeps orbiting the same incumbent basin.
