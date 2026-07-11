from __future__ import annotations

import json

from dehps.runtime.storage_capacity import runtime_storage_capacity_summary


def main() -> None:
    summary = runtime_storage_capacity_summary()
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    if summary.get("status") in {"critical", "unavailable"}:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
