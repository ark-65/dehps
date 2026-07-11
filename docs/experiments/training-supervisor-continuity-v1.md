# Training Supervisor Continuity V1

## Round frame

Primary goal: prevent a controlled supervisor handoff from forgetting a validated search direction while preserving the incumbent and every promotion/leakage guardrail.

Non-goals:

- no new scoring algorithm, advisor, weight, or lottery claim;
- no lower stagnation threshold or wider candidate budget;
- no promotion from an eval-slice score alone;
- no claim that a continuity seed improves future prediction.

Evidence level: operational training diagnostic. The legal red-ball universe is 1,107,568 combinations; the ranked post-filter universe in the observed runs is 1,105,506. The training history is `current_regime_default`, expanding mode, train window 900, eval window 100, frozen window 20, through issue `2026078`.

## Observed failure

- Fresh-advisor run `20260710-160311` completed three rounds with current signals. Its first two rounds repeated one config and one metric signature; round three changed config but retained `[3,3,3]` eval hits and no frozen primary hit.
- Prior run `20260710-134459` repeated the same best config and `[3,3,3]` eval metrics for all 17 rounds.
- At round 17, rank-homogeneity recovery generated candidate `7ab17b375d693fe3a4e18bd5795c06d08a5be5511a26c0f1ddf2a8c9450f730b`. It changed all 100 target ranks and scored frozen primary `[0,0,1]` versus incumbent `[0,0,0]`.
- The round decision selected that candidate as a source-frontier navigation candidate, but it ranked 12th on the eval slice. Only the eval top five and incumbent were reloadable, so the next supervisor reset the search direction and stagnation counter.

This is a lifecycle memory defect, not evidence that the candidate is a promoted model.

## Gauss–Riemann protocol

Historical boundary: “Gauss” and “Riemann” below are historically inspired verification lenses, not literal minds, model replicas, or sources of authority.

### Gauss pass: verification

Strongest claim: the database proves a strict frozen-primary navigation lift was selected in round 17 and was absent from the next run's seed set.

Weakest assumption: the stored decision remains valid after process handoff. It must therefore be re-evaluated against the exact current history fingerprint before reuse.

Required test: recover the exact config hash, rerun all 100 eval draws and the 20-draw frozen window, and reject it if frozen primary is no longer strictly above the incumbent.

### Riemann pass: structure

Strongest claim: a supervisor boundary is an operational discontinuity, not a legitimate boundary in the search state. Search direction and model promotion are distinct state spaces.

Weakest assumption: continuing one validated direction improves exploration efficiency; it may still lead to another plateau.

Required test: compare the first post-handoff search base and candidate-source survival with a reset run while keeping all evaluation parameters fixed.

### Cross-review and disagreement

- Gauss rejects carrying arbitrary exploration state because repeated frozen-window search creates multiple-testing risk.
- Riemann rejects resetting every search direction because it repeatedly forces the system to rediscover the same structural escape.
- Unresolved risk: a frozen-primary hit reused across repeated searches is not independent forward evidence.

### Smallest shared conclusion

Only a same-history candidate whose recorded frozen primary score strictly exceeded its baseline may be recovered. The new supervisor must fully re-evaluate it; if the strict lift survives, it may initialize `search_base` but must not replace `best_summary`, update the incumbent checkpoint, or bypass the normal promotion gate.

## Implementation

- Load recent same-history round navigation records from PostgreSQL.
- Recover the selected config from persisted summaries; legacy deterministic stagnation-restart candidates can be reconstructed and hash-verified.
- Re-evaluate recovered configs at startup and select continuity only on strict frozen-primary lift.
- Persist a decision candidate even when it is outside the eval top five, avoiding future reconstruction.
- Expose a compact `continuity_seed` in the watcher and require the two-hour self-iteration audit to inspect it.

## Acceptance evidence

- Focused supervisor/watcher tests: `170 passed`.
- Full worker suite: `434 passed`.
- Live database recovery found two hash-verified same-history candidates, including `7ab17...` from run `20260710-134459` round 17.
- Final live run `20260710-164004` (PID `2277896`) recovered and re-evaluated two candidates. Both retained a frozen-primary lift; `7ab17...` was selected as the initial search base with `[0,0,1]` versus incumbent `[0,0,0]`.
- Round 1 started from `7ab17...`, completed without runtime or leakage errors, but produced a narrow single-source frontier and no frozen promotion.
- Round 2 restored multi-source survival: Weight KDJ 2, Ridge KDJ 1, and Neural KDJ 1 reached full evaluation. Neural candidate `470494...` became round best; candidate-space diagnosis changed from `narrow` to `diverse`.
- Round 2 moved median rank from `556683.5` to `556659.5`, best rank from `39` to `38`, and objective from `5083.929527` to `5083.929797`, while exact eval hits stayed `[3,3,3]`. These small eval-slice changes did not pass frozen validation and are not accepted as predictive improvement.
- After two rounds the watcher reported `severity=ok`, `action=continue_current_run`, current advisor signals at issue `2026078`, distinct config/metric signatures, and parser/sync/duplicate and leakage checks passing.

## Guardrail

Historical lift remains hypothesis evidence only. Continuity reduces lifecycle forgetting; it does not establish a predictive edge, justify betting certainty, or count as model promotion.
