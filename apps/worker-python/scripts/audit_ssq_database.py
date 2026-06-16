from __future__ import annotations

import argparse
import json
from pathlib import Path

from dehps.config import ROOT_DIR
from dehps.db import get_connection
from dehps.storage.postgres_store import (
    TOTAL_SSQ_RED_COMBINATIONS,
    audit_ssq_history,
    count_red_combination_universe,
)


def render_audit_report(audit: dict) -> str:
    history = audit["history"]
    combinations = audit["red_combination_universe"]
    return f"""# SSQ Database Audit

## History

- total_draws: {history["total_draws"]}
- issue_range: {history["min_issue"]} to {history["max_issue"]}
- draw_date_range: {history["min_draw_date"]} to {history["max_draw_date"]}
- duplicate_issue_count: {len(history["duplicate_issues"])}
- id_issue_monotonic: {history["id_issue_monotonic"]}

## Red Combination Universe

- total_rows: {combinations["total_rows"]}
- expected_total_rows: {combinations["expected_total_rows"]}
- complete_universe: {combinations["complete_universe"]}

## Latest Issues

```json
{json.dumps(history["latest_10_by_issue"], ensure_ascii=False, indent=2)}
```
"""


def run_audit(*, output_dir: Path | None = None) -> dict:
    with get_connection() as conn:
        history_audit = audit_ssq_history(conn)
        combination_count = count_red_combination_universe(conn)

    audit = {
        "history": history_audit,
        "red_combination_universe": {
            "total_rows": combination_count,
            "expected_total_rows": TOTAL_SSQ_RED_COMBINATIONS,
            "complete_universe": combination_count == TOTAL_SSQ_RED_COMBINATIONS,
        },
    }
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        key = f"ssq-database-audit-{history_audit['max_issue'] or 'empty'}"
        json_path = output_dir / f"{key}.json"
        report_path = output_dir / f"{key}.md"
        json_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2))
        report_path.write_text(render_audit_report(audit))
        audit["json_path"] = str(json_path)
        audit["report_path"] = str(report_path)
    return audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT_DIR / "data/output/audits")
    parser.add_argument("--no-output", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run_audit(output_dir=None if args.no_output else args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
