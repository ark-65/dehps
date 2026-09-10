"""Real finite-learning process fixture, with only isolated operator credentials."""
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
from dehps.prediction.learning_execution import build_capabilities
from dehps.prediction.frozen_learning import calculation as core, analysis


def coordinator(config, mode='normal'):
    root = Path(config['root'])
    store = ExecutionStore(DatabaseBinding(config['dsn'], config['database'], config['role']),
                           ArtifactStore(RunContext(root, 'learning')),
                           ExecutionAuthorization(**config['authorization']), {})
    plan = ExecutionPlan(config['plan'])
    context = CapabilityContext(Path(config['input_root']), Path(__file__).resolve().parents[3],
                                SimpleNamespace(digest=config['authorization']['release_sha256']))
    capabilities = build_capabilities(plan, store, context)
    instrumented = {}
    for name, capability in capabilities.items():
        def execute(task, parents, artifacts, capability=capability):
            with open(root / (task.task_key + '.calls'), 'ab') as stream:
                stream.write(b'compute\n'); stream.flush(); os.fsync(stream.fileno())
            if mode == 'before_evaluate' and task.task_key.endswith('-evaluate'):
                os.kill(os.getpid(), signal.SIGKILL)
            return capability.execute(task, parents, artifacts)
        instrumented[name] = Capability(capability.verifier_id, capability.verify, execute)
    # Only the deliberately killed admission needs a short expiry. Normal
    # numerical work uses the same 30 s lease as the installed image: native
    # computation and cold compilation need not yield to Python every second.
    return Coordinator(plan, store, instrumented,
                       lease_seconds=1 if mode == 'before_evaluate' else 30)


if __name__ == '__main__':
    assert 'DEHPS_EXECUTION_TEST_ADMIN_DSN' not in os.environ
    config = json.loads(Path(sys.argv[1]).read_text())
    mode = sys.argv[2]
    original_refit = analysis.refit_checkpoint
    def refit(*args, **kwargs):
        with open(Path(config['root']) / 'actual-checkpoint-fits.calls', 'ab') as stream:
            stream.write(b'fit\n'); stream.flush(); os.fsync(stream.fileno())
        return original_refit(*args, **kwargs)
    analysis.refit_checkpoint = refit
    if mode == 'replay':
        def forbidden_computation(*args, **kwargs):
            raise AssertionError('committed learning replay must not fit, search or resample')
        core.fit = forbidden_computation
        core.evaluate_issue = forbidden_computation
        core.scores = forbidden_computation
        analysis.paired_interval = forbidden_computation
    engine = coordinator(config, mode)
    manifest = engine.replay() if mode == 'replay' else engine.run()
    print(json.dumps({'run_id': engine.run_id, 'manifest': manifest.to_dict(), 'projection_errors': engine.projection_errors}))
