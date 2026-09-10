"""Release schema rejection without a Docker daemon or production configuration."""
from copy import deepcopy
from io import BytesIO
import tarfile
import pytest

from dehps.execution.context import BoundaryError
from dehps.execution.release import Release, dependency_constraint


def packet():
    return {'schema': 'execution-release.v1', 'image_id': 'sha256:'+'1'*64,
            'base_image_id': 'sha256:'+'2'*64, 'git_commit': '3'*40,
            'source_archive_sha256': '4'*64, 'config_sha256': '5'*64,
            'entrypoint': ['/usr/local/bin/python', '-I', '-m', 'example'],
            'inventory': {'python': '3.14', 'packages': []}, 'platform': 'linux/amd64'}


@pytest.mark.parametrize('key,value', [('schema', 'unknown'), ('image_id', 'python:latest'),
    ('git_commit', 'main'), ('config_sha256', ''), ('entrypoint', ['python']),
    ('entrypoint', []), ('platform', 'unknown'), ('inventory', {})])
def test_release_rejects_incomplete_or_mutable_bindings(key, value):
    payload = packet()
    payload[key] = value
    with pytest.raises(BoundaryError):
        Release(payload).validate()


def test_every_release_component_changes_its_identity():
    original = Release(packet())
    for key in ['source_archive_sha256', 'config_sha256']:
        changed = deepcopy(original.payload)
        changed[key] = 'f'*64
        assert Release(changed).digest != original.digest
    changed = deepcopy(original.payload)
    changed['inventory']['packages'] = [['dependency', '1.0']]
    assert Release(changed).digest != original.digest
    changed['extra'] = 'ignored field'
    with pytest.raises(BoundaryError):
        Release(changed).validate()


def test_dependency_constraint_must_be_a_regular_file_in_the_frozen_archive():
    archive = BytesIO()
    with tarfile.open(fileobj=archive, mode='w') as output:
        data = b'numpy==2.4.6\n'
        info = tarfile.TarInfo('model/constraints.txt'); info.size = len(data)
        output.addfile(info, BytesIO(data))
        link = tarfile.TarInfo('model/link.txt'); link.type = tarfile.SYMTYPE
        link.linkname = 'constraints.txt'; output.addfile(link)
    data = archive.getvalue()
    assert dependency_constraint({}, data) == ''
    assert dependency_constraint({'dependency_constraints': 'model/constraints.txt'}, data).endswith('/model/constraints.txt')
    for name in ('../constraints.txt', '/etc/passwd', 'model/../constraints.txt', 'model//constraints.txt',
                 'model/constraints.txt;echo bad', 'model/missing.txt', 'model/link.txt'):
        with pytest.raises(BoundaryError):
            dependency_constraint({'dependency_constraints': name}, data)
