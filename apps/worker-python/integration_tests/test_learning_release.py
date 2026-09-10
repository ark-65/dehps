"""Installed learning release -> real scoped PostgreSQL -> report/API/replay."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4

from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest

from dehps.execution.context import RunContext
from dehps.execution.release import Release, build_release, canonical, launch
from dehps.prediction.learning_inputs import FrozenLearningInputs
from dehps.prediction.learning_plan import build_plan
from test_execution_mainline import mainline, records
from test_execution_status_api import api
from test_learning_execution import learning_packet, synthetic

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope='session')
def learning_release(tmp_path_factory):
    saved = os.environ.get('DEHPS_LEARNING_TEST_RELEASE')
    if saved:
        release = Release.read(Path(saved), os.environ['DEHPS_LEARNING_TEST_RELEASE_SHA256'])
        release.verify()
        return release
    commit = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    output = tmp_path_factory.mktemp('learning-release') / 'release.json'
    release = build_release(
        ROOT, commit, os.environ['DEHPS_OBSERVATION_TEST_BASE_IMAGE'],
        ['/usr/local/bin/python', '-I', '-m', 'dehps.execution.entry'],
        {'schema': 'execution-entry.v1', 'control_plane': 'learning',
         'factory': 'dehps.prediction.learning_execution:build_capabilities', 'lease_seconds': 30,
         'dependency_constraints': 'apps/worker-python/dehps/prediction/frozen_learning/constraints.txt'}, output)
    proof = os.environ.get('DEHPS_LEARNING_TEST_PROOF')
    if proof:
        target = Path(proof); target.mkdir(parents=True, exist_ok=True)
        (target / 'release.json').write_bytes(canonical(release.payload))
    return release


def docker(*args):
    return subprocess.run(['docker', *args], check=True, capture_output=True, text=True).stdout.strip()


def test_installed_learning_release_preserves_complete_evidence_and_readonly_replay(
        learning_release, mainline, authority, learning_packet, tmp_path):
    release = learning_release
    clients, admin_dsn, _, _ = authority
    # These are isolated test principals, not independent human deployment review.
    packet_root, digest, scientific = learning_packet
    if os.environ.get('DEHPS_LEARNING_TEST_INPUTS'):
        packet_root = Path(os.environ['DEHPS_LEARNING_TEST_INPUTS'])
        digest = sha256((packet_root / 'inputs.json').read_bytes()).hexdigest()
        scientific = FrozenLearningInputs(packet_root, digest).artifact('contract')['artifact_digest']
    directory = tmp_path / 'inputs'
    shutil.copytree(packet_root, directory)
    frozen = FrozenLearningInputs(directory, digest)
    runtime = tmp_path / 'runtime'; runtime.mkdir(mode=0o700)
    plan = build_plan(inputs_sha256=digest, scientific_contract_sha256=scientific)
    request_id = clients['engineer'].request(plan.payload, release.digest)
    content = clients['reviewer'].get(request_id)['content_sha256']
    clients['reviewer'].approve(request_id, content, release.digest,
                                datetime.now(timezone.utc) + timedelta(hours=2))
    (directory / 'release.json').write_bytes(canonical(release.payload))
    (directory / 'execution.json').write_bytes(canonical(
        {'schema': 'execution-input.v1', 'request_id': request_id, 'plan': plan.payload}))
    db = clients['operator'].database
    connection = {**conninfo_to_dict(db.dsn), 'host': 'learning-postgres', 'port': '5432'}
    credentials = tmp_path / 'credentials.json'
    credentials.write_bytes(canonical({'dsn': make_conninfo(**connection), 'database': db.database, 'role': db.role}))
    credentials.chmod(0o600)
    network = 'dehps-learning-' + uuid4().hex[:16]
    container = os.environ['DEHPS_EXECUTION_TEST_CONTAINER']
    info = json.loads(docker('inspect', container))[0]
    assert info['Config']['Labels'].get('dehps.execution-test') == 'true'
    docker('network', 'create', '--internal', network)
    try:
        docker('network', 'connect', '--alias', 'learning-postgres', network, container)
        context = RunContext(runtime, 'learning')

        def run(action='run'):
            return launch(release, release.digest, context, inputs=directory, credentials=credentials,
                          network=network, action=action, timeout=1800)

        first = run()
        assert first.returncode == 0, first.stderr.decode()
        result = json.loads(first.stdout)
        assert first.image_id == release.payload['image_id']
        assert result['release_sha256'] == release.digest
        assert set(result['tasks'].values()) == {'completed'} and len(result['artifacts']) == 5
        values = {}
        for key, ref in result['artifacts'].items():
            data = (runtime / ref['path']).read_bytes()
            assert sha256(data).hexdigest() == ref['sha256']
            values[key.rsplit('-', 1)[-1]] = json.loads(data)['scientific']
        assert values['fit']['checkpoint'] == frozen.artifact('checkpoint')
        assert values['evaluate']['issue_count'] == len(frozen.manifest['issues'])
        assert values['evaluate']['all_probabilities_and_losses_recomputed'] is True
        assert values['analysis']['analysis'] == frozen.artifact('analysis')
        assert values['top100']['reference'] == frozen.artifact('top100')
        assert values['top100']['new_prediction'] is False
        report = values['report']
        assert report['scientific_conclusion'] == frozen.artifact('analysis')['body']['conclusion']
        assert report['new_scientific_experiment'] is False
        for name in ('shrink900', 'new_original', 'old_original', 'old_full', 'old_diverse', 'random'):
            assert name in report['text']
        status_path = runtime / 'learning/status/execution.json'
        status = json.loads(status_path.read_bytes())['payload']
        execution_id = clients['operator'].begin(request_id, content, release.digest)
        assert status['execution_id'] == execution_id and status['run_id'] == result['run_id']
        config = dict(root=str(runtime), plan=plan.payload, authorization={'execution_id': execution_id})
        response = api(config, releaseSha256=release.digest)
        assert response['status'] == 'COMPLETED' and response['runId'] == result['run_id']
        before = records(admin_dsn)
        assert before['execution_store.commits'] == before['public.research_os_mainline_artifacts'] == 5
        assert before['public.research_os_mainline_execution_events'] == 10
        previous_status = status_path.read_bytes(), status_path.stat().st_mtime_ns
        replay = run('replay')
        assert replay.returncode == 0, replay.stderr.decode()
        replayed = json.loads(replay.stdout)
        assert replayed['manifest_digest'] == result['manifest_digest']
        assert replayed['artifacts'] == result['artifacts'] and replayed['run_id'] != result['run_id']
        assert records(admin_dsn) == before
        assert (status_path.read_bytes(), status_path.stat().st_mtime_ns) == previous_status
        evidence = dict(release_sha256=release.digest, image_id=first.image_id,
                        inputs_sha256=digest, run_id=result['run_id'], replay_run_id=replayed['run_id'],
                        manifest_digest=result['manifest_digest'], issue_count=values['evaluate']['issue_count'],
                        report_sha256=next(ref['sha256'] for key, ref in result['artifacts'].items() if key.endswith('-report')))
        print(json.dumps(evidence))
        proof = os.environ.get('DEHPS_LEARNING_TEST_PROOF')
        if proof:
            target = Path(proof); target.mkdir(parents=True, exist_ok=True)
            (target / 'validation.json').write_bytes(canonical(evidence))
            (target / 'report.md').write_text(report['text'])
            shutil.copytree(runtime, target / ('runtime-' + result['run_id']))
    finally:
        docker('network', 'disconnect', network, container)
        docker('network', 'rm', network)
