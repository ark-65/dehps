# Forward champion/challenger promotion — 2026-07-15

## Round contract

- Primary goal: close the gap between durable forward evaluations and config-bound champion promotion.
- Non-goals: no feature, score, weight, historical gate, or existing three-line policy change; no retroactive outcome reuse; no manual promotion route; no production migration or supervisor restart in the Engineering round.
- Authorization: Agent Request `engineering-forward-champion-challenger-9feb562` (request id 90, execution id 12).
- Starting commit: `9feb562`.
- Final authority: the existing `dehps.evaluation.PromotionGate`; the new code cannot bypass it.

## Root cause

Forward evaluation persistence was repaired, but the downstream aggregation remained deliberately hard-coded as:

```text
review_only = true
promotion_eligible = false
automatic_quarantine_release = false
```

The production runtime quarantined every historical non-initial promotion with `missing_forward_evidence`, yet no service converted durable unseen evaluations into a config-bound `EvaluationResult`. There was also no prospective fixed challenger: the dynamic KDJ lines can change effective configuration between issues, so their line-level totals cannot safely release a specific historical configuration.

## Implemented flow

```text
historical candidate
  -> must have pre-quarantine gate pass against the current incumbent hash
  -> create one durable accumulating cohort
  -> freeze incumbent/challenger config hashes and protocol
  -> export forward_challenger Top10000 before the draw
  -> automatic evaluation uses the same full ranking audit as official lines
  -> pair static_100 and forward_challenger by unseen target issue
  -> require 20 complete pairs
  -> validate config identity, candidate count, TopN equality, leakage and duplicates
  -> build incumbent/challenger forward EvaluationResult
  -> existing PromotionGate
  -> require no more than 3 consecutive challenger losses
  -> atomically promote or reject
```

Rejected or invalid challenger hashes are excluded from automatic reselection. A promoted challenger is written to the durable champion state and checkpointed through the existing supervisor-best storage path so subsequent prediction and carryover loading can see it.

The required `static_100`, `dynamic_kdj`, and `dynamic_kdj_near` lines remain unchanged. `forward_challenger` is an optional fourth, prospective-only diagnostic line. `show_latest_prediction.py` displays it when present but continues to compute consensus from the required three lines only.

## Fail-closed contract

Promotion is impossible unless all of the following are true:

- the historical frozen gate passed before quarantine and named the current incumbent config hash;
- exactly one active cohort exists;
- the cohort begins no earlier than its declared future activation issue;
- incumbent and challenger hashes remain constant;
- each paired issue has one accepted evaluation per line, complete candidates, equal TopN, a full model rank, and `leakage_passed=true`;
- at least 20 paired issues exist;
- the existing PromotionGate finds higher objective and primary hit score with no p95, worst-rank, tail-risk, or tail-count regression;
- the challenger does not lose more than three consecutive paired issues.

Terminal updates use `WHERE status='accumulating'`. Replaying the same accepted decision cannot publish a second champion or checkpoint.

## Database changes

`forward_promotion_cohorts` records the prospective contract, frozen configs and summaries, source protocol, progress, decision, and terminal status. A partial unique index permits only one accumulating cohort.

`forward_champion_state` stores the currently promoted production config and its source cohort. It references the cohort and is updated in the same transaction as the terminal decision and supervisor checkpoint.

The schema was executed against the live PostgreSQL engine inside a transaction, including candidate discovery, and then rolled back:

```text
schema columns: 26
eligible current challenger: none
after rollback: forward_promotion_cohorts = absent
after rollback: forward_champion_state = absent
```

The current database has no candidate satisfying the frozen historical gate against the current incumbent. Therefore deployment will create no cohort and will not promote the existing weak candidates. It will wait for a future legitimately eligible challenger.

## Validation

Focused promotion/evaluation/prediction tests:

```text
37 passed in 0.40s
```

Final full worker suite:

```text
980 passed in 44.41s
```

Production durable markers remained unchanged after transactional schema validation:

```text
training_round_results      10010  2026-07-14 22:12:08.512835+08
training_supervisor_best       11  2026-07-14 21:31:26.150290+08
forward runs for 2026081        3
forward candidates          30000
```

## Operational boundary

The Engineering round does not apply the schema or restart the supervisor. Production activation requires an approved database-migration Operator Request, followed by an approved supervisor restart and a live check that no cohort is created from the current ineligible historical rows. No promotion can be observed until a future candidate passes the historical gate and then completes 20 unseen paired issues.
