"""Reject incomplete or credential-bearing retained-release mount targets."""
import importlib.util
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[3] / 'deploy/execution/legacy_p3_namespace.py'
spec = importlib.util.spec_from_file_location('legacy_p3_namespace', MODULE)
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)


@pytest.mark.parametrize('target_kind', ['missing', 'nonempty', 'symlink'])
def test_unsafe_env_mount_target_rejected_before_launch(tmp_path, target_kind):
    bundle = tmp_path / 'bundle'
    for version, commit in zip(['ac0ef78', 'cd069c1'], legacy.SOURCE_COMMITS.values()):
        metadata = bundle / 'legacy' / version / '.git'
        metadata.mkdir(parents=True)
        (metadata / 'HEAD').write_text(commit + '\n')
    (bundle / 'legacy/environment').mkdir()
    target = bundle / 'legacy/ac0ef78/.env'
    if target_kind == 'nonempty':
        target.write_text('SYNTHETIC_TEST_SECRET=must-not-enter-release\n')
    elif target_kind == 'symlink':
        empty = tmp_path / 'empty'
        empty.touch()
        target.symlink_to(empty)
    with pytest.raises(ValueError, match='empty regular.*mount target'):
        legacy.command(bundle, 'supervisor', True)
