# M4 P2.6.1 Round 11 current-host Operator cutover

Date: 2026-08-05

Role: Operator

Agent Request: `operator-m4-p2-6-1-current-host-late-prefix-cutover-round-11-20260805` (#268)

Execution: #189

## Primary goal

Make merged commit `6024a02d71b3c526d5ae010bd0c901d91c7673fc`
the singular canonical P2.6.1 runtime on the current primary host, without
changing the frozen task, execution, workload, journal, worker count, or shard
identity.

## Non-goals

- No manifest import, database move, second-host deployment, workload or fold
  reduction, solver/tolerance/C/model change, worker tuning, Gate, or Promotion.
- No statistical result payload read and no Evidence Progress increment.

## Cutover result

The user Supervisor was restarted at 10:03:34 CST from a clean detached
worktree at `6024a02`. The previous runtime was `c1c8330`. The service created
immutable runtime migration
`32d49770795f0fafd13e11c3f08749ecac458da77e2293b4a1f95b3f1c935e16`.

The following identities remained unchanged:

- live manifest: `dd9a2a0106fe17787cb57a6293bd1e9eea9cb8c30771f6a7e27b0ecc30c18ce3`
- Resolver snapshot: `29aa2bf7b608b427bc6b7d0f7338d3a380682bd7861f1d40131a5f6c8971b6ad`
- task: `80068e22f5e1c343fd86213faa0d9a411d71f92ad2750fed10449a10151de8fa`
- execution: `cd64aacc48c5e1dac4f84d7f644e92384b50f37299b1643631b7ee872ab452b3`
- execution plan: `808b9a0b804b9c0919a4a299304d4449eb0ec9c370fbdfef2c0af2b043661d79`
- executor: shard 0 of 2, 20 workers

## Live validation

The restarted Supervisor first replayed existing partial journals and compared
every reconstructed checkpoint fail-closed. It then crossed the prior journal
waterline for HISTORICAL replicate 948 and persisted 78 new canonical fold
entries: 1,316 before restart and 1,394 at acceptance observation.

- fold indices were contiguous;
- the strict-prior target-access guard remained present on every entry;
- failed and retried replicate counts remained zero;
- the service had zero restarts, zero swap, and zero OOM events;
- memory was 8.31 GiB current and 8.56 GiB peak, below the 16 GiB rollback line;
- all 20 workers were running from the `6024a02` worktree.

The immutable 61-fold production-like replay remained exact:

- result float64-tree digest:
  `e239c79849894d269dc8d33997c8a13ec1e6dc75f40c7f1bbd614105de9370b4`
- journal SHA-256:
  `5ad68b8a9b6e97067d692fdf82f101520e261d2451262591e5ee178b4966db24`
- journal byte count: 40,250

No statistical payload was inspected.

## Integration matrix

| Mainline link | Evidence | Status |
|---|---|---|
| Goal | Requests #267 and #268 | complete |
| Resolver | live manifest resolved as snapshot `29aa2bf7...` | complete |
| Ready Queue | unchanged running P2.6.1 task selected | complete |
| Supervisor | fresh invocation `2ba05ff3...` on `6024a02` | complete |
| Capability | compact no-trace identity and exact prefix/tree reuse | complete |
| Artifacts | runtime migration plus 78 new canonical fold entries | complete |
| Status | live progress heartbeat, zero failure/retry | complete |
| Next task | next owned fold/replicate and result-blind ETA audit | active |
| Replay | registered 61-fold result and journal identities exact | complete |

Mainline integration answer for the Round 11 acceleration:

**YES — validated by unified mainline execution and replay.**

The overall P2.6.1 workload remains `RUNNING` at 13,842/31,000. This acceptance
does not claim that the remaining work is already below two weeks. A result-
blind steady-state throughput sample is still required after the first full
post-restart replicates complete. Exact liblinear remains the next dominant
operator candidate.
