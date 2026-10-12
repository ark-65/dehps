"""Disposable real PostgreSQL fixture; never used by deployed workers."""

import json
import os
import signal
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dehps.execution.artifacts import ArtifactStore
from dehps.execution.context import RunContext
from dehps.execution.coordinator import Coordinator
from dehps.execution.database import DatabaseBinding
from dehps.execution.plan import ExecutionPlan
from dehps.execution.store import ExecutionAuthorization, ExecutionStore
from dehps.notifications.historical_calendar_recovery.capabilities import (
    build_capabilities,
)


def engine(config):
    root = Path(config["root"])
    store = ExecutionStore(
        DatabaseBinding(config["dsn"], config["database"], config["role"]),
        ArtifactStore(RunContext(root, config.get("domain", "learning"))),
        ExecutionAuthorization(**config["authorization"]),
        {},
    )
    p = ExecutionPlan(config["plan"])
    ctx = SimpleNamespace(
        inputs=root / "inputs",
        release=SimpleNamespace(digest=config["authorization"]["release_sha256"]),
    )
    return Coordinator(p, store, build_capabilities(p, store, ctx), lease_seconds=30)


if __name__ == "__main__":
    if sys.argv[2] == "replay-past-fixture":
        from dehps.notifications.historical_calendar_recovery.contract import DATES

        DATES["2026117"] = "2026-10-11"  # isolated synthetic temporal fixture only
    e = engine(json.loads(Path(sys.argv[1]).read_bytes()))
    from dehps.prediction.forward_learning import calculation

    calculation.fit_checkpoint = lambda *a, **kw: (_ for _ in ()).throw(
        AssertionError("mail must never train")
    )
    if sys.argv[2] == "kill-after-commit":
        original = e.store.commit

        def killed(*a, **kw):
            original(*a, **kw)
            os.kill(os.getpid(), signal.SIGKILL)

        e.store.commit = killed
    manifest = (
        e.replay(require_complete=False)
        if sys.argv[2].startswith("replay")
        else e.run()
    )
    print(
        json.dumps(
            {
                "run_id": e.run_id,
                "completed": sum(
                    s.declared_status.value == "completed" for s in manifest.task_states
                ),
                "task_errors": e.task_errors,
                "waits": e.wait_reasons,
            }
        )
    )
