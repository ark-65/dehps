"""Readonly, digest-bound learning inputs and explicit historical export.

Export is packaging, never a competing training or completion path. It copies
verified artifacts and retains their original source archive; it neither edits
the old source contract nor fetches data or payout information from production.
"""
from hashlib import sha256
import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
import tarfile

from dehps.execution.context import BoundaryError
from .frozen_learning import calculation as core

SCHEMA = 'frozen-learning-inputs.v1'
SOURCE_PATHS = {
    'apps/worker-python/dehps/prediction/learning_v1.py',
    'apps/worker-python/dehps/prediction/learning_v1_runtime.py',
    'apps/worker-python/dehps/prediction/learning_v1_mainline.py',
    'apps/worker-python/scripts/run_prediction_learning_v1.py',
    'docs/experiments/2026-09-05-prediction-learning-v1-contract.md',
}
KINDS = {
    'snapshot': 'PredictionLearningSnapshot', 'contract': 'PredictionLearningContract',
    'training': 'PredictionLearningTraining', 'checkpoint': 'PredictionLearningCheckpoint',
    'analysis': 'PredictionLearningAnalysis', 'top100': 'PredictionLearningExperimentalTop100',
    'semantic_replay': 'PredictionLearningSemanticReplay', 'replay': 'PredictionLearningReplay',
}


def file_digest(path):
    if not path.is_file():
        raise BoundaryError('regular immutable input file required')
    result = sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def verify_source_archive(path, expected_sha256, identities, expected_commit):
    if file_digest(path) != expected_sha256:
        raise BoundaryError('historical source archive changed')
    with tarfile.open(path, 'r:') as archive:
        if archive.pax_headers.get('comment') != expected_commit:
            raise BoundaryError('historical source commit differs from its archive')
        members = archive.getmembers()
        if len({member.name for member in members}) != len(members):
            raise BoundaryError('duplicate historical source archive member')
        python = {member.name for member in members
                  if member.name.startswith('apps/worker-python/dehps/') and member.name.endswith('.py')}
        if set(identities) != python | SOURCE_PATHS:
            raise BoundaryError('historical source identity inventory differs')
        for name, digest in identities.items():
            member = archive.getmember(name)
            if not member.isfile() or sha256(archive.extractfile(member).read()).hexdigest() != digest:
                raise BoundaryError('historical source file differs from frozen contract')


class FrozenLearningInputs:
    def __init__(self, root: Path, expected_sha256: str):
        if not root.is_absolute() or root.resolve() != root:
            raise BoundaryError('canonical explicit learning input root required')
        self.root = root
        data = self._path('inputs.json').read_bytes()
        if sha256(data).hexdigest() != expected_sha256:
            raise BoundaryError('learning input manifest changed')
        self.digest = expected_sha256
        self.manifest = json.loads(data)
        value = self.manifest
        if set(value) != {'schema', 'artifacts', 'issues', 'payouts', 'original_source'} or value['schema'] != SCHEMA:
            raise BoundaryError('closed learning input manifest required')
        if set(value['artifacts']) != set(KINDS):
            raise BoundaryError('complete historical artifact bindings required')
        for ref in [*value['artifacts'].values(), *value['issues'].values(), *value['payouts'].values()]:
            if (set(ref) != {'path', 'sha256', 'artifact_digest'}
                    or not re.fullmatch(r'objects/[0-9a-f]{64}\.json', ref['path'])
                    or not all(re.fullmatch('[0-9a-f]{64}', ref[key]) for key in ('sha256', 'artifact_digest'))
                    or ref['path'] != 'objects/' + ref['sha256'] + '.json'):
                raise BoundaryError('invalid learning artifact reference')
        source = value['original_source']
        if (set(source) != {'path', 'sha256', 'git_commit'} or source['path'] != 'original-source.tar'
                or not re.fullmatch('[0-9a-f]{64}', source['sha256'])
                or not re.fullmatch('[0-9a-f]{40}', source['git_commit'])):
            raise BoundaryError('exact historical source archive identity required')
        snapshot, contract = self.artifact('snapshot'), self.artifact('contract')
        if contract['body']['snapshot_digest'] != snapshot['artifact_digest']:
            raise BoundaryError('contract and snapshot differ')
        verify_source_archive(self._path(source['path']), source['sha256'], contract['body']['source'], source['git_commit'])
        training = self.artifact('training')
        if training['body']['contract_digest'] != contract['artifact_digest']:
            raise BoundaryError('historical training contract differs')
        issues = contract['body']['outer_issues']
        rows = snapshot['body']['rows']
        if (issues != [row['issue'] for row in rows[core.MINIMUM:]]
                or len(issues) != len(set(issues)) or set(value['issues']) != set(issues)
                or len(training['body']['issues']) != len(issues)
                or [ref['artifact_digest'] for ref in training['body']['issues']]
                   != [value['issues'][issue]['artifact_digest'] for issue in issues]):
            raise BoundaryError('historical evaluation coverage or ordering differs')
        if not set(value['payouts']).issubset(set(issues)):
            raise BoundaryError('payout outside the frozen issue set')

    def _path(self, relative):
        path = self.root / relative
        if path.resolve() != path or not path.is_relative_to(self.root) or not path.is_file():
            raise BoundaryError('input path escapes its readonly root')
        return path

    def _read(self, ref):
        data = self._path(ref['path']).read_bytes()
        if sha256(data).hexdigest() != ref['sha256']:
            raise BoundaryError('learning input artifact file changed')
        value = core.verify(json.loads(data))
        if value['artifact_digest'] != ref['artifact_digest']:
            raise BoundaryError('learning scientific artifact identity differs')
        return value

    def artifact(self, name):
        value = self._read(self.manifest['artifacts'][name])
        if value['artifact_type'] != KINDS[name]:
            raise BoundaryError('learning artifact kind differs')
        return value

    def issue(self, issue):
        value = self._read(self.manifest['issues'][issue])
        if value['artifact_type'] != 'PredictionLearningIssue' or value['body']['issue'] != issue:
            raise BoundaryError('learning issue artifact binding differs')
        return value

    def payout(self, issue):
        value = self._read(self.manifest['payouts'][issue])
        if value['artifact_type'] != 'PredictionLearningPayout' or value['body']['issue'] != issue:
            raise BoundaryError('learning payout artifact binding differs')
        return value

    def verify_files(self, *, include_issues=True):
        """Recheck frozen bytes; descendants verify issues via their predecessor."""
        if file_digest(self._path('inputs.json')) != self.digest:
            raise BoundaryError('learning input manifest changed')
        refs = [*self.manifest['artifacts'].values(),
                *self.manifest['payouts'].values(), self.manifest['original_source']]
        if include_issues:
            refs.extend(self.manifest['issues'].values())
        for ref in refs:
            if file_digest(self._path(ref['path'])) != ref['sha256']:
                raise BoundaryError('learning input artifact file changed')

    def validate_execution(self, code_root):
        snapshot, contract = self.artifact('snapshot'), self.artifact('contract')
        body = contract['body']
        required = {'candidate_configurations': list(core.CONFIGS), 'candidate_count': 4,
                    'minimum_training': core.MINIMUM, 'seed': core.SEED, 'primary_model': 'shrink900',
                    'random_repetitions': 32, 'bootstrap_repetitions': 4000,
                    'bootstrap_block_length': 13, 'primary_family_contrasts': 8, 'formal_changes': False,
                    'nested_threads': 1}
        if any(body.get(key) != expected for key, expected in required.items()):
            raise BoundaryError('migrated first-round scientific contract differs')
        versions = body['runtime_versions']
        if versions['numpy'] != core.np.__version__ or versions['python'].split()[0] != platform.python_version():
            raise BoundaryError('frozen learning numerical runtime differs')
        # Preserve the old complete source inventory in its archive, while the
        # active release checks the scientific definitions it actually reuses.
        # Unrelated executor/model modules do not become this model's source ID.
        scientific = ('prediction/learning_v1.py', 'prediction/learning_v1_runtime.py',
                      'input_contracts/candidate_abi.py', 'prediction/v2/generator.py',
                      'research_os/information_theory/metrics/log_loss.py',
                      'research_os/information_theory/walk_forward/contracts.py',
                      'research_os/information_theory/walk_forward/split.py')
        for relative in scientific:
            name = 'apps/worker-python/dehps/' + relative
            if file_digest(code_root / name) != body['source'][name]:
                raise BoundaryError('active learning scientific source differs from historical definition')
        if core.formal.load_source_contract(root_dir=code_root) != snapshot['body']['formal_source']:
            raise BoundaryError('formal scientific source differs from the fixed snapshot')
        core.validate_rows(snapshot['body']['rows'], today=datetime.now(timezone.utc).date().isoformat())
        if not set(body['examples']).issubset(set(body['outer_issues'])):
            raise BoundaryError('frozen replay examples outside the evaluation set')


def export_historical_learning(source_root: Path, round_root: Path, output: Path):
    """Explicit filesystem-only export; original artifact bytes stay untouched."""
    for path in (source_root, round_root, output):
        if not path.is_absolute() or path.resolve() != path:
            raise BoundaryError('canonical export paths required')
    if not round_root.is_relative_to(source_root) or output.is_relative_to(source_root) or source_root.is_relative_to(output):
        raise BoundaryError('historical source and export must be separate')
    def git(*args):
        return subprocess.check_output(['git', '-C', str(source_root), *args])
    if git('status', '--porcelain'):
        raise BoundaryError('historical source checkout must be clean')
    commit = git('rev-parse', 'HEAD').decode().strip()
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    (output / 'objects').mkdir(mode=0o700, exist_ok=True)

    def immutable(path, data):
        if path.resolve() != path:
            raise BoundaryError('export path must not follow symlinks')
        if path.exists():
            if path.stat().st_nlink != 1 or path.stat().st_uid != os.getuid():
                raise BoundaryError('export cannot change a shared or foreign file')
            if path.read_bytes() != data:
                raise BoundaryError('export collision; original evidence was not overwritten')
        else:
            with path.open('xb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        path.chmod(0o600)

    def copy(path):
        if path.resolve() != path or not path.is_relative_to(source_root) or not path.is_file():
            raise BoundaryError('historical artifact reference escapes source root')
        data = path.read_bytes()
        value = core.verify(json.loads(data))
        digest = sha256(data).hexdigest()
        relative = 'objects/' + digest + '.json'
        immutable(output / relative, data)
        return {'path': relative, 'sha256': digest, 'artifact_digest': value['artifact_digest']}, value

    value = {'schema': SCHEMA, 'artifacts': {}, 'issues': {}, 'payouts': {}}
    names = {name: name.replace('_', '-') + '.json' for name in KINDS}
    names['top100'] = 'experimental-top100.json'
    loaded = {}
    for name, filename in names.items():
        ref, artifact = copy(round_root / filename)
        value['artifacts'][name] = ref
        loaded[name] = artifact
    for expected in loaded['training']['body']['issues']:
        ref, artifact = copy(source_root / expected['path'])
        if ref['artifact_digest'] != expected['artifact_digest']:
            raise BoundaryError('historical training index artifact differs')
        issue = artifact['body']['issue']
        if issue in value['issues']:
            raise BoundaryError('duplicate historical issue')
        value['issues'][issue] = ref
    for path in sorted((round_root / 'payouts').glob('*.json')):
        ref, artifact = copy(path)
        issue = artifact['body']['issue']
        if issue in value['payouts']:
            raise BoundaryError('duplicate historical payout')
        value['payouts'][issue] = ref
    archive = git('archive', '--format=tar', commit)
    immutable(output / 'original-source.tar', archive)
    value['original_source'] = {'path': 'original-source.tar', 'sha256': sha256(archive).hexdigest(), 'git_commit': commit}
    data = core.raw(value)
    immutable(output / 'inputs.json', data)
    digest = sha256(data).hexdigest()
    FrozenLearningInputs(output, digest)
    return digest
