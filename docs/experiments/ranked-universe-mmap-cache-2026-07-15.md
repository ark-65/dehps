# Ranked-universe mmap cache — 2026-07-15

## Round contract

- Primary goal: remove repeated PostgreSQL combination loading and NPZ array materialization from the production training supervisor's static-universe hot path.
- Non-goals: no changes to legal-space rules, hard filters, features, scores, weights, candidate budgets, advisors, promotion gates, or forward state.
- Authorization: Agent Request `engineering-mmap-ranked-universe-9c4744f` (request id 84, execution id 6).
- Starting commit: `9c4744fd794cb52b19b413a63fb802eed3b47ba7`.

## Root cause

The prior cache was one `.npz` file. Loading it returned ordinary in-memory arrays, and the production supervisor first queried and materialized all `C(33,6) = 1,107,568` rows from `ssq_red_combinations` to derive the cache key. A nominal cache hit therefore still paid the database transfer, Python tuple allocation, fingerprint traversal, and ndarray materialization costs.

## Change

- The full legal universe now has a deterministic source identity: lexicographic combinations from 1 through 33, choose 6.
- On a hot start, the deterministic source key is known before enumeration, so the cache is opened directly and no combination-table query or local enumeration occurs.
- On a cold start, the legal universe is generated locally once and filtered with the unchanged rules.
- Each of the 22 immutable matrix arrays is stored as an individual `.npy` file and reopened with `numpy.load(..., mmap_mode="r")`.
- A JSON manifest records cache format, feature schema, filter version, source count, dtype, and shape for every array.
- A cache is rejected on any manifest, source-count, dtype, shape, row-count, or file error.
- Publication uses a temporary directory plus atomic rename. A corrupt prior artifact is moved aside, replaced, and then removed.
- Cache artifacts remain generated local data under `data/output/cache` and are not committed.

## Exactness and performance evidence

Full legal-space cold construction produced:

- source rows: 1,107,568
- filtered rows: 1,105,506
- excluded rows: 2,062
- mmap fields: 22 of 22
- wall time: 45.267 seconds
- maximum RSS: 767,412 KiB
- swaps: 0

The next load produced:

- cache open time reported by the program: 0.0040 seconds
- maximum process RSS without traversing array pages: 51,844 KiB
- mmap fields: 22 of 22, all read-only
- swaps: 0

All 22 arrays were compared against the existing full-universe NPZ artifact with `numpy.array_equal`; every field was exactly equal. Fixture tests also compare score/rank results between uncached ndarrays and mmap arrays.

## Validation

Focused matrix/ranking and target-inversion tests:

```text
30 passed in 0.34s
```

Final full worker suite:

```text
963 passed in 41.01s
```

Final cache-focused suite, including corrupt manifest and corrupt-file replacement:

```text
5 passed, 19 deselected in 0.33s
```

## Gauss–Riemann cross-review

### Gauss pass

The proof obligation is exact ordered-sample-space and array equality, not a claim inferred from timing. The local generator is the same lexicographic `C(33,6)` construction previously enforced by the database loader. Every cached dtype, shape, source count, filtered count, field value, and representative rank result is checked. The full old/new array comparison passed exactly.

### Riemann pass

The ranked universe is an immutable shared base space. Splitting its coordinate fields into read-only mmap arrays lets the parent and forked workers refer to the same filesystem-backed pages instead of reconstructing the base space at each process start. The hot-load result confirms that the representation can be opened without enumerating the legal space or eagerly touching all pages.

### Disagreement and smallest shared conclusion

Exact semantic equivalence is established, but page-fault behavior under a complete training round is still an operational measurement rather than a proof. The smallest shared conclusion is to merge this representation-only change, then run one bounded observability-only 28-config round before considering 48 or 96 configurations.

## Live acceptance and bounded scale test

The first authorized live attempt, supervisor run `20260715-130405`, failed before round 1 because the production status renderer still referenced the removed Python `universe` list. The mmap cache itself opened successfully in about 0.005 seconds. The failure was recorded, no training or forward rows changed, and the integration bug was fixed by deriving legal, ranked, and excluded counts from the matrix status. PR #120 added the regression test.

The retry, supervisor run `20260715-131447`, completed one 28-config observability-only round:

- cache hit/open: 0.009 seconds
- total wall: 253.85 seconds
- target inversion: 43.539 seconds with 16 active workers
- maximum RSS: 10,178,892 KiB
- maximum sampled process-tree PSS: 6,798,523 KiB
- swaps: 0

The same merged commit then ran controlled 48- and 96-config rounds. Only the configuration budget changed.

| Budget | Generated | Selected | Wall seconds | Inversion seconds | Max RSS KiB | Sampled PSS KiB | Swap |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 28 | 28 | 17 | 253.85 | 43.539 | 10,178,892 | 6,798,523 | 0 |
| 48 | 48 | 21 | 261.66 | 43.212 | 10,653,504 | 6,001,435 | 0 |
| 96 | 96 | 26 | 279.99 | 45.165 | 10,349,128 | 5,286,486 | 0 |

Moving from 28 to 96 generated configurations increased wall time by 10.30% while remaining within the 24 GB operational bound. The sampled PSS values are observations, not proven true peaks.

All three rounds selected the same round-best config hash, `9ee993...5212f`. This establishes bounded capacity only; it is not evidence that 96 configurations improve predictive quality. Durable training table counts/update markers and the 2026081 forward run/candidate counts remained unchanged after every observability-only run.

## Acceptance conclusion

The mmap representation is accepted as semantically exact and operationally live-tested. A 96-config budget is safe for this one-round workload, but additional candidate volume produced no better round-best configuration and therefore does not justify a production budget increase by itself.
