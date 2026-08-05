# M4 P2.6.1 Round 12 native liblinear acceleration

Date: 2026-08-05

Role: Engineering Agent

Agent Request:
`engineering-m4-p2-6-1-native-liblinear-acceleration-round-12-20260805`
(#269)

Execution: #190

## Primary goal

Test whether a conservative current-host build of the exact scikit-learn 1.9.0
liblinear extension can remove enough of the remaining frozen P2.6.1 terminal-
fold cost to justify integration, without changing any scientific input or
output.

The acceptance threshold was frozen before measurement: exact binary64 model
and prediction identity plus at least `1.10x` warm full late-prefix fold
speedup. A faster liblinear microbenchmark alone was not sufficient.

## Non-goals

- No production service, production virtualenv, task, execution, worker, shard,
  fold, probe, solver, tolerance, `C`, seed, or model change.
- No fast-math, unsafe floating-point reassociation, approximate output,
  statistical result read, Evidence Progress increment, Gate, or Promotion.
- No deployment of a locally built binary without a passed full-fold gate and
  a separately authorized Operator execution.

## Isolated build provenance

The experiment used a temporary build environment under ignored `runtime/`.
No system package or production environment was modified.

- scikit-learn source: version 1.9.0 sdist
- source SHA-256:
  `8833266989d3a5110178a9fae30783675460724d0e1efb13b14901d2c660c557`
- baseline `_liblinear` SHA-256:
  `ae4217390c23a40b8729b614313e638e9e474653e4b3fb79392b16340f6a500a`
- local compiler: GCC/G++ 15.2.0 extracted from official Ubuntu packages
- native build SHA-256:
  `ba37d06043f5d847dbddab3cdaa29b19d535a8c13274f0387d3b01062b98a9fe`
- native plus LTO build SHA-256:
  `870ed3689e23b8c0d7206a71d74c12f65eb338ba4ed270b22f5902e432eeb342`

Both candidates used `-O3 -march=native -mtune=native` with
`-fno-fast-math`, `-fno-associative-math`,
`-fno-unsafe-math-optimizations`, `-ffp-contract=off`, and
`-fexcess-precision=standard`. The LTO candidate additionally used one serial
LTO partition. Benchmarks were pinned to one logical CPU and run at nice 19 so
the live Supervisor retained priority.

## Exactness result

The baseline, native, and native-plus-LTO builds produced identical values for
the 6,961-issue, 229,713-row terminal LONG/NULL fold:

- coefficient SHA-256:
  `338d2e81d88550983679a2fde1d3f70347b124de7e738530964cb3d845aef394`
- intercept SHA-256:
  `e3ff939105fc1a799c87b9d97b9ee3cc8e72020192da9e8abc73f3b3a199c259`
- iterations: `[4]`
- probability SHA-256:
  `55847452461f9c163591c9f1d965a2a85145180c356180ed75105979ae2aed3b`
- preprocessing state:
  `b8034f580379ebc81071968e2629deb83db1b51ff8a3be041e76a0097d9cf1f6`
- model parameters:
  `9b2734f542016e25919351706d0c06114f81ae5eb9904f9708c877f9a1bd7dd3`
- logistic probe state:
  `32d87723c03514dd81b21064d530139c941f3eb2818278465ab1b86cbaebef58`

All four full-fold probe state and prediction identities also matched exactly.
The candidate therefore passed the identity precondition but not the speed
condition.

## Performance result and rejection

The native-only build improved the dominant logistic component by about
`1.07x`, which could not reach the full-fold gate by Amdahl's bound. LTO raised
the component result to `1.133x`: baseline median `5.0331` CPU seconds versus
candidate median `4.4428` CPU seconds.

The decisive full terminal-fold benchmark was:

| Build | CPU seconds | Median |
|---|---:|---:|
| installed baseline | 9.9252, 10.2166, 10.2411 | 10.2166 |
| native plus LTO | 9.9452, 9.8898, 9.4771 | 9.8898 |

The measured full-fold speedup was only `1.0330x`, or a 3.20% CPU reduction.
The required candidate median was at most 9.2878 seconds. The candidate missed
that line by 0.6020 seconds and was rejected.

Because the speed gate failed, the experiment stopped before immutable result-
artifact and journal-byte replay. No candidate source integration or binary
deployment was retained. The exact Round 11 implementation remains the
canonical live capability.

## Production observation

The live service remained the Round 11 Supervisor throughout the experiment:
invocation `2ba05ff3b4d043e5951921326def4dd7`, main PID 2364013, active/running,
zero restarts in the current invocation, 8.49 GiB observed memory, and 10.75
GiB current-invocation peak. Round 12 did not restart or mutate it.

## Integration matrix

| Mainline link | Round 12 evidence | Status |
|---|---|---|
| Goal | approved Engineering request #269 | complete |
| Resolver | production Resolver deliberately unchanged | not integrated |
| Ready Queue | production queue deliberately unchanged | not integrated |
| Supervisor | isolated benchmark only | not integrated |
| Capability | exact candidate missed the 1.10x gate | rejected |
| Artifacts | source/binary provenance and exact timing record | engineering evidence only |
| Status | negative Round 12 report | complete |
| Next task | profile the remaining exact terminal-fold cost | ready |
| Replay | not run after the speed gate failed | not applicable |

Mainline integration answer for the Round 12 candidate:

**NO — candidate rejected before integration; the validated Round 11 runtime
remains canonical.**

