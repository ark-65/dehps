from __future__ import annotations

import json

from dehps.forward_checkpoint import seal_2026084_checkpoint


def main() -> int:
    print(json.dumps(seal_2026084_checkpoint(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
