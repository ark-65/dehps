# M4 isolated 24-hour challenger factory V11

## Status and boundary

This is a separate `RESEARCH_ONLY / SHADOW` lineage. It does not replace,
modify, tune, or feed Formal P3, and it has no P4, P5, P6, or Promotion
authority. Its frozen contract is
`M4_ISOLATED_24H_CHALLENGER_RESEARCH_FACTORY_CONTRACT_V11`, digest
`6d14bd57f290e9e0a625658bf0255cf33d1609efa68e667993cc58ccec8f7a02`.

Capability complete is not code complete. Before Operator import and a real
draw cycle, the required answer is:

> NO — INTEGRATION_PENDING

The final answer may become `YES — validated by unified mainline execution and
replay` only after the complete simulation and one real Tuesday, Thursday, or
Sunday cycle have registered and replayed all required artifacts, including
external provider-acknowledged predraw, postdraw, and 09:00 daily mail receipts.

## Runtime graph

The independent control plane renders exactly 42 task templates and registers
only exact task-key dispatch. Its core chains are:

1. preregistration -> target projection -> strict-prior history snapshot;
2. mail configuration verification -> search genesis;
3. atomic 18-candidate registration -> 18-worker execution -> batch replay ->
   checkpoint -> checkpoint replay;
4. 16:40 multiplicity seal -> eligibility -> 16:45 challenger freeze;
5. 1,000-portfolio legal-random baseline freeze and replay -> full-space Top-100
   prediction and replay;
6. 17:00 predraw envelope -> replay -> external delivery receipt;
7. audited draw -> settlement -> random baseline settlement -> legal Formal P3
   issue comparison or `PENDING_LEGAL_COMPARISON` -> report and replay ->
   external postdraw receipt;
8. daily 09:00 summary and immediate incident mail chains.

All source rows, features, fits, ranks, selections, and freezes use only issues
strictly earlier than the target. The legal red-ball space is exactly
`C(33,6) = 1,107,568`. Every attempted seed candidate is registered before its
first lease. A lease becomes an attempt only after its child process has
acknowledged startup; a preempted unstarted lease is released without consuming
retry or multiplicity. Retries preserve configuration and seed, and the lifetime
multiplicity limit is 1,000,000 with no partial batch at the boundary.

## Resource isolation and Formal P3 priority

The timer invokes one bounded cycle per minute. Search uses exactly 18 worker
processes and is limited by systemd to 1,800% CPU, `MemoryHigh=20G`, and
`MemoryMax=24G`.

Each worker has a 1 GiB RSS soft limit and a 1.25 GiB hard limit. The hard limit
terminates the whole deterministic round and consumes only acknowledged
attempts. The service invocation is bounded to 1 hour 45 minutes, below the
two-hour blackout before each 09:00 summary, 16:40 selection cut, 17:00 predraw
mail, and official-draw settlement window. If that outer bound terminates a
run, the next timer invocation recovers stale leases from PostgreSQL before
starting any new process; it never fabricates completion.

Before a search lease, the runner reads exactly these properties from
the user-manager unit `dehps-forward-prequential-successor.service` with
`systemctl --user show`:

`LoadState, ActiveState, SubState, MainPID, ControlPID`.

Only `loaded/inactive/dead/0/0` is quiescent. Any other state, query failure,
missing field, parse error, or unknown value means `PREEMPT`. A production
worker coordinator must stop new leases immediately, send SIGTERM to all 18
research workers, and send SIGKILL after five seconds to survivors. Resume
requires a new continuous 60-second quiescent interval. Formal P3 has no
dependency on this research line and continues autonomously if this line is
stopped or deleted.

## Email is a hard activation dependency

Opening the isolated line also opens its independent email downstream. Search
cannot obtain a lease unless a registered and replayed
`M4IsolatedMailConfigurationV11` has produced
`m4-isolated-24h-challenger-v11-mail-configuration:VERIFIED`.

Production configuration uses QQ SMTP with implicit TLS on `smtp.qq.com:465`.
The Operator-created user environment file
`/home/ark/.config/dehps/m4-isolated-24h-challenger-v11.env` must be mode
`0600` and contain:

```text
DEHPS_ISOLATED_V11_MAIL_FROM=sender@qq.com
DEHPS_ISOLATED_V11_MAIL_TO=recipient@example.com
DEHPS_ISOLATED_V11_SMTP_USERNAME=sender@qq.com
DEHPS_ISOLATED_V11_SMTP_PASSWORD=<QQ authorization code>
DEHPS_ISOLATED_V11_SMTP_HOST=smtp.qq.com
DEHPS_ISOLATED_V11_SMTP_PORT=465
DEHPS_ISOLATED_V11_SMTP_TLS=IMPLICIT_TLS
```

The current maximum audited `(issue, draw_date)` identity is resolved from
`ssq_history` in one repeatable-read snapshot on every timer cycle; it is not a
mutable environment setting. The target is the sequential issue successor on
the next Tuesday, Thursday, or Sunday after that actual audited date. Issue
numbers are never reconstructed by counting nominal draw weekdays from January
1, because historical suspension dates make that ordinal mapping false. The
rendered source date and target date are part of every affected task and replay
identity. This lets the additive issue DAG advance after each draw without a
manual unit edit.

Official holiday-adjusted historical draw dates remain authoritative even when
they are not Tuesday, Thursday, or Sunday. They retain all uniqueness, year,
ordering, schema, and content-integrity checks. In the existing three-component
Tuesday/Thursday/Sunday calendar feature, such a historical date is encoded as
exactly `0,0,0`; no category or feature dimension is added. Only a future target
date must be Tuesday, Thursday, or Sunday.

Secrets and plaintext recipients never enter artifacts or logs. Configuration
artifacts store only identity digests and the TLS/AUTH/NOOP provider result.
Each message has a content-addressed delivery key and deterministic Message-ID.
The ledger transitions `UNSENT -> SENDING` before the network call. `SENT`
requires a single authenticated TLS SMTP transaction and exact final DATA reply
code 250. Any post-call ambiguity is terminal `UNCERTAIN`; automatic retry is
forbidden. The PostgreSQL delivery ledger is append-only, and a delivery fact is
published only after the receipt artifact and its generic replay are registered.

Four independent downstreams are mandatory: predraw Top-100, postdraw
settlement, daily 09:00 summary, and immediate fail-closed incident alert.
Opening the research line without all four is forbidden. A missed predraw or
daily window opens an incident and sends the incident chain; it never backfills
an unverified predraw message.

Simulation always uses `FAKE_EPHEMERAL`, makes zero SMTP calls, and can never
emit an external `SENT` fact.

## Reports and accounting

Predraw mail is scheduled at 17:00 Asia/Shanghai on Tuesday, Thursday, and
Sunday. A challenger must be frozen by 16:45 from the 16:40 scientific cut.
The mail lists the exact 100 tickets and clearly states the hypothetical stake:
100 tickets x CNY 2 = CNY 200.

Postdraw readiness is polled every 15 minutes after the draw. The report lists
tier counts, gross prize, estimated tax, after-tax receipt, net, ROI, red/blue
hits, the 1,000 frozen legal-random portfolio comparison, and an issue-specific
Formal P3 comparison or an explicit pending marker.

The frozen estimate is:

- gross prize at or below CNY 10,000: estimated tax CNY 0;
- gross prize above CNY 10,000: estimated tax is 20% of the full gross;
- net = estimated after-tax receipt - CNY 200;
- ROI = net / CNY 200.

Actual withholding remains authoritative.

Daily research mail is sent exactly once at 09:00 Asia/Shanghai. It includes
attempt, retry, family, multiplicity, eligibility, resource, checkpoint,
replay, incident, recovery, and next-freeze status.

## Engineering verification

Run from the repository root:

```bash
apps/worker-python/.venv/bin/python -m pytest -q \
  apps/worker-python/tests/test_m4_isolated_challenger_v11_contract.py \
  apps/worker-python/tests/test_m4_isolated_challenger_v11_search.py \
  apps/worker-python/tests/test_m4_isolated_challenger_v11_mainline.py \
  apps/worker-python/tests/test_m4_isolated_challenger_v11_mail.py \
  apps/worker-python/tests/test_m4_isolated_challenger_v11_runner.py
apps/worker-python/.venv/bin/ruff check \
  apps/worker-python/dehps/research_os/information_theory/measurement_system_v2/isolated_challenger_v11_*.py \
  apps/worker-python/dehps/notifications/isolated_challenger_v11.py \
  apps/worker-python/scripts/build_m4_isolated_24h_challenger_v11_manifest.py \
  apps/worker-python/scripts/run_m4_isolated_24h_challenger_v11.py
```

The result-blind simulation command is intentionally non-production:

```bash
apps/worker-python/.venv/bin/python \
  apps/worker-python/scripts/run_m4_isolated_24h_challenger_v11.py \
  simulate --source-max-issue YYYYNNN --source-max-draw-date YYYY-MM-DD
```

## Operator-only deployment sequence

No command in this section is Engineering authorization. A new approved
Operator Request must bind the exact merged commit, source contract, target
projection, database migration, nonsecret mail configuration identity, unit
paths, and rollback steps before any of the following may run.

1. apply `003_m4_isolated_24h_challenger_v11.sql`;
2. run the source loader and result-blind simulation; the additive install then
   seals the exact database schema version, contract digest, and initial merged
   commit. A reviewed descendant repair may reuse that immutable schema only
   when Git proves the installation commit is its ancestor;
3. install the independent control-plane manifest with `install --apply`;
4. execute the mail TLS/AUTH/NOOP configuration task and verify the registered
   `VERIFIED` fact;
5. install and enable only the new V11 service and timer;
6. verify `ACTIVE_RESEARCH_ONLY`, the 18-worker cap, Formal P3 priority, and no
   changes to Formal P3/P4/P5/P6/Promotion;
7. observe one real draw cycle and retain replay-bound external predraw,
   postdraw, and daily `SENT` receipts.

Rollback disables only the two new V11 units and stops new isolated leases. It
does not delete manifests, artifacts, registrations, receipts, or any Formal P3
state.
