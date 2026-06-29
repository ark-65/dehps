# Frozen Primary Navigation Gate V1

## Primary Goal

Prevent eval-slice wins with no frozen-primary lift from steering the next DEHPS training search base, target-weight inversion anchor, or decision round best when the stale/overfit guardrail is active.

## Non-Goals

- Do not add or promote a new algorithm, model, advisor, candidate source, strategy, or betting recommendation.
- Do not change the legal sample space, historical window, feature definitions, or promotion score.
- Do not commit generated runtime artifacts from `data/output` or `runtime`.
- Do not claim predictive lift from this change alone.

## Diagnostic Constraint

Gauss pass:

- The navigation candidate must beat the incumbent on the frozen primary score before it is allowed to steer search during the overfit/stale gate.
- Eval-slice top-100/top-1000/top-10000 hits alone are insufficient evidence when the frozen primary tuple remains tied with the incumbent.
- Strict comparison is required: a candidate with frozen primary score equal to the incumbent is treated as no lift.

Riemann pass:

- The issue was a framing mismatch between the local eval-slice response surface and the frozen validation boundary.
- The fix moves navigation choices back onto the frozen boundary when the gate says the local surface is suspect.
- The search space is not narrowed by a new heuristic; it only refuses unvalidated local candidates as navigation anchors under the existing guardrail.

## Change

- `best_challenger_summary` can now require strict frozen-primary lift over a baseline.
- `select_decision_round_best` centralizes decision-round selection and blocks probability focus, probability calibration, source-frontier, restart, and exploration champions without frozen-primary lift when the gate is active.
- `select_target_weight_inversion_anchor` now falls back to the incumbent when the proposed round best lacks frozen-primary lift under the gate, and filters challenger anchors by the same rule.
- `select_probability_focus_search_base` refuses a held focus as a search base when the gate requires frozen-primary lift and the focus does not clear it.
- `select_next_search_base` filters round best and challenger search-base choices by frozen-primary lift when the stale/overfit gate is active.
- Supervisor metadata now records the lift requirement, baseline frozen score, selected frozen score, and blocked decision candidates for auditability.

## Validation

```bash
apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests/test_training_supervisor.py -q
```

Result: `103 passed in 0.72s`.

```bash
apps/worker-python/.venv/bin/python -m pytest -q
```

Result: `295 passed in 28.95s`.

## Live Smoke

- Fresh supervisor run id: `20260629-092002`
- Running process: `pid=1334480`
- Status JSON: `data/output/optimization/training-supervisor-20260629-092002.json`
- Markdown status: `data/output/optimization/training-supervisor-20260629-092002.md`
- Log: `runtime/logs/training-supervisor-kdj-ridge-neural-target-inversion-20260629-092001.log`
- Command source: watchdog restarted the supervisor after the previous live process was stopped; this run uses the patched code.

Observed completed rounds:

- Round 1 completed target evaluation `100/100`, selected `search_challenger`, and ended with `no_improvement best_top10000=3`.
- Round 2 completed target evaluation `100/100`, selected `search_challenger`, and ended with `no_improvement best_top10000=3`.
- Round 3 started, confirming the run continued after two completed decision loops.
- No `Traceback`, `Error`, or `failed` lines were found in the live log during validation.

The fresh run had local stagnation `0` then `1`, so the frozen-primary gate was not active in the first two completed rounds. The gated behavior is covered by regression tests that force the overfit/stale condition and verify that no-lift candidates are blocked.

## Positioning

This is a training-navigation guardrail. It makes existing overfit/stale detection enforceable across the actual decision paths that choose anchors and search bases. It does not prove the training target has been reached, and it does not convert historical lift into a betting claim.
