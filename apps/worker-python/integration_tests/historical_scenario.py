"""Disposable engineering fixture, using the actual coordinator and PostgreSQL."""
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import os
import signal

from dehps.execution.artifacts import ArtifactStore
from dehps.execution.context import RunContext
from dehps.execution.coordinator import Coordinator
from dehps.execution.database import DatabaseBinding
from dehps.execution.plan import ExecutionPlan
from dehps.execution.store import ExecutionAuthorization, ExecutionStore
from dehps.prediction.historical_learning.capabilities import build_capabilities


def engine(config):
    root = Path(config['root'])
    store = ExecutionStore(DatabaseBinding(config['dsn'], config['database'], config['role']),
        ArtifactStore(RunContext(root, config.get('domain', 'learning'))), ExecutionAuthorization(**config['authorization']), {})
    plan = ExecutionPlan(config['plan'])
    context = SimpleNamespace(inputs=root/'inputs', code_root=Path(__file__).resolve().parents[3],
                              release=SimpleNamespace(digest=config['authorization']['release_sha256']))
    return Coordinator(plan, store, build_capabilities(plan, store, context), lease_seconds=config.get('lease_seconds', 30))


if __name__ == '__main__':
    from dehps.prediction.forward_learning import calculation
    config = json.loads(Path(sys.argv[1]).read_bytes())
    e = engine(config)
    fit = calculation.fit_checkpoint
    def recorded(*args, **kwargs):
        with (Path(config['root'])/'fit-calls').open('a') as stream:
            stream.write(str(args[1])+'\n')
        return fit(*args, **kwargs)
    calculation.fit_checkpoint = recorded
    if sys.argv[2] == 'replay':
        def no_fit(*args, **kwargs):
            raise AssertionError('readonly historical replay invoked fitting')
        calculation.fit_checkpoint = no_fit
        manifest = e.replay(require_complete=False)
    else:
        if sys.argv[2] == 'kill-after-update':
            commit = e.store.commit
            def interrupted(*args, **kwargs):
                result = commit(*args, **kwargs)
                if (Path(config['root'])/'fit-calls').exists():
                    os.kill(os.getpid(), signal.SIGKILL)
                return result
            e.store.commit = interrupted
        manifest = e.run()
    print(json.dumps({'run_id': e.run_id, 'manifest_digest': manifest.artifact_digest,
        'completed': [t.task_key for t in manifest.tasks if manifest.task_state_by_digest[t.artifact_digest].declared_status.value == 'completed'],
        'wait_reasons': e.wait_reasons}))
