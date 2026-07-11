# 双色球 Data Sources

## Current Sources

- `zhcw`: public China Welfare Lottery / 中彩网 style pages or open JSON endpoints, accessed once per manual run or scheduled daily run.
- `csv`: explicit local CSV import path for controlled backfills or tests. No sample CSV is bundled.

## Fields

- `issue`: draw issue, for example `2026001`.
- `draw_date`: draw date in `YYYY-MM-DD`.
- `red_numbers`: six sorted red balls from 1 to 33.
- `blue_number`: blue ball from 1 to 16.
- `source`: source identifier.

## Stability Risks

Public pages can change HTML structure or API response shape. The crawler logs response snippets when parsing fails so failures are inspectable.

## Request Policy

The crawler uses a clear User-Agent, timeout, and at most two retries by default. It does not bypass login, crack interfaces, run concurrent scraping, or make high-frequency requests.

## Historical Sync

Use the real source for normal operation:

```bash
cd apps/worker-python
python scripts/sync_latest_ssq.py --source zhcw --history --dry-run
python scripts/sync_latest_ssq.py --source zhcw --history
```

Without issue bounds, `zhcw --history` fetches the current system date minus 10 years through the current system date.

## Explicit CSV Import

Use:

```bash
cd apps/worker-python
python scripts/import_history_csv.py --file /absolute/path/to/history.csv
python scripts/sync_latest_ssq.py --source csv --history --csv-file /absolute/path/to/history.csv
```

CSV is intentionally explicit so repository checkouts do not carry stale sample issue data.

## Conflict Policy

The same issue with the same numbers is treated as idempotent. The same issue with different red or blue numbers is written to `ssq_data_conflicts` and the existing canonical row is not overwritten.

Unresolved conflicts stop forward evaluation, advisor refresh, and supervisor startup. After an operator verifies the authoritative draw, resolve one conflict group without deleting evidence:

```bash
cd apps/worker-python
.venv/bin/python scripts/resolve_ssq_data_conflict.py \
  --conflict-id 123 \
  --accept existing \
  --resolution-note "verified against official draw notice" \
  --resolved-by "operator-name"
```

Use `--accept incoming` only when the incoming side was independently verified. The command locks both the conflict and canonical draw, rejects stale third-state data, updates the canonical draw only when required, and marks matching duplicate conflict evidence resolved. It never deletes conflict records. Autonomous self-iteration must not run this command.
