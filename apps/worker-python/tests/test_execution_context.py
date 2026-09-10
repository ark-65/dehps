from pathlib import Path
import json
import os
import subprocess
import sys

import pytest

from dehps.execution.context import BoundaryError, RunContext
from dehps.execution.database import DatabaseBinding


@pytest.mark.parametrize("relative", ["", ".", "../formal.json", "a/../../formal", "/formal", "a//b", "a/./b"])
def test_projection_escape_is_rejected(tmp_path, relative):
    with pytest.raises(BoundaryError):
        RunContext(tmp_path, "observer").write_projection("state", relative, {})


@pytest.mark.parametrize("identity", ["", "../formal", "formal/../observer", "UPPER", "a" * 97])
def test_control_identity_is_not_a_path(tmp_path, identity):
    with pytest.raises(BoundaryError):
        RunContext(tmp_path, identity)


def test_every_lifecycle_projection_preserves_formal_sentinel(tmp_path):
    formal = tmp_path / "formal.json"
    formal.write_text("original")
    before = (formal.read_bytes(), formal.stat().st_mtime_ns)
    observer, learning = (RunContext(tmp_path, name) for name in ("observer", "learning"))
    for state in ("starting", "waiting", "running", "completed", "failed"):
        for context in (observer, learning):
            for area in ("state", "status", "logs"):
                context.write_projection(area, "latest.json", {"state": state})
                assert context.read_projection(area, "latest.json") == {"state": state}
    assert (formal.read_bytes(), formal.stat().st_mtime_ns) == before
    assert not list(tmp_path.rglob(".pending-*"))


def test_symlink_traversal_and_final_symlink_do_not_write_target(tmp_path):
    context = RunContext(tmp_path, "observer")
    target = tmp_path / "formal.json"
    target.write_text("formal")
    before = target.stat().st_mtime_ns
    context.write_projection("status", "latest.json", {})
    status = tmp_path / "observer/status"
    (status / "escape").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(OSError):
        context.write_projection("status", "escape/formal.json", {})
    (status / "latest.json").unlink()
    (status / "latest.json").symlink_to(target)
    with pytest.raises(OSError):
        context.read_projection("status", "latest.json")
    context.write_projection("status", "latest.json", {"ok": True})
    assert not (status / "latest.json").is_symlink()
    assert target.read_text() == "formal" and target.stat().st_mtime_ns == before


def test_root_symlink_and_shared_writable_root_are_rejected(tmp_path):
    link = tmp_path / "link"
    link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(OSError):
        RunContext(link, "observer")
    tmp_path.chmod(0o777)
    with pytest.raises(BoundaryError, match="owned"):
        RunContext(tmp_path, "observer")


def test_projection_cannot_mutate_artifacts_or_outbox(tmp_path):
    for area in ("artifacts", "outbox", "locks", "unknown"):
        with pytest.raises(BoundaryError):
            RunContext(tmp_path, "observer").write_projection(area, "value.json", {})


def test_consumer_rejects_cross_domain_projection(tmp_path):
    context = RunContext(tmp_path, "observer")
    context.write_projection("status", "latest.json", {})
    path = tmp_path / "observer/status/latest.json"
    path.write_text(json.dumps({"control_plane": "formal", "payload": {}}))
    with pytest.raises(BoundaryError, match="identity"):
        context.read_projection("status", "latest.json")


def test_nonfinite_projection_fails_before_publication(tmp_path):
    context = RunContext(tmp_path, "observer")
    context.write_projection("status", "latest.json", {"good": True})
    with pytest.raises(ValueError):
        context.write_projection("status", "latest.json", {"bad": float("nan")})
    assert context.read_projection("status", "latest.json") == {"good": True}


@pytest.mark.parametrize("dsn", ["", "dbname=dehps", "service=production",
    "host=localhost port=5432 dbname=experiment user=runner password=test options=-crole=admin"])
def test_database_admission_requires_explicit_connection_without_service_defaults(dsn):
    with pytest.raises(BoundaryError):
        DatabaseBinding(dsn, "experiment", "runner").connect()


def test_execution_boundaries_import_without_production_settings():
    script = """
import sys
from dehps.execution.context import RunContext
from dehps.execution.database import DatabaseBinding
from dehps.execution.authority import AuthorityClient
from dehps.execution.store import ExecutionStore
assert 'dehps.config' not in sys.modules
assert 'dehps.research_os.supervisor' not in sys.modules
assert not any(m.startswith('dehps.notifications') for m in sys.modules)
"""
    subprocess.run([sys.executable, "-c", script], check=True,
                   env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])})
