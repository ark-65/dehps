# M4 V2 Marginal-Static Historical Execution — Round 54

Date: 2026-08-08

Role sequence: Research Agent -> Engineering Agent

Primary goal: implement the preregistered marginal-static historical executor
so that the immutable snapshot is loaded once, completed fold shards resume
without recomputation, and duplicate validation is removed from the fold and
resampling hot paths.

## Non-goals

- No formula, prior, threshold, seed, resampling family, or decision rule was
  changed after preregistration.
- Engineering did not query the historical database or inspect historical
  statistical results.
- No Evidence, accepted model, promotion, betting output, or production
  decision was created.
- The Gate Compiler remains a separate downstream task.

## Typed authorization

- Research Request 370 / Execution 291 froze the result-blind execution
  contract, including formulas, RNG, bootstrap, intervals, equivalence, MDE,
  power, and Holm rules.
- Engineering Request 371 / Execution 292 authorized implementation, additive
  DAG revision, synthetic live execution, status projection, deterministic
  replay, tests, and this report.
- Engineering validation used only a synthetic 3,481-row boundary fixture.

## Duplicate-validation removal

Validation now occurs at explicit trust boundaries rather than inside every
fold:

| Boundary | Validation | Frequency |
|---|---|---:|
| capability entry | registered source and six preregistration inputs | once |
| dataset load | immutable dataset identity and ordered records | once |
| resume | completion-index identity and one aggregate digest | once |
| fold loop | incremental score and six-count update | none |
| resampling loop | frozen arrays and deterministic child seed | none |
| finalization/replay | all immutable child bytes and registered identities | once |

The executor therefore performs zero database reads and writes per fold,
loads the dataset once, loads the completion index once, and keeps
`duplicate_validation=false`. This removes redundant work without removing
the entry, resume, artifact, or replay integrity boundaries.

The Einstein-style constraint was to preserve the falsifiable invariant: the
same frozen dataset, order, formulas, and child seeds must produce byte-equal
science artifacts whether execution is cold or resumed. Optimization was
accepted only after that invariant held.

## Execution and recovery contract

- One 33-count vector is initialized from the 900-issue training prefix.
- The vector advances once per settled target by updating only its six red
  counts.
- 2,581 evaluation folds are written as 11 immutable shards.
- 2,000 deterministic roots generate 16,000 resampling children through
  vectorized moving-block and stationary-bootstrap kernels.
- The operational completion index records verified shard state and score
  state. A resumed run restores the state directly and skips completed shards
  without directory scanning.
- An interruption after two shards restored and skipped 512 completed folds in
  the synthetic recovery test.
- Cold synthetic mainline execution completed in about 1.2 seconds; the
  execution-plus-full-replay test completed in about 3.2 seconds. These are
  implementation timings, not historical-effect results or a production ETA.

## Mainline artifacts implemented

The capability emits 16 immutable children plus one mainline execution record:

1. 11 fold shards;
2. one completion index;
3. one resampling result containing all 16,000 child identities;
4. one inference aggregate;
5. one still-undecided branch candidate;
6. one execution completion artifact;
7. one unified mainline execution record.

The completion record remains `evidence_created=false`. The newly added exact
next consumer is
`m4-v2-marginal-static-historical-measurement-gate-compiler`.

## Additive migration proof

The dry run against the durable Round 53 manifest returned `VERIFIED`:

- live tasks: 58;
- output tasks: 59;
- revised task: historical measurement execution only;
- added task: historical measurement Gate Compiler only;
- state regressions: 0;
- fact deletions: 0;
- task deletions: 0;
- unallowlisted definition rewrites: 0;
- projected output manifest:
  `60a03a0ce2a79da3e6ed0fb2ca20568262f2003af748d40ca18ecfa47a0395fa`;
- dry-run artifact:
  `aacba28f37dd46103fb7762b67b49fd43b2b5ad4b695708130f2edfe0261f560`.

## Validation

- Source contract and byte-integrity verification: PASS.
- Python compilation, Ruff, JSON parsing, and diff check: PASS.
- Round 54 focused tests: 8 passed.
- Synthetic Supervisor execution registered all 17 artifacts: PASS.
- Interrupted resume and corrupt-index fail-closed tests: PASS.
- Deterministic replay with byte-equal science artifacts: PASS.
- Complete non-retired Worker suite: 2,134 passed, 4 skipped (the four
  warnings are the existing Python 3.14 `fork()` deprecation warnings).
- Fresh merged Supervisor execution and durable replay: pending publication.

## Integration matrix

| Link | Engineering proof | Durable mainline proof |
|---|---|---|
| Goal -> Resolver | additive task and exact dependencies validate | pending import |
| Resolver -> Ready Queue | execution requires all eight frozen inputs | pending import |
| Ready Queue -> Supervisor | exact capability is registered | pending merged run |
| Supervisor -> Capability | synthetic full execution completes | pending merged run |
| Capability -> Artifacts | 16 children plus execution are deterministic | pending registration |
| Artifacts -> Status | execution metrics and Gate projection tested | pending projection |
| Status -> Next Task | exact Gate Compiler is the sole next consumer | pending Ready observation |
| Deterministic replay | all 17 identities replay locally | pending durable replay |

Final integration answer for this engineering checkpoint:

**NO — INTEGRATION_PENDING.**

The capability may advance to `VALIDATED_IN_MAINLINE` only after the ready PR
is merged, a fresh merged Supervisor executes the exact durable task once, all
17 artifacts are registered, the Gate Compiler becomes Ready, and replay
verifies the registered bytes without database I/O or duplicate validation.
