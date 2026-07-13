# Training Runtime Architecture

The refactored runtime separates application orchestration from frozen training facts and policy decisions:

```text
scripts/run_training_supervisor.py
  -> training.cli
  -> ProductionTrainingSession.next_request()
  -> TrainingSupervisor
  -> TrainingRoundRunner.run(request)
  -> ProductionRuntimeRoundExecutor.execute(request, state)
       -> CandidateSourceComposer
       -> RuntimeAdvisorOrchestrator -> AdvisorRegistry
       -> runtime evaluation
       -> RuntimeEvaluationNormalizer -> promotion decision
       -> round persistence
       -> status/report event publication
```

The executable entry parses compatible CLI arguments, builds settings and dependencies, and starts `TrainingSupervisor`. Heavy-job locking and lifecycle completion belong to the supervisor. A `TrainingRoundRunner` accepts an immutable `TrainingRoundRequest`, loads a frozen context through the repository, obtains candidate proposals, evaluates them, calls the promotion gate, persists the result, writes artifacts, and publishes the event.

No `TrainingRoundRunner` dependency is constructed internally. In particular it cannot create a PostgreSQL connection, HTTP client, or multiprocessing pool. Tests use in-memory fakes for every boundary.

Candidate proposals retain `source_key` and `protocol_version`. Objective facts use `EvaluationResult`; promotion uses the separate `PromotionDecision` with stable reason codes. Invalid experiments, leakage failures, unacceptable baseline overlap, and missing forward evidence fail closed.

`dehps.training.runtime` now contains established ranking/backtest helpers and compatibility facades; it no longer contains the production round loop. Run-scoped initialization lives in `production_runtime.build_production_training_session`, mutable continuity lives in `RuntimeTrainingState`, and one round lives in `ProductionRuntimeRoundExecutor.execute(request, state)`.

The production CLI does not construct or advance a generator. `TrainingSupervisor` obtains an explicit request from the persistent session and calls `TrainingRoundRunner.run(request)`. The old `iter_supervisor_rounds()` API remains only as a compatibility facade for legacy imports; it consumes the same session/executor API and is not wired into production dependencies.

All four production advisor sources—Weight KDJ, Ridge KDJ, Neural KDJ, and Target Weight Inversion—enter one `AdvisorRegistry` call with stable source and protocol metadata. Candidate source composition is centralized in `CandidateSourceComposer`; evaluation normalization and historical-holdout quarantine are centralized in `RuntimeEvaluationNormalizer`.
