# Training Advisor Freshness Lifecycle V1

Date: 2026-07-10

## Primary Goal

Close the operational loop between latest SSQ history, canonical KDJ advisor signals, and the live training supervisor so scheduled training does not keep spending compute on stale advisor inputs.

## Non-Goals

- No new model, advisor, candidate source, feature, weight, or betting recommendation.
- No relaxation of frozen validation, ranked-uniform null comparison, leakage checks, or promotion gates.
- No claim that historical lift or a recovered search candidate predicts a future draw.

## Evidence Before Change

- History and the live supervisor were at issue `2026078`.
- Weight KDJ, Ridge KDJ, and Neural KDJ loaded canonical signals ending at `2026068`, a lag of 10 actual history issues.
- Scheduled `daily_pipeline.py` invocations repeatedly failed at startup with `ModuleNotFoundError: No module named 'scripts'`.
- The supervisor remained alive and productive at the process level, but the same round-best configuration and metric signature repeated across 12 recent rounds.

## Change

- Direct script execution of `daily_pipeline.py` now resolves its sibling signal generator safely; module execution remains supported.
- Training watch reports per-advisor signal freshness against the ordered history issue sequence, including cross-year boundaries, missing metadata, stale signals, and signal-ahead leakage risk.
- The watchdog treats stale canonical signals as a supervisor lifecycle boundary: stop the old supervisor, refresh `weight-kdj-recent-1000-v1` incrementally, verify exact issue alignment, then start a fresh supervisor.
- The two-hour self-iteration prompt now requires signal freshness, repetition, rank homogeneity, source survival, frozen validation, null baseline, and leakage review. More compute alone is explicitly not accepted as improvement.

## Gauss–Riemann Cross-Review

- Task Frame: distinguish an operationally healthy process from a scientifically progressing training loop.
- Historical Boundary: Gauss and Riemann are historically inspired diagnostic lenses, not literal minds or authority.
- Gauss Pass: the verified invariant is issue alignment across history, canonical signals, and supervisor inputs; stale or future signals invalidate interpretation before model comparison.
- Riemann Pass: the learning loop must be treated as a data-to-search-to-validation state transition, not as an isolated optimizer process.
- Disagreement: stale signals may explain advisor failure but do not by themselves explain the full objective plateau.
- Synthesis: repair and freeze the data lifecycle first; only a same-parameter fresh run can test whether search logic also needs adjustment.
- Next Verification: refresh through `2026078`, start a fresh run, observe at least 1-2 completed rounds, and compare source survival, rank signatures, frozen validation, and failure modes with the stale-signal run.

## Einstein Experiment

- Core question: does restoring canonical signal freshness change advisor survival or search geometry under otherwise identical supervisor arguments?
- Invariant: legal universe `1,107,568`, ranked universe `1,105,506`, expanding train window `900`, eval window `100`, Top-N `10000`, and frozen/null/leakage gates remain unchanged.
- Hypothesis: fresh canonical signals will change advisor proposals or rank signatures; it need not improve frozen validation immediately.
- Measurement: signal issue lag, generated/refined/source-survival counts, round-best rank signature, dynamic/static line deltas, frozen primary score, parser/sync/duplicate status, and runtime errors.
- Failure mode: if a fresh run still repeats the incumbent and advisor sources remain filtered out, stale data was not the sole cause and the next round should test navigation/objective plateaus without weakening promotion.
