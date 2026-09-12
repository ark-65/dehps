"""Synthetic compressed calendar only; all persistence and clocks remain real."""
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
import json
import os
import sys

from dehps.execution.artifacts import ArtifactStore
from dehps.execution.context import RunContext
from dehps.execution.coordinator import Coordinator
from dehps.execution.database import DatabaseBinding
from dehps.execution.plan import ExecutionPlan
from dehps.execution.store import ExecutionAuthorization, ExecutionStore
from dehps.prediction.forward_learning import contract as contract_module
from dehps.prediction.forward_learning.capabilities import build_capabilities


def engine(config):
    # Only replace the business calendar's 17:00/21:15 schedule in this fixture.
    # No production clock, authority, store, transaction or registration mock.
    contract_module.validate_calendar_times = lambda cutoff, draw: None
    root = Path(config['root'])
    store = ExecutionStore(DatabaseBinding(config['dsn'], config['database'], config['role']),
        ArtifactStore(RunContext(root, config.get('domain', 'learning'))), ExecutionAuthorization(**config['authorization']), {})
    packet = ExecutionPlan(config['plan'])
    context = SimpleNamespace(inputs=root/'inputs', code_root=Path(__file__).resolve().parents[3],
                              release=SimpleNamespace(digest=config['authorization']['release_sha256']))
    return Coordinator(packet, store, build_capabilities(packet, store, context), lease_seconds=30)


if __name__ == '__main__':
    config = json.loads(Path(sys.argv[1]).read_text())
    e = engine(config)
    if sys.argv[2] == 'replay':
        from dehps.prediction.forward_learning import calculation
        def no_fitting(*args, **kwargs):
            raise AssertionError('readonly replay invoked fitting')
        calculation.fit_checkpoint = no_fitting
        manifest = e.replay(require_complete=False)
    else:
        manifest = e.run()
    print(json.dumps({'run_id': e.run_id, 'completed': [t.task_key for t in manifest.tasks
                     if manifest.task_state_by_digest[t.artifact_digest].declared_status.value == 'completed'],
                     'wait_reasons': e.wait_reasons}))
