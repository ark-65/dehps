"""Exact immutable pre-migration manifests, never the evolving production head."""
import gzip
import json
from pathlib import Path
from dehps.research_os.models import ControlPlaneManifest


def archived_manifest(digest: str) -> ControlPlaneManifest:
    assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)
    path = Path(__file__).parent / "fixtures" / "archival-manifests" / (digest + ".json.gz")
    manifest = ControlPlaneManifest.from_dict(json.loads(gzip.decompress(path.read_bytes())))
    assert manifest.artifact_digest == digest
    return manifest
