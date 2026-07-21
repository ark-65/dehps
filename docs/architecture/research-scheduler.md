# Autonomous Research Scheduler

> Implementation status: this document describes the Round 26 v1 scheduler. Its global forward and
> open-request waiting behavior is not the target control plane. The accepted successor architecture
> is [Goal-Driven Research Orchestrator](goal-driven-research-orchestrator.md), which scopes waits to
> typed Task dependencies under a durable Goal Graph.

Round 26 adds the first DEHPS component that decides what research work should happen next.

The scheduler is intentionally narrow:

```text
formal state -> one next action -> optional Research Scheduler Request
```

It does not execute experiments, modify code, modify training, update the Registry, promote production, or bypass Reviewer/Operator gates.

## Inputs

The scheduler reads formal state only:

- Hypothesis Registry families, hypotheses, experiments, evidence, and decisions.
- Agent Requests and active request state.
- Scheduler queue state.
- Training round summaries.
- Formal training-watch evidence for forward coverage.
- Sequential null audit state.
- Rejected families and rejected hypotheses through `ResearchContext`.
- Budget counters for proposal, experiment, and forward quota.

It does not read prompts, Markdown conclusions, or chat history as scheduling evidence.

## Queue

Persistent queue rows live in `research_scheduler_queue`.

Supported queue statuses:

```text
proposal
planning
engineering
operator
waiting_forward
review
completed
blocked
```

Open queue rows are de-duplicated by action and target. This is the main guard against infinite proposal or experiment generation.

## Actions

The scheduler emits exactly one `NextResearchAction`:

```text
create_proposal_request
create_planning_request
create_engineering_request
create_operator_request
create_review_request
wait_forward
block
stop
continue_existing
```

Only the `create_*_request` actions create a submitted `research_scheduler_request` Agent Request.

WAIT, BLOCK, STOP, and CONTINUE do not create new research work.

## Forward Waiting Policy

Forward coverage is a hard gate. If formal forward evidence is not review-ready or has fewer paired issues than the declared minimum, the scheduler chooses:

```text
wait_forward
```

This prevents the system from spending compute on additional proposals before the existing validation obligation has matured.

This is preserved as historical v1 behavior, not as a v2 invariant. In the Goal-driven architecture,
forward coverage gates only Tasks whose declared evidence or authority depends on that coverage.
Unrelated Replay, benchmark, diagnostics, Runtime-capability, and Maintenance Tasks remain eligible.

## Budget Policy

The budget manager tracks:

- CPU slots
- memory budget
- GPU slots
- daily experiment quota
- forward quota
- proposal quota

If all research-producing actions are out of budget, the scheduler chooses:

```text
stop
```

No request is created in that case.

## Authority Boundary

Round 26 adds:

```text
AgentAction.SCHEDULE_RESEARCH
AgentRequestType.RESEARCH_SCHEDULER_REQUEST
```

Only the Research role can create and execute this request type. Reviewer still reviews requests. The request payload explicitly records non-goals:

- do not execute experiment
- do not modify code
- do not modify Registry
- do not modify training
- do not promote production

The scheduler request is a handoff declaration: "this is the next research thing to prepare." It is not an experiment run.

## API

The API is read-only:

```text
GET /scheduler
GET /scheduler/queue
GET /scheduler/next
GET /scheduler/status
```

These endpoints read queue state and latest scheduler decisions. They do not run the scheduler and do not create queue rows or Agent Requests.
