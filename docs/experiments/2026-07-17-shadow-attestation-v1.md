# Two-Phase Shadow Capture and Attestation v1

## Round boundary

Primary goal: make a live three-issue shadow cohort cryptographically honest by
separating immutable pre-draw scoring capture from post-draw evaluation
attestation, then wire opt-in simultaneous capture into newly created forward
snapshots.

Non-goals:

- no live capture activation;
- no modification of existing 2026081/2026082 runs;
- no production backend switch;
- no prediction, evaluation, service, or scheduler operation;
- no automatic promotion authority.

## Evidence phases

`scoring-kernel-shadow-evidence.v1` now has two explicit phases.

### `scoring_capture`

Produced before persistence of a new forward prediction. It compares NumPy and
Numba TopK from the same candidate store, window, weights, and request, binds the
generated official candidate rows and scores, and records evaluation, restart,
and watchdog as pending.

### `post_draw_attested`

Produced after the draw and completed official evaluation. It embeds and verifies
the complete pre-draw capture, references its digest, and binds a simultaneous
exact-rank/Red5 replay plus evaluation, restart recovery, and watchdog evidence.
The link rejects any change to target, line, prediction run, config, Candidate ABI
package, or source commit.

The readiness gate accepts only the second phase. If a standalone pre-draw file
and its attestation both exist, the gate joins them by digest and treats the
capture as superseded evidence rather than a duplicate. Invalid, unrelated, or
multiple attestations still fail closed.

## Production capture boundary

The snapshot builders for `static_100`, `dynamic_kdj`, `dynamic_kdj_near`, and an
optional forward challenger call one shared attachment boundary. Capture is off
unless `DEHPS_FORWARD_SHADOW_CAPTURE` is an explicit true value. When enabled:

1. `numpy_reference` must still be the official backend;
2. snapshot and runtime Git commits must match;
3. the ranked CandidateStore is reused without copying the universe;
4. a second NumPy reference and Numba shadow execute before persistence;
5. generated candidates must match the reference TopK exactly;
6. sealed evidence is placed in `forward_prediction_run.metadata`, so database
   candidate rows and shadow identity share one transaction.

Capture failure never substitutes a candidate list. Instead it persists a
structured `shadow_scoring_failure`, emits a warning, and leaves
`automatic_promotion_allowed=false`.

## Post-draw operation

`scripts.run_forward_scoring_shadow` now has two behaviors:

- a run with stored pre-draw evidence can create a linked post-draw attestation;
- a legacy run without it remains `posthoc_reconstruction` and cannot pass the
  gate.

The script remains read-only with respect to PostgreSQL and writes only
content-addressed artifacts under ignored output storage. It refuses source
evidence with a malformed seal and exposes source/replay commit differences.

## Validation

Focused capture, attestation, next-candidate, storage, adapter, and gate tests:

```text
66 passed in 6.84s
```

Complete worker regression:

```text
1161 passed, 4 existing multiprocessing fork warnings in 56.44s
```

The integration fixture executes real NumPy and Numba kernels, binds 100 generated
candidates, verifies metadata persistence, exercises explicit capture flags and
structured failure isolation, links post-draw evidence, rejects raw/pending and
post-hoc rows, and joins a standalone capture with its attestation by digest.
Latest-prediction JSON and Markdown also expose per-line capture state and an
aggregate captured/failed/unavailable summary without fabricating legacy evidence.

## Operational state

No live environment variable was changed and no service was restarted. Existing
forward runs, candidates, evaluations, history, and production defaults remain
unchanged. Activation still requires an approved Operator action.
