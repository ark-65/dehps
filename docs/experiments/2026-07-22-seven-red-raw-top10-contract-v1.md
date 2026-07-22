# Seven-Red Raw Top10 Contract v1 — 2026-07-22

## Round contract

- Primary goal: deterministically select the unmodified Raw Top10 from an immutable pre-scored
  seven-red candidate Artifact.
- Engineering authorization: Agent Request `173`
  (`engineering-seven-red-raw-top10-contract-v1`), execution `94`.
- Dependency: completed Request `172`, `seven-red-domain.v1.0.0`, merged commit
  `5580676a4c96ea9cafe649856c31963a3219708a`.
- Role: Engineering Agent.
- Status: `RESEARCH_ONLY`.
- Production impact: none.

## Implemented inputs and outputs

`ScoredSevenRedCandidate` binds one immutable milestone-1 `SevenRedCandidate` to:

- the original finite binary64-compatible `raw_score`;
- the original finite binary64-compatible `normalized_score`;
- an explicit normalized-score round-8 ranking key;
- `source_model`, `feature_digest`, and `source_run_id` provenance;
- a full domain-separated SHA-256 row digest.

`PreScoredSevenRedCandidateList` is the input Artifact. Its rows are canonically stored by the
seven-red full-universe lexicographic ID, so caller, database, or hash-container iteration order does
not affect its digest. Duplicate candidates, empty input, noncanonical stored order, malformed
provenance, ambiguous score types, booleans, NaN, and infinity fail with typed errors.

`RawSevenRedTop10Snapshot` is the output Artifact. It binds the source Artifact digest and applies
exactly this frozen ranking contract:

```text
normalized_score rounded to 8 decimals descending
then seven-red full-universe lex_id ascending
then take exactly 10
```

The snapshot retains each original raw and normalized score, selected candidate ID, red numbers,
mask, lex ID, provenance, one-based raw rank, source row digest, and source candidate-list digest.
There is no seed input and no generated timestamp in either content identity.

## Deterministic evidence

The executable golden case contains twelve pre-scored candidates, including two distinct
normalized scores that become equal after round-8. The lower lex ID wins that tie without changing
either stored score.

- frozen normative contract digest:
  `cae99a1a4a834de93ba805153f82878c1ef3857e3c4856a1ae371e83785c1a65`;
- frozen candidate-list Artifact digest:
  `11e808c38f8cfa64081e8986345b74b3fc7f29691d47e7ab514113bc79b24ca5`;
- frozen Raw Top10 snapshot digest:
  `c9a9710816090a22be10e78cfcd061384f70c83fcf71816d163cbb164e04f922`.

Permuting the same twelve input rows reproduces all three identities and the same Top10 ranks.
Changing a score or source-run provenance changes the input Artifact digest. Fewer than ten valid
candidates fails closed; exactly ten succeeds.

## Raw means unmodified

This selector applies no overlap penalty, marginal-relevance term, clustering, family quota,
coverage objective, score adjustment, or outcome-aware reranking. That is necessary because Raw
Top10 must remain the audit reference for the model's unaltered scored order. Diversity metrics and
Diversified Top10 require later separately authorized rounds.

Raw Top10 is not required to produce 70 unique expanded six-red combinations. Detecting and
reporting such collapse is a future diversity-audit responsibility; silently modifying Raw Top10 to
repair it would violate this contract.

## Validation

- Focused Raw Top10 plus milestone-1 regression:

  ```bash
  apps/worker-python/.venv/bin/python -m pytest -q \
    tests/test_seven_red_raw_top10.py tests/test_seven_red_domain.py
  ```

  Result: `43 passed in 0.24s`.
- Complete worker regression after freezing golden digests:
  `apps/worker-python/.venv/bin/python -m pytest -q`
  — `1421 passed, 4 skipped, 4 warnings in 78.87s`.
- The four warnings are the existing Python 3.14 `multiprocessing` warning about `fork()` from a
  multi-threaded process; this round introduced no new warning class.
- `git diff --check` passed, and the changed Python files contain no lines longer than 110
  characters.
- Source-scope audit found no Raw Top10 import or integration outside the isolated seven-red package
  and its focused tests.
- No database, API, web, CLI, model, feature producer, training, scheduler, watchdog, forward-wait,
  supervisor, prediction, scoring, or production TopK path was changed or operated.

## Explicit non-goals and next dependency

This round does not generate candidates or scores, define score normalization, implement
Diversified Top10, compute diversity metrics, enforce cross-candidate expansion uniqueness, run a
baseline or walk-forward experiment, create Evidence, or decide the long-term hypothesis.

The next dependency is a read-only diversity audit over both the complete pre-scored pool and the
frozen Raw Top10 snapshot. Its thresholds must remain observational until a later strict experiment
justifies any selection constraint.
