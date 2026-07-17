from __future__ import annotations

from dataclasses import dataclass

from dehps.contracts import canonical_digest
from dehps.feature_runtime.abi import FeatureABIPackage, FeatureABIVerifier
from dehps.feature_runtime.compiler import FeatureRuntimeViolation
from dehps.input_contracts.candidate_abi import CandidateABIPackage, CandidateABIVerifier
from dehps.input_contracts.history_window import HistorySnapshotArtifact, WindowArtifact


@dataclass(frozen=True)
class FeatureABIRuntime:
    history_snapshot: HistorySnapshotArtifact
    window_artifact: WindowArtifact
    candidate_package: CandidateABIPackage
    feature_tiles: tuple[FeatureABIPackage, ...]

    @property
    def candidate_count(self) -> int:
        return self.candidate_package.header.row_count

    @property
    def runtime_digest(self) -> str:
        return canonical_digest(
            {
                "runtime_type": "feature_abi_runtime.v1",
                "history_snapshot_digest": self.history_snapshot.history_digest,
                "window_artifact_digest": self.window_artifact.artifact_digest,
                "candidate_package_digest": self.candidate_package.package_digest,
                "feature_tiles": [
                    {
                        "start": tile.header.start,
                        "end": tile.header.end,
                        "package_digest": tile.package_digest,
                    }
                    for tile in self.feature_tiles
                ],
            },
            domain="dehps.feature-abi-runtime.v1",
        )

    def verify(self) -> None:
        FeatureABIRuntimeVerifier().verify(self)


class FeatureABIRuntimeVerifier:
    """Joint Candidate/Feature preflight for the explicit Feature ABI execution path."""

    def verify(self, runtime: FeatureABIRuntime) -> None:
        runtime.history_snapshot.verify()
        runtime.window_artifact.verify()
        if (
            runtime.window_artifact.snapshot_id != runtime.history_snapshot.snapshot_id
            or runtime.window_artifact.envelope.history_snapshot_digest
            != runtime.history_snapshot.history_digest
            or runtime.window_artifact.envelope.input_draw_count
            != runtime.history_snapshot.draw_count
        ):
            self._reject(
                "feature_runtime_history_window_binding_mismatch",
                "Window Artifact does not match the runtime History Snapshot",
            )
        CandidateABIVerifier().verify(runtime.candidate_package)
        if not runtime.feature_tiles:
            self._reject("feature_runtime_missing_tiles", "Feature ABI runtime requires at least one tile")

        expected_start = 0
        window_artifact_digest: str | None = None
        target_context_digest: str | None = None
        candidate_package_digest = runtime.candidate_package.package_digest
        for tile_index, tile in enumerate(runtime.feature_tiles):
            FeatureABIVerifier().verify(tile)
            header = tile.header
            if header.candidate_package_digest != candidate_package_digest:
                self._reject(
                    "feature_runtime_candidate_binding_mismatch",
                    "Feature tile does not reference the runtime Candidate ABI package",
                    tile_index=tile_index,
                )
            if header.window_artifact_digest != runtime.window_artifact.artifact_digest:
                self._reject(
                    "feature_runtime_window_binding_mismatch",
                    "Feature tile does not reference the runtime Window Artifact",
                    tile_index=tile_index,
                )
            if header.start != expected_start:
                self._reject(
                    "feature_runtime_tile_continuity_mismatch",
                    "Feature tiles must be ordered, contiguous, and non-overlapping",
                    tile_index=tile_index,
                    expected_start=expected_start,
                    actual_start=header.start,
                )
            if runtime.candidate_count and header.row_count == 0:
                self._reject(
                    "feature_runtime_empty_interior_tile",
                    "nonempty Candidate runtimes may not contain empty Feature tiles",
                    tile_index=tile_index,
                )
            if header.end > runtime.candidate_count:
                self._reject(
                    "feature_runtime_tile_out_of_range",
                    "Feature tile exceeds Candidate ABI row_count",
                    tile_index=tile_index,
                )
            if window_artifact_digest is None:
                window_artifact_digest = header.window_artifact_digest
                target_context_digest = header.target_context_digest
            elif (
                header.window_artifact_digest != window_artifact_digest
                or header.target_context_digest != target_context_digest
            ):
                self._reject(
                    "feature_runtime_context_mismatch",
                    "all Feature tiles must share one Window and target context",
                    tile_index=tile_index,
                )
            expected_start = header.end

        if expected_start != runtime.candidate_count:
            self._reject(
                "feature_runtime_incomplete_coverage",
                "Feature tiles must cover every Candidate ABI row exactly once",
                covered_rows=expected_start,
                candidate_count=runtime.candidate_count,
            )
        if runtime.candidate_count == 0 and len(runtime.feature_tiles) != 1:
            self._reject(
                "feature_runtime_empty_tile_count_mismatch",
                "an empty Candidate runtime requires exactly one canonical empty Feature tile",
            )

    @staticmethod
    def _reject(code: str, message: str, **context: object) -> None:
        raise FeatureRuntimeViolation(code, message, **context)
