# Dynamic KDJ Adaptive Strength V1

## Goal

Turn the dynamic KDJ line from a fixed best strength into an auditable KDJ-state strength band.

The selected strength is now an anchor, not a constant controller. For example, an anchor of `0.25` can produce per-issue effective strengths inside a KDJ-derived band such as `0.125..0.5`.

## Non-Goals

- Do not add a new model family.
- Do not promote the dynamic line over the main line.
- Do not claim predictive certainty or betting edge from historical lift alone.

## Historical Boundary

The Gauss/Riemann notes here are diagnostic lenses, not literal reconstructions of either historical figure.

## Gauss Pass

- The dynamic line must not select a static `0.0` strength.
- A selected training summary must be fully dynamic: no fallback targets, all evaluated targets changed, and leakage checks passed.
- The effective strength range is persisted in regression metadata as min, median, and max effective offset scale.
- Candidate snapshots refuse to publish the dynamic line when KDJ offsets are absent or policy regression is not fully dynamic.

## Riemann Pass

The old line treated strength as a single global coordinate. The new line treats it as a state function over the KDJ advice space: `anchor -> [min, max] -> per-issue effective strength`.

This keeps the base search space shared with the main line while allowing local KDJ state to change how strongly the offsets are applied.

## Change

- Removed the static `0.0` branch from dynamic KDJ strength sweep selection.
- Added `kdj_state_band` strength policies with `anchor_offset_scale`, `min_offset_scale`, and `max_offset_scale`.
- Added KDJ-state effective strength calculation from advice probability, J extremity, J slope, interval edge, and downweighted share.
- Added fully dynamic guards for training policy selection and next-candidate publication.
- Added supervisor policy/status fields for anchor, band, strength mode, and effective median scale.

## Validation

```bash
apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests/test_next_candidates.py -q
apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests/test_training_supervisor.py -q
```

Both commands passed locally before live supervisor validation.

## Next Verification

- Restart the training supervisor with updated code.
- Monitor at least 1-2 completed rounds.
- Compare dynamic anchor, effective strength median/range, top bands, red5 bands, fallback count, changed count, and leakage status.
- Treat any persistent top100 degradation against the main line as a warning, even if median rank improves.
