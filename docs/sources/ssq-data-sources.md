# 双色球 Data Sources

## Current Sources

- `zhcw`: public China Welfare Lottery / 中彩网 style pages or open JSON endpoints, accessed once per manual run or scheduled daily run.
- `csv`: local CSV fallback for initializing or testing history data.

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

## CSV Fallback

Use:

```bash
cd apps/worker-python
python scripts/sync_latest_ssq.py --source csv --history
```

The CSV source reads `data/raw/ssq_history_sample.csv` by default and can be extended to a full historical CSV.

## Conflict Policy

The same issue with the same numbers is treated as idempotent. The same issue with different red or blue numbers is written to `ssq_data_conflicts` and the existing canonical row is not overwritten.

