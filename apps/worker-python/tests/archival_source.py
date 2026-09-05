"""Materialize original Git source bytes for immutable historical-contract tests."""
import json
import subprocess
from pathlib import Path
from dehps.config import ROOT_DIR


def original_source(root: Path, *, contract_path: str, commit: str) -> Path:
    raw = subprocess.check_output(["git", "show", f"{commit}:{contract_path}"], cwd=ROOT_DIR)
    assert raw == (ROOT_DIR / contract_path).read_bytes(), "historical contract was changed"
    payload = json.loads(raw)
    for entry in [*payload["source_entries"], {"path": contract_path}]:
        relative = entry["path"]
        path = root / relative
        assert path.resolve().is_relative_to(root.resolve())
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(subprocess.check_output(["git", "show", f"{commit}:{relative}"], cwd=ROOT_DIR))
    return root
