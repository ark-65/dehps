# Training Runtime Architecture

The refactored runtime separates application orchestration from frozen training facts and policy decisions:

```text
scripts/run_training_supervisor.py
  -> training.cli
  -> TrainingSupervisor
  -> TrainingRoundRunner
       -> CandidateSearchPolicy
       -> AdvisorRegistry
       -> RoundEvaluationPipeline
       -> PromotionGate
       -> TrainingRepository
       -> ArtifactWriter
       -> TrainingEventPublisher
```

The executable entry parses compatible CLI arguments, builds settings and dependencies, and starts `TrainingSupervisor`. Heavy-job locking and lifecycle completion belong to the supervisor. A `TrainingRoundRunner` accepts an immutable `TrainingRoundRequest`, loads a frozen context through the repository, obtains candidate proposals, evaluates them, calls the promotion gate, persists the result, writes artifacts, and publishes the event.

No `TrainingRoundRunner` dependency is constructed internally. In particular it cannot create a PostgreSQL connection, HTTP client, or multiprocessing pool. Tests use in-memory fakes for every boundary.

Candidate proposals retain `source_key` and `protocol_version`. Objective facts use `EvaluationResult`; promotion uses the separate `PromotionDecision` with stable reason codes. Invalid experiments, leakage failures, unacceptable baseline overlap, and missing forward evidence fail closed.

The mechanically migrated `dehps.training.runtime` currently contains the established ranking/backtest implementation and compatibility helpers. It is not a new strategy layer. Its remaining extraction into production `TrainingRoundRunner` dependencies is tracked as an acceptance item; the architecture is not considered complete while the live loop bypasses the runner.
