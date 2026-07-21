from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from dehps.research_os.models import (
    ControlPlaneManifest,
    ResolutionSnapshot,
    jsonable,
    stable_hash,
)
from dehps.research_os.ready_queue import ReadyQueue
from dehps.research_os.resolver import TaskDependencyResolver


class ResearchOSControlPlane:
    """Pure P1 control plane: resolve dependencies and materialize a Ready Queue."""

    def __init__(
        self,
        *,
        resolver: TaskDependencyResolver | None = None,
        ready_queue: ReadyQueue | None = None,
    ) -> None:
        self.resolver = resolver or TaskDependencyResolver()
        self.ready_queue = ready_queue or ReadyQueue()

    def resolve(self, manifest: ControlPlaneManifest) -> ResolutionSnapshot:
        resolutions = self.resolver.resolve(manifest)
        queue = self.ready_queue.build(manifest, resolutions)
        counts = Counter(item.status.value for item in resolutions)
        state_counts = tuple(sorted(counts.items()))
        body = {
            "schema_version": manifest.schema_version,
            "artifact_type": "resolution_snapshot",
            "manifest_digest": manifest.artifact_digest,
            "resolutions": resolutions,
            "ready_queue": queue,
            "state_counts": state_counts,
        }
        return ResolutionSnapshot(
            manifest_digest=manifest.artifact_digest,
            resolutions=resolutions,
            ready_queue=queue,
            state_counts=state_counts,
            snapshot_digest=stable_hash(body),
            schema_version=manifest.schema_version,
        )

    def resolve_payload(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        manifest = ControlPlaneManifest.from_dict(payload)
        snapshot = self.resolve(manifest)
        return {
            "artifact_type": "resolution_snapshot",
            "schema_version": snapshot.schema_version,
            "manifest_digest": snapshot.manifest_digest,
            "snapshot_digest": snapshot.snapshot_digest,
            "state_counts": dict(snapshot.state_counts),
            "ready_queue": jsonable(snapshot.ready_queue),
            "resolutions": jsonable(snapshot.resolutions),
            "dispatch_performed": False,
            "production_impact": "none",
        }
