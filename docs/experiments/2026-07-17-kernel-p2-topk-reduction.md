# Kernel P2: deterministic hierarchical TopK reduction

## Round boundary

- Primary goal: remove the serial tile/global TopK merge boundary without
  changing `strict_v1` candidate identity.
- Formal comparator: greater score is better; equal score selects the smaller
  canonical candidate row id.
- In scope: normal TopK, Red5 selection, NumPy reference, Numba CPU, Feature ABI
  reference, telemetry, and benchmark instrumentation.
- Non-goals: scoring or feature changes, production backend promotion, GPU,
  full ranking materialization, prediction regeneration, database writes, and
  historical artifact rewrites.

## Reduction architecture

`TopKReducer` is the shared reduction protocol. One bounded
`TopKReductionPool` is shared by normal TopK and Red5 for a kernel invocation.
The planner selects by K and tile size:

| Range | Reducer | Data flow |
| --- | --- | --- |
| `K <= 256` | `SmallKReducer` | tile-local selection, balanced strict merge tree |
| medium K, including 10,000 | `TileSelectionReducer` | tile-local TopK, bounded shard retention, balanced merge tree |
| large K | `PartitionMergeReducer` | streaming strict partition merge |

Every tile is reduced independently across configurations. Finalization uses a
fixed balanced tree and the same comparator at every boundary. Chunk order,
chunk size, worker count, and executor completion order therefore cannot change
the result. Red5 uses the same reducer with a shared boolean mask and `K=1`.

No full ranking is materialized. For the production-sized Top10000 benchmark,
the reducer retained 400,000 `(id, score)` cells across five tiles and eight
configurations, estimated at 6.4 MB.

## Correctness evidence

The focused tests compare reducer output to a full `np.lexsort` oracle and cover:

- small K, Top1000, Top10000, and large-K planner paths;
- randomized scores rounded to create dense tie groups;
- all-equal scores;
- forward and reverse tile order;
- different chunk sizes and 1/3/4/8 reduction workers;
- masked Red5 selection;
- zero K and empty masks;
- dtype and shape fail-closed behavior;
- exact integration equality across NumPy, fused Numba, and Feature ABI paths.

Full legal-space checks used all `C(33,6) = 1,107,568` candidates, the real
history window ending at issue `2026081`, eight configurations, exact target
rank, Red5, and two score passes. NumPy and Numba result digests were identical.

## Performance evidence

The machine was concurrently running the existing 16-worker research lane, so
these are conservative operational measurements rather than an isolated host
ceiling. Peak RSS was 1,227 MiB and swap remained zero.

### Top1000

| Backend | Workers | Wall s | TopK s | Strict exact |
| --- | ---: | ---: | ---: | --- |
| NumPy reference | 1 | 2.688 | 0.124 | yes |
| Numba CPU | 1 | 0.584 | 0.078 | yes |
| Numba CPU | 8 | 0.176 | 0.041 | yes |
| Numba CPU | 16 | 0.135 | 0.040 | yes |

The previous strict-v1 profile measured approximately 0.085 seconds in serial
TopK merge at eight threads and 0.233/0.188 seconds end-to-end at 8/16 threads.
P2 reduces the observed merge boundary to about 0.041 seconds and the measured
8/16-thread wall time to 0.176/0.135 seconds while preserving the result digest.

### Top10000

| Backend | Workers | Wall s | TopK s | Reducer | Strict exact |
| --- | ---: | ---: | ---: | --- | --- |
| NumPy reference | 1 | 3.129 | 0.235 | tile tree | yes |
| Numba CPU | 8 | 0.329 | 0.081 | tile tree | yes |
| Numba CPU | 16 | 0.189 | 0.072 | tile tree | yes |

All three Top10000 rows produced digest
`1d53eac25bacb73c6322b4d87a2990116905dfc74ee0a2c7b78d9d376beca7d1`.

The benchmark now prepares each backend once and reuses the prepared store.
This removes repeated full Candidate ABI validation from steady-state profiles;
the profile now contains 17,842 calls and measures the 0.29-second kernel path,
instead of reporting roughly 298 million calls dominated by repeated preflight.

## Operational boundary

This round issued no prediction, evaluation, promotion, or candidate write. The
live system advanced independently while the benchmark ran: history currently
contains issue `2026081`; the database contains the original three pending
2026081 runs and three newer pending 2026082 runs. This code did not create,
rewrite, supersede, or evaluate any of them. Production still defaults to
`numpy_reference`.

## Newly exposed next bottleneck

The corrected profile also makes one startup defect explicit: a full Candidate
ABI `prepare()` currently spends roughly 87 seconds revalidating 1,107,568 rows
in Python. That cost is outside the 0.1–0.3 second scoring measurement but is too
large for repeated runtime preparation. The next infrastructure round should
cache a sealed, verified Candidate ABI identity by package/layout/payload digest
and reuse it across backend preparation, while retaining fail-closed validation
on cache miss or payload drift. Shadow promotion remains after that correction.
