"""Actual frozen image and authenticated revocation; no production admission."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import time
from uuid import uuid4

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest

from dehps.execution.context import RunContext
from dehps.execution.release import Release, build_release, canonical, launch
from dehps.prediction.forward_learning.contract import digest
from dehps.prediction.forward_learning.plan import build_plan
from test_execution_mainline import mainline, records
from test_forward_learning_mainline import helper
from test_learning_release import docker

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope='session')
def forward_release(tmp_path_factory):
    saved = os.environ.get('DEHPS_FORWARD_TEST_RELEASE')
    if saved:
        release = Release.read(Path(saved), os.environ['DEHPS_FORWARD_TEST_RELEASE_SHA256'])
        release.verify()
        return release
    commit = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    return build_release(ROOT, commit, os.environ['DEHPS_OBSERVATION_TEST_BASE_IMAGE'],
        ['/usr/local/bin/python', '-I', '-m', 'dehps.execution.entry'],
        {'schema': 'execution-entry.v1', 'control_plane': 'learning',
         'factory': 'dehps.prediction.forward_learning.capabilities:build_capabilities', 'lease_seconds': 300,
         'dependency_constraints': 'apps/worker-python/dehps/prediction/frozen_learning/constraints.txt'},
        tmp_path_factory.mktemp('forward-release')/'release.json')


def test_installed_image_stops_on_mid_run_revocation_and_replays_without_writes(forward_release, mainline, authority, tmp_path):
    release = forward_release
    clients, admin_dsn, _, _ = authority
    inputs = tmp_path/'image-inputs'
    contract, rows, key = helper.fixture(inputs)
    now = datetime.now(timezone.utc)
    # Past synthetic labels exercise safe gaps, never fabricated past forecasts.
    for row in rows:
        for name in ('draw_at', 'available_at'):
            row[name] = (datetime.fromisoformat(row[name])-timedelta(days=400)).isoformat()
    contract['created_at'] = (now-timedelta(days=365)).isoformat()
    for target in contract['targets']:
        for name in ('deadline', 'draw_at'):
            target[name] = (datetime.fromisoformat(target[name])-timedelta(days=200)).isoformat()
    contract['initial_sha256'] = digest(rows); contract['calendar_sha256'] = digest(contract['targets'])
    (inputs/'initial.json').write_bytes(canonical(rows)); (inputs/'contract.json').write_bytes(canonical(contract))
    for index in range(60): helper.publish(inputs, contract, key, index)
    plan = build_plan(contract)
    # Actual separate test logins, not a claim of human scientific review.
    request = clients['engineer'].request(plan.payload, release.digest)
    content = clients['reviewer'].get(request)['content_sha256']
    clients['reviewer'].approve(request, content, release.digest, now+timedelta(hours=1))
    (inputs/'release.json').write_bytes(canonical(release.payload))
    (inputs/'execution.json').write_bytes(canonical({'schema': 'execution-input.v1', 'request_id': request, 'plan': plan.payload}))
    binding = clients['operator'].database
    credentials = tmp_path/'image-credentials.json'
    credentials.write_bytes(canonical({'dsn': make_conninfo(**{**conninfo_to_dict(binding.dsn),
        'host': 'forward-postgres', 'port': '5432'}), 'database': binding.database, 'role': binding.role}))
    credentials.chmod(0o600)
    runtime = tmp_path/'image-runtime'; runtime.mkdir(mode=0o700)
    context = RunContext(runtime, 'learning')
    container = os.environ['DEHPS_EXECUTION_TEST_CONTAINER']
    assert json.loads(docker('inspect', container))[0]['Config']['Labels'].get('dehps.execution-test') == 'true'
    network = 'dehps-forward-' + uuid4().hex[:16]
    docker('network', 'create', '--internal', network)
    try:
        docker('network', 'connect', '--alias', 'forward-postgres', network, container)
        def run(action='run'):
            return launch(release, release.digest, context, inputs=inputs, credentials=credentials,
                          network=network, action=action, timeout=300)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(run)
            deadline = time.monotonic()+90
            with psycopg.connect(admin_dsn, autocommit=True) as admin:
                while time.monotonic() < deadline:
                    if admin.execute('SELECT count(*) FROM execution_store.commits').fetchone()[0] > 0:
                        break
                    assert not future.done(), future.result().stderr.decode()
                    time.sleep(0.1)
                else:
                    pytest.fail('actual image did not produce its first commit')
            clients['reviewer'].revoke(request)
            stopped = future.result(timeout=60)
        assert stopped.returncode == 0, stopped.stderr.decode()
        result = json.loads(stopped.stdout)
        assert result['reason'] == 'AUTHORIZATION_REQUIRED' and result['phase'] == 'waiting'
        before = records(admin_dsn)
        assert 1 <= before['execution_store.commits'] < 181
        denied = run(); assert denied.returncode == 0, denied.stderr.decode()
        assert json.loads(denied.stdout)['reason'] == 'AUTHORIZATION_REQUIRED'
        assert records(admin_dsn) == before
        status = runtime/'learning/status/execution.json'; previous = status.read_bytes(), status.stat().st_mtime_ns
        replay = run('replay-prefix'); assert replay.returncode == 0, replay.stderr.decode()
        replayed = json.loads(replay.stdout)
        assert len(replayed['artifacts']) == before['execution_store.commits']
        assert records(admin_dsn) == before and (status.read_bytes(), status.stat().st_mtime_ns) == previous
        evidence = {'image_id': release.payload['image_id'], 'release_sha256': release.digest,
            'source_commit': release.payload['git_commit'], 'run_id': result['run_id'],
            'replay_run_id': replayed['run_id'], 'records': before, 'status': 'ISOLATED_IMAGE_VERIFIED',
            'real_draw_acceptance': False, 'independent_human_review': False}
        print(json.dumps(evidence))
        if output := os.environ.get('DEHPS_FORWARD_RELEASE_PROOF'):
            Path(output).write_bytes(canonical(evidence))
    finally:
        docker('network', 'disconnect', network, container)
        docker('network', 'rm', network)
