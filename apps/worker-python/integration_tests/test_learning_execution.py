"""Fixed-input training/evaluation/checkpoint/report with real PostgreSQL."""
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tarfile
import time

import pytest

from dehps.execution.context import BoundaryError
from dehps.prediction.frozen_learning import calculation as core, analysis
from dehps.prediction.learning_inputs import FrozenLearningInputs, SOURCE_PATHS
from dehps.prediction.learning_plan import build_plan
from learning_scenario import coordinator
from test_execution_mainline import mainline, records
from tests.test_prediction_learning_v1 import synthetic

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope='module')
def learning_packet(synthetic, tmp_path_factory):
    """Engineering fixture: real complete calculations, no production snapshot."""
    directory = tmp_path_factory.mktemp('frozen-learning-inputs')
    (directory / 'objects').mkdir()
    commit = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    source = subprocess.check_output(['git', '-C', str(ROOT), 'archive', '--format=tar', commit])
    with tarfile.open(fileobj=BytesIO(source), mode='r:') as archive:
        paths = SOURCE_PATHS | {member.name for member in archive.getmembers()
                              if member.name.startswith('apps/worker-python/dehps/') and member.name.endswith('.py')}
        identities = {name: sha256(archive.extractfile(name).read()).hexdigest() for name in paths}
    snapshot = core.seal('PredictionLearningSnapshot', synthetic)
    rows = synthetic['rows']; issues = [row['issue'] for row in rows[core.MINIMUM:]]
    contract = core.seal('PredictionLearningContract', {
        'snapshot_digest': snapshot['artifact_digest'], 'source': identities,
        'candidate_configurations': list(core.CONFIGS), 'candidate_count': 4,
        'minimum_training': core.MINIMUM, 'seed': core.SEED, 'primary_model': 'shrink900',
        'random_repetitions': 32, 'bootstrap_repetitions': 4000, 'bootstrap_block_length': 13,
        'primary_family_contrasts': 8, 'formal_changes': False, 'outer_issues': issues, 'nested_threads': 1,
        'examples': issues, 'runtime_versions': {'numpy': core.np.__version__, 'python': platform.python_version() + ' engineering fixture'},
    })
    values = {issue: core.evaluate_issue(index, snapshot=synthetic, contract=contract)
              for index, issue in enumerate(issues, core.MINIMUM)}
    checkpoint = analysis.refit_checkpoint(snapshot, contract)
    training = core.seal('PredictionLearningTraining', {'contract_digest': contract['artifact_digest'],
        'issues': [{'path': 'old-unmounted-directory/' + issue + '.json', 'artifact_digest': value['artifact_digest']}
                   for issue, value in values.items()], 'checkpoint_digest': checkpoint['artifact_digest']})
    payouts = {}
    for index, issue in enumerate(issues, core.MINIMUM):
        row = rows[index]
        record = {'issue': issue, 'red': row['red'], 'blue': row['blue'],
                  'winnerDetails': [{'awardEtc': tier, 'baseBetWinner': {'awardMoney': amount}}
                                    for tier, amount in enumerate((10000000, 200000, 3000, 200, 10, 5), 1)]}
        payouts[issue] = core.seal('PredictionLearningPayout', {'issue': issue, 'record': record})
    by_digest = {value['artifact_digest']: value for value in values.values()}
    result = analysis.analyze(contract, training, lambda digest: by_digest[digest], payouts)
    space = core.combinations(); q = core.np.asarray(checkpoint['body']['probabilities'])
    scores = core.scores(q, space); ids = core.ordered(core.np.arange(len(space)), scores, 10000)
    chosen = core.diverse(ids, scores[ids], space[ids]); target = str(int(rows[-1]['issue'])+1)
    blues = core.formal._blue_numbers(preregistration_digest=synthetic['formal_preregistration']['artifact_digest'], target_issue=target)
    top100 = core.seal('PredictionLearningExperimentalTop100', {'checkpoint_digest': checkpoint['artifact_digest'],
        'target_issue': target, 'engineering_fixture': True,
        'tickets': [{'rank': rank+1, 'red': (space[index]+1).tolist(), 'blue': blues[rank]} for rank, index in enumerate(chosen)]})
    artifacts = dict(snapshot=snapshot, contract=contract, training=training, checkpoint=checkpoint,
                     analysis=result, top100=top100,
                     semantic_replay=core.seal('PredictionLearningSemanticReplay', {'engineering_fixture': True}),
                     replay=core.seal('PredictionLearningReplay', {'engineering_fixture': True}))
    def save(value):
        data = core.raw(value) + b'\n'; digest = sha256(data).hexdigest(); name = 'objects/' + digest + '.json'
        (directory / name).write_bytes(data)
        return {'path': name, 'sha256': digest, 'artifact_digest': value['artifact_digest']}
    manifest = {'schema': 'frozen-learning-inputs.v1', 'artifacts': {name: save(value) for name, value in artifacts.items()},
                'issues': {issue: save(value) for issue, value in values.items()},
                'payouts': {issue: save(value) for issue, value in payouts.items()},
                'original_source': {'path': 'original-source.tar', 'sha256': sha256(source).hexdigest(), 'git_commit': commit}}
    (directory / 'original-source.tar').write_bytes(source)
    data = core.raw(manifest); (directory / 'inputs.json').write_bytes(data)
    digest = sha256(data).hexdigest()
    frozen = FrozenLearningInputs(directory, digest); frozen.validate_execution(ROOT)
    return directory, digest, contract['artifact_digest']


def child(config, mode):
    path = Path(config['root']) / 'learning-config.json'
    path.write_bytes(core.raw(config)); path.chmod(0o600)
    return subprocess.run([sys.executable, str(Path(__file__).with_name('learning_scenario.py')), str(path), mode],
                          env={'PATH': os.defpath, 'PYTHONPATH': str(ROOT / 'apps/worker-python'),
                               'PYTHONDONTWRITEBYTECODE': '1', 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'},
                          capture_output=True, text=True, timeout=120)


def test_learning_resumes_without_new_training_commit_and_consumes_report(mainline, learning_packet):
    _, admin_dsn, authorize = mainline
    directory, digest, scientific = learning_packet
    plan = build_plan(inputs_sha256=digest, scientific_contract_sha256=scientific)
    config = {**authorize(plan), 'input_root': str(directory)}
    killed = child(config, 'before_evaluate')
    assert killed.returncode == -9, killed.stderr
    assert records(admin_dsn)['execution_store.commits'] == 1
    time.sleep(1.05)
    resumed = child(config, 'normal'); assert resumed.returncode == 0, resumed.stderr
    before = records(admin_dsn)
    assert before['execution_store.commits'] == before['public.research_os_mainline_artifacts'] == 5
    assert before['public.research_os_mainline_execution_events'] == 10
    replay = child(config, 'replay'); assert replay.returncode == 0, replay.stderr
    first, last = json.loads(resumed.stdout), json.loads(replay.stdout)
    assert first['run_id'] != last['run_id'] and first['manifest'] == last['manifest']
    assert not first['projection_errors'] and not last['projection_errors']
    assert records(admin_dsn) == before
    fit = plan.validate().tasks[0]
    assert (Path(config['root']) / (fit.task_key + '.calls')).read_bytes() == b'compute\n'
    engine = coordinator(config); engine.replay()
    report = engine.store.result(engine.bindings[engine.initial.tasks[-1].artifact_digest])
    text = json.loads(report.data)['scientific']['text']
    assert all(name in text for name in (*core.ARMS, *(config['name'] for config in core.CONFIGS)))
    assert 'not used for chronological historical predictions' in text
    print(json.dumps({'run_id': first['run_id'], 'replay_run_id': last['run_id'], 'report_sha256': report.artifact.sha256}))


def test_cached_learning_verification_still_rejects_changed_input_bytes(mainline, learning_packet):
    _, admin_dsn, authorize = mainline
    directory, digest, scientific = learning_packet
    plan = build_plan(inputs_sha256=digest, scientific_contract_sha256=scientific)
    config = {**authorize(plan), 'input_root': str(directory)}
    engine = coordinator(config); engine.run()
    frozen = FrozenLearningInputs(directory, digest)
    ref = frozen.manifest['artifacts']['analysis']; path = directory / ref['path']
    original = path.read_bytes(); before = records(admin_dsn)
    try:
        path.write_bytes(original + b' ')
        with pytest.raises(BoundaryError, match='input artifact file changed'):
            engine.replay()
        assert records(admin_dsn) == before
    finally:
        path.write_bytes(original)
    engine.replay()
