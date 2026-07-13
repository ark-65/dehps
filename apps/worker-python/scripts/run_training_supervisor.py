from __future__ import annotations

import sys

from dehps.training import runtime
from dehps.training.cli import main


if __name__ == "__main__":
    main()
else:
    # Preserve monkeypatch/import behavior for legacy library consumers while the
    # executable itself remains a minimal application entry point.
    sys.modules[__name__] = runtime
