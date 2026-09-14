"""Full frozen-data engineering acceptance in disposable PostgreSQL only.

This harness is not a production admission or a competing training path. It
uses the same Coordinator, claims, registrations, consumers and replay as entry.
The fixture enforces the explicit dehps_execution_test_admin database boundary.
"""
import argparse
from contextlib import contextmanager
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
import gzip
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from threading import Event, Thread
import time

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from dehps.execution.plan import ExecutionPlan
from dehps.execution.store import ExecutionAuthorization
from dehps.prediction.forward_learning.operations import signing_key
from dehps.prediction.historical_learning.contract import Inputs, digest
from dehps.prediction.historical_learning.publisher import publish_dispatch, publish_observations
from dehps.prediction.historical_learning.plan import CAPABILITIES
from conftest import authority_fixture
from historical_scenario import engine
from test_execution_mainline import mainline_fixture, records


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)); path.chmod(0o600)


def dump(admin, output):
    tables = ['execution_authority.requests', 'execution_authority.approvals', 'execution_authority.executions',
        'execution_authority.identities', 'execution_authority.revocations',
        'execution_store.request_plan_index', 'execution_store.request_task_specs', 'execution_store.task_inputs',
        'execution_store.plans', 'execution_store.tasks', 'execution_store.attempts', 'execution_store.commits',
        'public.research_os_goal_definitions', 'public.research_os_task_definitions',
        'public.research_os_mainline_execution_events', 'public.research_os_mainline_artifacts']
    with psycopg.connect(admin) as connection, gzip.open(output, 'wt') as stream:
        for table in tables:
            if connection.execute('SELECT to_regclass(%s)', (table,)).fetchone()[0] is None:
                continue
            for row in connection.execute(sql.SQL('SELECT to_jsonb(t) FROM {} t').format(sql.Identifier(*table.split('.')))):
                stream.write(json.dumps({'table': table, 'row': row[0]}, ensure_ascii=True)+'\n')
    output.chmod(0o600)


def authorize(identities, root, packet):
    clients, _, _, _ = identities
    release = 'a'*64  # explicit engineering fixture, not a fixed production release
    request = clients['engineer'].request(packet.payload, release, label='ENGINEERING_663_DISPOSABLE_REAL_DATA_TEST')
    content = clients['reviewer'].get(request)['content_sha256']
    clients['reviewer'].approve(request, content, release, datetime.now(timezone.utc)+timedelta(hours=24), label='FIXTURE_ONLY')
    execution = clients['operator'].begin(request, content, release, label='FIXTURE_ONLY')
    binding = clients['operator'].database
    return dict(dsn=binding.dsn, database=binding.database, role=binding.role, root=str(root), plan=packet.payload,
        authorization=asdict(ExecutionAuthorization(execution, content, release)), lease_seconds=300)


def run(inputs_root, output, key_file):
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    key = signing_key(key_file)
    candidate = Path(__file__).resolve().parents[3]
    write(output/'source-identity.json', {'scope': 'ENGINEERING_FIXTURE_NOT_PRODUCTION_ACTIVATION',
        'files': {str(p.relative_to(candidate)): sha256(p.read_bytes()).hexdigest()
                  for p in (candidate/'apps/worker-python/dehps').rglob('*.py')},
        'inputs_sha256': sha256((inputs_root/'contract.json').read_bytes()).hexdigest()})
    roots = {d: output/d for d in ('learning', 'observer')}
    for root in roots.values():
        root.mkdir(mode=0o700)
        # Immutable frozen sources can share inodes; mutable projections are new.
        shutil.copytree(inputs_root, root/'inputs', copy_function=os.link)
        (root/'inputs/formal-cgroups').symlink_to('/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice')
    with contextmanager(authority_fixture)('learning') as learning_ids, contextmanager(authority_fixture)('observer') as observer_ids:
        with contextmanager(mainline_fixture)(learning_ids, roots['learning']), contextmanager(mainline_fixture)(observer_ids, roots['observer']):
            packets = {d: ExecutionPlan(json.loads((inputs_root/(d+'-plan.json')).read_bytes())) for d in roots}
            configs = {d: authorize(ids, roots[d], packets[d]) for d, ids in [('learning', learning_ids), ('observer', observer_ids)]}
            configs['observer']['domain'] = 'observer'
            for d, config in configs.items():
                write(output/(d+'-config.json'), config)
            inputs = {d: Inputs(roots[d]/'inputs', digest(json.loads((inputs_root/'contract.json').read_bytes()))) for d in roots}
            until = (datetime.now(timezone.utc)+timedelta(hours=24)).isoformat()
            stopped = Event()
            def heartbeat():
                while not stopped.is_set():
                    # Static engineering snapshot: no claim of a production poll.
                    for value in inputs.values():
                        publish_dispatch(value, key, approved_until=until, reason=None)
                    stopped.wait(30)
            thread = Thread(target=heartbeat, daemon=True); thread.start()
            summary = {'scope': 'ENGINEERING_FIXTURE_NOT_PRODUCTION_ACTIVATION', 'runs': []}
            try:
                while True:
                    first = engine(configs['learning'])
                    cap = first.capabilities[CAPABILITIES['learn']]
                    def first_two(task, parents):
                        definition = json.loads(task.metric_contract)['historical']
                        return 'FIRST_TWO_WITNESS' if definition['index'] > 901 else cap.ready(task, parents)
                    first.capabilities[CAPABILITIES['learn']] = replace(cap, ready=first_two)
                    first.run()
                    if records(learning_ids[1])['execution_store.commits'] >= 5:
                        break
                    time.sleep(30)
                publish_observations(inputs['observer'], engine(configs['learning']), key, approved_until=until)
                while True:
                    observed = engine(configs['observer']); observed.run()
                    if records(observer_ids[1])['execution_store.commits'] == 2:
                        break
                    time.sleep(30)
                witness = {'learning_run_id': first.run_id, 'observer_run_id': observed.run_id,
                    'producer_records': records(learning_ids[1]), 'observer_records': records(observer_ids[1]),
                    'issues': inputs['learning'].contract['issues'][900:902]}
                write(output/'two-issue-witness.json', witness); print(json.dumps(witness), flush=True)
                while True:
                    current = engine(configs['learning']); current.run()
                    summary['runs'].append(current.run_id)
                    status = json.loads((roots['learning']/'learning/status/execution.json').read_bytes())['payload']
                    write(output/'progress.json', status)
                    if status['capability_progress']['batch_summary_registered']:
                        break
                    if any(r not in {'FORMAL_TASK_RUNNING', 'WAITING_FOR_SOURCE_CHECK'} for r in current.wait_reasons.values()):
                        raise RuntimeError(str(current.wait_reasons))
                    time.sleep(30)
                publish_observations(inputs['observer'], engine(configs['learning']), key, approved_until=until)
                while True:
                    observed = engine(configs['observer']); observed.run()
                    status = json.loads((roots['observer']/'observer/status/execution.json').read_bytes())['payload']
                    if status['capability_progress']['batch_summary_registered']:
                        break
                    if observed.task_errors:
                        raise RuntimeError(str(observed.task_errors))
                    time.sleep(30)
                before = {d: records(ids[1]) for d, ids in [('learning', learning_ids), ('observer', observer_ids)]}
                for d in roots:
                    replay = subprocess.run([sys.executable, str(Path(__file__).with_name('historical_scenario.py')),
                        str(output/(d+'-config.json')), 'replay'], capture_output=True, text=True, timeout=86400)
                    if replay.returncode:
                        raise RuntimeError(replay.stderr)
                    write(output/(d+'-replay.json'), json.loads(replay.stdout))
                after = {d: records(ids[1]) for d, ids in [('learning', learning_ids), ('observer', observer_ids)]}
                assert before == after
                n = len(inputs['learning'].history)-900
                assert after['learning']['execution_store.commits'] == 2*n+2
                assert after['observer']['execution_store.commits'] == n+1
                summary.update(status='ISOLATED_BATCH_AND_REPLAY_PASSED', records=after, observer_run_id=observed.run_id)
                write(output/'acceptance.json', summary); print(json.dumps(summary), flush=True)
            finally:
                stopped.set(); thread.join()
                for d, identities in [('learning', learning_ids), ('observer', observer_ids)]:
                    dump(identities[1], output/(d+'-database-evidence.jsonl.gz'))


def resume_existing(output, key_file):
    """Resume this harness's interrupted fixture; never provision new approval."""
    details = conninfo_to_dict(os.environ['DEHPS_EXECUTION_TEST_ADMIN_DSN'])
    assert details['dbname'] == 'dehps_execution_test_admin'
    configs = {d: json.loads((output/(d+'-config.json')).read_bytes()) for d in ('learning', 'observer')}
    assert all(c['database'].startswith('xa_') and c['database'].endswith('_db') for c in configs.values())
    admins = {d: make_conninfo(**{**details, 'dbname': c['database']}) for d, c in configs.items()}
    roots = {d: Path(c['root']) for d, c in configs.items()}
    inputs = {d: Inputs(root/'inputs', digest(json.loads((root/'inputs/contract.json').read_bytes()))) for d, root in roots.items()}
    key = signing_key(key_file)
    stopped = Event(); stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    candidate = Path(__file__).resolve().parents[3]
    identity = {'scope': 'ENGINEERING_FIXTURE_RESUME_NOT_PRODUCTION',
        'files': {str(p.relative_to(candidate)): sha256(p.read_bytes()).hexdigest()
                  for p in (candidate/'apps/worker-python/dehps').rglob('*.py')}, 'database_functions': {}}
    for d, admin in admins.items():
        with psycopg.connect(admin) as connection:
            identity['database_functions'][d] = {name: sha256(body.encode()).hexdigest() for name, body in connection.execute(
                "SELECT p.oid::regprocedure::text,pg_get_functiondef(p.oid) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname IN ('execution_store','execution_authority')")}
    write(output/('resume-source-'+stamp+'.json'), identity)
    # Same finite approved fixture expiry; never renew its SQL admission.
    with psycopg.connect(admins['learning']) as connection:
        until = connection.execute('SELECT a.expires_at FROM execution_authority.approvals a JOIN execution_authority.executions e ON e.request_id=a.request_id WHERE e.id=%s',
            (configs['learning']['authorization']['execution_id'],)).fetchone()[0].isoformat()
    def heartbeat():
        while not stopped.is_set():
            for i in inputs.values():
                publish_dispatch(i, key, approved_until=until, reason=None)
            stopped.wait(30)
    thread = Thread(target=heartbeat, daemon=True); thread.start()
    summary = {'scope': 'ENGINEERING_FIXTURE_NOT_PRODUCTION_ACTIVATION', 'resumed_without_new_admission': True, 'runs': []}
    try:
        while True:
            current = engine(configs['learning']); current.run(); summary['runs'].append(current.run_id)
            status = json.loads((roots['learning']/'learning/status/execution.json').read_bytes())['payload']
            write(output/'progress.json', status)
            if status['capability_progress']['batch_summary_registered']:
                break
            if current.task_errors or any(r not in {'FORMAL_TASK_RUNNING','WAITING_FOR_SOURCE_CHECK'} for r in current.wait_reasons.values()):
                raise RuntimeError(str(current.wait_reasons)+str(current.task_errors))
            time.sleep(30)
        publish_observations(inputs['observer'], engine(configs['learning']), key, approved_until=until)
        while True:
            observed = engine(configs['observer']); observed.run()
            status = json.loads((roots['observer']/'observer/status/execution.json').read_bytes())['payload']
            if status['capability_progress']['batch_summary_registered']:
                break
            if observed.task_errors:
                raise RuntimeError(str(observed.task_errors))
            time.sleep(30)
        before = {d: records(a) for d, a in admins.items()}
        for d in roots:
            replay = subprocess.run([sys.executable, str(Path(__file__).with_name('historical_scenario.py')),
                str(output/(d+'-config.json')), 'replay'], capture_output=True, text=True, timeout=86400)
            if replay.returncode:
                raise RuntimeError(replay.stderr)
            write(output/(d+'-replay-'+stamp+'.json'), json.loads(replay.stdout))
        after = {d: records(a) for d, a in admins.items()}
        n = len(inputs['learning'].history)-900
        assert before == after and after['learning']['execution_store.commits'] == 2*n+2
        assert after['observer']['execution_store.commits'] == n+1
        summary.update(status='ISOLATED_BATCH_AND_REPLAY_PASSED', records=after, observer_run_id=observed.run_id)
        write(output/('acceptance-'+stamp+'.json'), summary); print(json.dumps(summary), flush=True)
    finally:
        stopped.set(); thread.join()
        for d, admin in admins.items():
            dump(admin, output/(d+'-database-evidence-'+stamp+'.jsonl.gz'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('inputs', 'output', 'key-file'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    if args.resume:
        resume_existing(args.output, args.key_file)
    else:
        run(args.inputs, args.output, args.key_file)
