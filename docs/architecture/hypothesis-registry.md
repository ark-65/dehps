# Hypothesis Registry Design

This document defines the next-round registry contract only. Round 18 does not add a database migration or alter training strategy.

## Records

- `Hypothesis`: a falsifiable claim with invariant, null, minimal non-null, metric, failure condition, evidence boundary, author role, and timestamps.
- `HypothesisFamily`: a mechanism-level grouping used to prevent parameter retuning from disguising a rejected mechanism.
- `Experiment`: a preregistered execution of one hypothesis against a frozen history/as-of boundary, config, code revision, objective policy, and baseline.
- `Evidence`: immutable measured output, including metrics, artifacts, leakage report, failures, and uncertainty.
- `Rejection`: structured reason codes, scope (`parameter` or `family`), rejected configuration region, and evidence references.
- `ReopenCondition`: a preregistered condition whose satisfaction permits a rejected hypothesis or family to return for review.

## States

```text
proposed -> preregistered -> running
running -> accepted_for_followup | rejected | inconclusive | invalidated
```

`invalidated` means the experiment cannot judge the claim because of leakage, parser failure, corrupted history, protocol violation, or another validity defect. It is not positive or negative model evidence.

## Parameter Failure Versus Family Failure

A parameter failure rejects the exact frozen configuration or preregistered bounded region. It does not reject the mechanism unless the experiment was designed with sufficient representative coverage and family-level failure criteria.

A family failure rejects the mechanism and forbids new experiments that only vary seed, nearby weights, epochs, thresholds, or equivalent parameterizations. The registry must compare normalized mechanism signatures before allowing a new experiment.

## Rejection And Reopen Rules

A rejected family cannot be rerun merely to consume compute or because time passed. Reopen requires a stored `ReopenCondition` and new evidence that satisfies it, such as a genuinely new causal input, a corrected validity boundary, a new untouched temporal block, or a materially different mechanism representation. Reopen approval records who approved it and which evidence satisfied the condition; the old rejection remains immutable.

## Markdown And Database Correspondence

Markdown reports are human-readable evidence views, not the source of lifecycle truth. Each report carries stable registry IDs and links to its experiment/evidence records. Database records keep the canonical status, objective policy identity, history fingerprint, config hash, commit, artifacts, and reason codes. Re-rendering Markdown must not create a new hypothesis or alter status.

## Agent Authority

- Research Agent may propose and preregister hypotheses and interpret evidence. It cannot promote a production strategy.
- Engineering Agent may implement a preregistered experiment, validity check, or runtime boundary. It cannot invent a hypothesis or weaken its failure rule.
- Training runtime may execute frozen experiments and emit facts. It cannot change hypothesis state beyond recording execution outcomes.
- Promotion requires the separate frozen gate and the project review policy. No agent can bypass invalid/leakage/forward-evidence failures.
