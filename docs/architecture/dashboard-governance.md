# Runtime And Research Dashboard Governance

Status: accepted information architecture; API/Web implementation requires a separate Engineering
Request.

## Purpose

DEHPS must not place platform maturity and prediction quality into one score, one color, or one
leaderboard. The product surface therefore has two dashboards backed by separate data contracts.
Knowledge remains a shared definition/index surface rather than a third performance score.

## Runtime Dashboard

The Runtime Dashboard answers: can this computation be trusted and reproduced under the declared
contracts?

| Section | Fields |
| --- | --- |
| Contracts | family/version/digest, compatibility status, last verified commit |
| ABI | Candidate/Feature/Scoring/Ranking/Evaluation layout and verification status |
| Backend equality | package identity, backend pair, result/artifact digests, mismatch count |
| Golden suites | suite identity, command, pass/fail, commit, timestamp |
| Worker regression | command, scope, passed/failed/warnings, commit, timestamp |
| Performance | workload identity, cold/hot latency, throughput, RSS, device workspace, swap |
| Telemetry | Runtime Envelope, verification passes/time, cache, transfer, kernel, rejection reasons |
| Operational health | service/process evidence, shadow cohort coverage, stale/missing evidence |

M1 acceptance is a capability badge, not a permanent green signal. Current status values are:

```text
verified | warning | stale | missing | failed | not_applicable
```

Missing or expired evidence fails closed to `stale` or `missing`. A backend is not equal merely
because its last successful comparison once passed.

## Research Dashboard

The Research Dashboard answers: did a frozen research change improve the declared objective, remain
stable, and generalize beyond selection evidence?

| Section | Fields |
| --- | --- |
| Search windows | Recent-30/100 exact issue identities, role, cutoff hits, rank distribution |
| Stability | Recent-300, sub-window deltas, window overlap warning |
| Walk-forward | as-of rule, train/eval windows, baseline/null, exact ranks, missed issues |
| Calibration | null probability, expected/observed hits, interval, unadjusted/adjusted status |
| Feature evidence | definition/version, importance method, ablation boundary and deltas |
| Generalization | frozen future issues, evidence maturity, successes and failures |
| Candidate evidence | line, config/package identity, compression/keep rate where applicable |
| Uncertainty | leakage, parser/sync/duplicate, multiple-search, post-hoc, stability warnings |

Expected Value displays `not_defined` until an accepted economic Evaluation Contract exists.

## Cross-lane process strip

Evaluation freshness, shadow capture coverage, experiment completion, and promotion decisions are
shown in a separate process strip. They are not added to either Runtime maturity or model-quality
scores.

- Shadow numeric equality and attestation validity are Runtime Health.
- Whether a research batch has complete evaluations is Research Process.
- Promotion Rate is descriptive; a higher rate is not automatically better.
- Production selection remains controlled by the existing Promotion Gate.

## No composite score

The UI and API must not calculate a combined Runtime/Research health number. A view may be:

```text
Runtime: verified
Research quality: no_learning_lift
Research process: 14 rounds complete, forward evidence pending
```

Those facts must remain simultaneously visible. Runtime green does not soften a research failure,
and a research lift does not hide stale Runtime evidence.

## Implementation slices

1. API projection: normalized read-only Runtime, Research Quality, and Research Process payloads with
   source identity and freshness.
2. Web navigation: Runtime and Research dashboards; existing service/training/experiment views map
   into the correct dashboard without losing evidence.
3. Knowledge links: each metric links to its contract or semantic definition.
4. Acceptance: API/Web tests, Web build, stale/missing/error fixtures, and rendered evidence for both
   dashboards.

No slice may invent a green value from absent evidence or infer model quality from service health.
