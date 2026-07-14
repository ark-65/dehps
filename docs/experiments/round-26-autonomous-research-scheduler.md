# Round 26: Autonomous Research Scheduler

## Goal

Round 26 upgrades DEHPS from a system that can complete one autonomous research loop into a system that can decide the next research action.

The scheduler reads formal research state, applies waiting and budget policy, chooses exactly one next action, and creates at most one audited Research Scheduler Request.

## Implemented Surface

Worker package:

```text
apps/worker-python/dehps/research_scheduler/
```

CLI:

```text
dehps scheduler run
dehps scheduler once
dehps scheduler status
dehps scheduler queue
dehps scheduler next
```

API:

```text
GET /scheduler
GET /scheduler/queue
GET /scheduler/next
GET /scheduler/status
```

Schema:

```text
research_scheduler_queue
research_scheduler_request
schedule_research
```

## Scientific Guardrail

Einstein pass:

- Core question: can DEHPS choose the next research action from formal state without inventing work?
- Invariant: a scheduler decision may create only one audited Research Request and must not execute experiments, mutate code, mutate training, or update the Registry.
- Null: when forward coverage is insufficient or budget is exhausted, the correct action is WAIT or STOP, not another proposal.
- Measurement: next action, queue status, duplicate suppression, forward paired issue count, budget counters, open request count, and request uniqueness.
- Failure mode: prompt-driven scheduling, duplicate proposal loops, ignoring rejected families, continuing while forward evidence is immature, or creating work after budget is exhausted.
- Next experiment: later rounds can let approved scheduler requests trigger existing Proposal/Planning tools, but Round 26 stops at request creation.

## Validation

```text
cd apps/worker-python
.venv/bin/python -m pytest -q
872 passed in 19.56s

DB_PORT=1 .venv/bin/python -m pytest -q
872 passed in 20.54s

cd apps/api
npm test
94 passed

npm run build
passed
```

## Isolated Smoke Plan

Target database:

```text
dehps_round26_smoke
```

Required smoke flow:

```text
start from a completed Round 25 state
run scheduler next
verify insufficient forward evidence produces WAIT
verify no request is created for WAIT
run scheduler once with a formal forward-ready context
verify exactly one research_scheduler_request is created
run scheduler once again
verify no duplicate proposal/request is created
run scheduler once with exhausted budget
verify STOP
verify production database has no Round 26 writes
```

Smoke result:

```text
database: dehps_round26_smoke
base state: cloned from dehps_round25_smoke
setup: inherited non-terminal Agent Requests cancelled inside smoke database only

no-forward branch:
  action: wait_forward
  queue_status: waiting_forward
  reason_code: forward_evidence_insufficient
  scheduler_requests_created: 0

forward-ready branch:
  context source: temporary formal evidence root, no project runtime artifact modified
  first_action: create_proposal_request
  first_queue_status: proposal
  first_request_type: research_scheduler_request
  first_request_status: submitted
  second_action: wait_forward
  second_created_request: false
  scheduler_request_count: 1

budget-exhausted branch:
  action: stop
  queue_status: blocked
  reason_code: all_action_budgets_exhausted
  scheduler_request_count_after_stop: 1

production isolation:
  prod_scheduler_queue: 0
  prod_scheduler_requests: 0
```

The smoke confirms that Round 26 can WAIT, create one Research Scheduler Request when the forward gate is ready, avoid duplicate request generation, STOP when budget is exhausted, and leave the production database without Round 26 queue/request writes.

## Non-goals Confirmed

Round 26 does not:

- add a model
- add a feature
- modify training
- execute an Experiment
- modify Objective
- modify Candidate Source
- modify Promotion Gate
- modify production Supervisor
- auto-modify code at runtime
- auto-merge
- publish a release
