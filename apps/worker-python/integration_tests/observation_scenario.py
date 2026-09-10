"""Real observation capability in a disposable, authenticated PostgreSQL domain.

This process fixture does not attest an image; fixed-release launch is a separate
acceptance gate. Only the scoped operator credentials enter the child process.
"""
import json
import os
from pathlib import Path
import signal
import sys
from types import SimpleNamespace

from dehps.execution.artifacts import ArtifactStore
from dehps.execution.context import RunContext
from dehps.execution.coordinator import Capability, Coordinator
from dehps.execution.database import DatabaseBinding
from dehps.execution.entry import CapabilityContext
from dehps.execution.plan import ExecutionPlan
from dehps.execution.store import ExecutionAuthorization, ExecutionStore
from dehps.prediction.observation_execution import build_capabilities


def coordinator(config, mode='normal'):
    root = Path(config['root'])
    store = ExecutionStore(
        DatabaseBinding(config['dsn'], config['database'], config['role']),
        ArtifactStore(RunContext(root, 'learning')),
        ExecutionAuthorization(**config['authorization']), {},
    )
    plan = ExecutionPlan(config['plan'])
    context = CapabilityContext(root / 'inputs', Path(__file__).resolve().parents[3],
                                SimpleNamespace(digest=config['authorization']['release_sha256']))
    caps = build_capabilities(plan, store, context)
    instrumented = {}
    for name, cap in caps.items():
        def execute(task, parents, artifacts, cap=cap):
            with open(root / (task.task_key + '.calls'), 'ab') as stream:
                stream.write(b'compute\n'); stream.flush(); os.fsync(stream.fileno())
            if mode == 'before_report' and task.task_key.endswith('-report'):
                os.kill(os.getpid(), signal.SIGKILL)
            return cap.execute(task, parents, artifacts)
        instrumented[name] = Capability(cap.verifier_id, cap.verify, execute)
    return Coordinator(plan, store, instrumented, lease_seconds=1)


if __name__ == '__main__':
    assert 'DEHPS_EXECUTION_TEST_ADMIN_DSN' not in os.environ
    config = json.loads(Path(sys.argv[1]).read_text())
    mode = sys.argv[2]
    engine = coordinator(config, mode)
    result = engine.replay() if mode == 'replay' else engine.run()
    print(json.dumps({'run_id': engine.run_id, 'manifest': result.to_dict(),
                      'projection_errors': engine.projection_errors}))
