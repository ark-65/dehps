# M4-P3 Top-100 replay-bound mail and monetary-return runtime

## Round objective

Deploy a downstream notification capability for the already-frozen successor P3
portfolio.  It sends the 100 registered model tickets after the 17:00 replay gate
on Tuesday, Thursday, and Sunday, then sends one post-draw report after the exact
P3 settlement replay and complete issue-specific prize data are both available.

The notification runtime does not alter or select P3 tickets.  It does not read
legacy `static_100`, `dynamic_kdj`, `dynamic_kdj_near`, or Prediction-v2 output.

## Monetary contract

- 100 tickets at CNY 2.00 each: **hypothetical input CNY 200.00**.
- First and second prizes use the exact issue's `winnerDetails.awardMoney`.
- Third through sixth prizes must equal CNY 3,000 / 200 / 10 / 5 per ticket.
- All hypothetical prizes are aggregated as one natural person's income for the
  same computer-lottery game and issue.
- Gross prize at or below CNY 10,000.00 has estimated tax CNY 0.00.
- Gross prize above CNY 10,000.00 has estimated tax equal to 20% of the full gross.
- The report shows gross prize, estimated tax, after-tax receipt, net after the
  CNY 200.00 cost, and ROI.  Actual withholding and redemption records remain
  authoritative.

The tax rule is bound to the Ministry of Finance / State Taxation Administration /
Ministry of Civil Affairs / General Administration of Sport Announcement 2024
No. 12: <https://fgk.chinatax.gov.cn/zcfgk/c102416/c5233840/content.html>.

## Fail-closed delivery sequence

```text
registered P3 candidate/checkpoint/predraw replay
  -> notification pre-envelope task
  -> typed pre replay
  -> generic Research Evidence Supervisor replay
  -> idempotent QQ delivery ledger

registered P3 settlement/settlement replay + exact issue winnerDetails
  -> registered payout source + post-return report task
  -> typed post replay
  -> generic Research Evidence Supervisor replay
  -> idempotent QQ delivery ledger
```

The delivery ledger uses `sending`, `sent`, and `uncertain`.  A connection or
SMTP exception after `sending` becomes `uncertain`; automatic retry is forbidden
because server acceptance could be ambiguous.

## Operator commands

All commands run from the repository root.  They require the existing QQ mail
environment variables but never print their values.

```bash
apps/worker-python/.venv/bin/python \
  apps/worker-python/scripts/run_m4_p3_top100_notification.py install

apps/worker-python/.venv/bin/python \
  apps/worker-python/scripts/run_m4_p3_top100_notification.py install --apply

apps/worker-python/.venv/bin/python \
  apps/worker-python/scripts/run_m4_p3_top100_notification.py status

apps/worker-python/.venv/bin/python \
  apps/worker-python/scripts/run_m4_p3_top100_notification.py pre --apply --deliver

apps/worker-python/.venv/bin/python \
  apps/worker-python/scripts/run_m4_p3_top100_notification.py post --apply --deliver
```

The two production timers are:

- `dehps-p3-top100-pre-draw-mail.timer`: `Tue,Thu,Sun 17:00 Asia/Shanghai`.
- `dehps-p3-top100-post-draw-mail.timer`: persistent 15-minute readiness poll.

The initial manifest records the latest completed P3 predraw issue as
`minimum_issue`, preventing deployment from sending historical post-draw mail.

## Runtime sufficiency

The P3 runtime remains `outer=1`, `inner=1`, `affinity=all`, with CPU affinity
0-21.  The selected deterministic reference median is 0.087912 seconds; `inner=2`
was slower at 0.101389 seconds.  The observed full settlement-to-next-replay
cycle was about 254 seconds against a 900-second scheduler interval (about 3.54x
headroom).  Therefore the current autonomous training runtime has sufficient
time; this round does not change concurrency or any P3 scientific identity.

## Mainline integration matrix

| Contract link | Implementation |
| --- | --- |
| Goal | `M4_P3_TOP100_REPLAY_BOUND_MAIL_AND_RETURN_V1` |
| Resolver / Ready Queue | separate `m4-p3-top100-notification` manifest |
| Supervisor | notification-only `ResearchEvidenceSupervisor` subclass |
| Capabilities | pre envelope/replay and post report/replay |
| Immutable artifacts | envelope, payout source, return report, typed replays |
| Status | installed/armed, per-task state, ready queue, delivery ledger |
| Downstream consumer | QQ transport only after typed and generic replay |
| Scientific effect | zero; P3 source entries and decision semantics unchanged |

Engineering answer before production deployment: **NO — INTEGRATION_PENDING**.
The code and fixture replay are complete, but production is complete only after a
separately approved Operator execution imports the control plane, enables the
timers, and verifies the merged-main runtime.
