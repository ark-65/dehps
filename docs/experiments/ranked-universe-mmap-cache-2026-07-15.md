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

## Remaining acceptance step

A separately authorized Operator run must complete at least one observability-only training round on the merged commit, record stage timing and RSS/PSS, and confirm that durable training and forward fingerprints remain unchanged.
