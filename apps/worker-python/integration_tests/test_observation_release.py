"""Complete installed observation entry, real release approval, DB and HTTP."""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
from uuid import uuid4

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest

from dehps.execution.context import RunContext
from dehps.execution.release import Release, build_release, canonical, launch
from dehps.prediction.observation_plan import build_plan
from test_execution_mainline import mainline, records
from test_execution_status_api import api
from tests.test_prediction_error_learning import inputs, outcome

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope='session')
def observation_release(tmp_path_factory):
    output = os.environ.get('DEHPS_OBSERVATION_TEST_RELEASE')
    if output:
        release = Release.read(Path(output), os.environ['DEHPS_OBSERVATION_TEST_RELEASE_SHA256'])
        release.verify()
        return release
    commit = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    output = tmp_path_factory.mktemp('observation-release') / 'release.json'
    return build_release(
        ROOT, commit, os.environ['DEHPS_OBSERVATION_TEST_BASE_IMAGE'],
        ['/usr/local/bin/python', '-I', '-m', 'dehps.execution.entry'],
        {'schema': 'execution-entry.v1', 'control_plane': 'observer',
         'factory': 'dehps.prediction.observation_execution:build_capabilities', 'lease_seconds': 30}, output,
    )


def docker(*args):
    return subprocess.run(['docker', *args], check=True, capture_output=True, text=True).stdout.strip()


def test_fixed_image_observation_admission_full_report_http_and_readonly_replay(
        observation_release, mainline, authority, inputs, tmp_path):
    release = observation_release
    clients, admin_dsn, roles, _ = authority
    # Dedicated test principals, never a claim of real human deployment review.
    with psycopg.connect(admin_dsn) as admin:
        admin.execute("UPDATE execution_authority.identities SET control_plane='observer' WHERE control_plane='learning'")
    runtime = tmp_path / 'runtime'; runtime.mkdir(mode=0o700)
    directory = tmp_path / 'inputs'; directory.mkdir(mode=0o700)
    frozen = canonical(asdict(inputs))
    bundle, payout = outcome(inputs)
    opened = canonical(dict(settlement=bundle.settlement, settlement_replay=bundle.settlement_replay,
                            payout=payout, available_at='2026-09-03T22:00:00+08:00'))
    plan = build_plan(issue=inputs.predraw.issue, frozen_sha256=sha256(frozen).hexdigest(),
                      scientific_contract_sha256=inputs.source['artifact_digest'],
                      opened_sha256=sha256(opened).hexdigest())
    request_id = clients['engineer'].request(plan.payload, release.digest)
    content = clients['reviewer'].get(request_id)['content_sha256']
    clients['reviewer'].approve(request_id, content, release.digest, datetime.now(timezone.utc) + timedelta(hours=1))
    (directory / 'frozen.json').write_bytes(frozen)
    (directory / 'opened.json').write_bytes(opened)
    (directory / 'release.json').write_bytes(canonical(release.payload))
    packet = canonical({'schema': 'execution-input.v1', 'request_id': request_id, 'plan': plan.payload})
    (directory / 'execution.json').write_bytes(packet)
    db = clients['operator'].database
    connection = {**conninfo_to_dict(db.dsn), 'host': 'observation-postgres', 'port': '5432'}
    credentials = tmp_path / 'credentials.json'
    credentials.write_bytes(canonical({'dsn': make_conninfo(**connection), 'database': db.database, 'role': db.role}))
    credentials.chmod(0o600)
    network = 'dehps-observation-' + uuid4().hex[:16]
    container = os.environ['DEHPS_EXECUTION_TEST_CONTAINER']
    info = json.loads(docker('inspect', container))[0]
    assert info['Config']['Labels'].get('dehps.execution-test') == 'true'
    docker('network', 'create', '--internal', network)
    try:
        docker('network', 'connect', '--alias', 'observation-postgres', network, container)
        context = RunContext(runtime, 'observer')

        def run(action='run'):
            return launch(release, release.digest, context, inputs=directory, credentials=credentials,
                          network=network, action=action, timeout=120)

        first = run()
        assert first.returncode == 0, first.stderr.decode()
        assert first.image_id == release.payload['image_id']
        result = json.loads(first.stdout)
        assert set(result['tasks'].values()) == {'completed'}
        assert result['release_sha256'] == release.digest
        assert len(result['artifacts']) == 2
        report_ref = next(value for key, value in result['artifacts'].items() if key.endswith('-report'))
        report_bytes = (runtime / report_ref['path']).read_bytes()
        assert sha256(report_bytes).hexdigest() == report_ref['sha256']
        report = json.loads(report_bytes)['scientific']
        assert len(report['diagnosis']['all_100_tickets']) == 100
        assert len(report['sample']['body']['red_labels_1_to_33']) == 33
        assert len(report['sample']['body']['blue_labels_1_to_16']) == 16
        assert report['new_prediction'] is False and report['text'] and report['html']
        status_path = runtime / 'observer/status/execution.json'
        status = json.loads(status_path.read_bytes())['payload']
        execution_id = clients['operator'].begin(request_id, content, release.digest)
        assert status['execution_id'] == execution_id and status['run_id'] == result['run_id']
        api_config = dict(root=str(runtime), plan=plan.payload, authorization={'execution_id': execution_id})
        response = api(api_config, controlPlane='observer', releaseSha256=release.digest)
        assert response['status'] == 'COMPLETED' and response['runId'] == result['run_id']
        before = records(admin_dsn)
        assert before['execution_store.commits'] == before['public.research_os_mainline_artifacts'] == 2
        timestamp = status_path.stat().st_mtime_ns
        replay = run('replay')
        assert replay.returncode == 0, replay.stderr.decode()
        replayed = json.loads(replay.stdout)
        assert replayed['manifest_digest'] == result['manifest_digest']
        assert replayed['artifacts'] == result['artifacts'] and replayed['run_id'] != result['run_id']
        assert records(admin_dsn) == before and status_path.stat().st_mtime_ns == timestamp
        clients['reviewer'].revoke(request_id)
        failed = run()
        assert failed.returncode != 0
        assert json.loads(status_path.read_bytes())['payload']['phase'] == 'failed'
        assert api(api_config, controlPlane='observer', releaseSha256=release.digest)['status'] == 'UNKNOWN'
        assert records(admin_dsn) == before
        # Revocation prevents new execution but does not erase valid history.
        replay = run('replay')
        assert replay.returncode == 0, replay.stderr.decode()
        assert json.loads(replay.stdout)['artifacts'] == result['artifacts']
        assert records(admin_dsn) == before
        print(json.dumps({'release_sha256': release.digest, 'image_id': first.image_id,
                          'run_id': result['run_id'], 'replay_run_id': replayed['run_id'],
                          'manifest_digest': result['manifest_digest'], 'report_sha256': report_ref['sha256']}))
    finally:
        docker('network', 'disconnect', network, container)
        docker('network', 'rm', network)
