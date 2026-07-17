from __future__ import annotations

import os
from typing import TYPE_CHECKING

from dehps.scoring_kernel.contracts import (
    KernelRequest,
    KernelResult,
    KernelWorkspace,
    ScoringKernelBackend,
    WeightMatrix,
)
from dehps.scoring_kernel.numpy_backend import NumpyReferenceBackend

if TYPE_CHECKING:
    from dehps.feature_runtime.runtime import FeatureABIRuntime
    from dehps.scoring_kernel.feature_abi_backend import (
        FeatureABINumpyReferenceBackend,
        PreparedFeatureABIRuntime,
    )


DEFAULT_BACKEND = "numpy_reference"
BACKEND_ENV = "DEHPS_SCORING_BACKEND"


def resolve_backend_name(explicit: str | None = None) -> str:
    name = str(explicit or os.getenv(BACKEND_ENV) or DEFAULT_BACKEND).strip().lower()
    if name not in {"numpy_reference", "numba_cpu"}:
        raise ValueError(f"unsupported scoring backend: {name}")
    return name


class KernelPlanner:
    """Control-plane backend selection; backends never inspect production state."""

    def __init__(self, backend_name: str | None = None) -> None:
        self.backend_name = resolve_backend_name(backend_name)

    def backend(self) -> ScoringKernelBackend:
        if self.backend_name == "numpy_reference":
            return NumpyReferenceBackend()
        if self.backend_name == "numba_cpu":
            from dehps.scoring_kernel.numba_backend import NumbaCpuBackend

            return NumbaCpuBackend()
        raise AssertionError(f"unreachable backend: {self.backend_name}")

    def feature_abi_backend(self) -> FeatureABINumpyReferenceBackend:
        from dehps.feature_runtime.compiler import FeatureRuntimeViolation
        from dehps.scoring_kernel.feature_abi_backend import FeatureABINumpyReferenceBackend

        if self.backend_name != "numpy_reference":
            raise FeatureRuntimeViolation(
                "feature_abi_backend_not_migrated",
                "the selected fused backend has no verified Feature ABI execution path",
                backend=self.backend_name,
            )
        return FeatureABINumpyReferenceBackend()

    def prepare_feature_abi(
        self,
        runtime: FeatureABIRuntime,
        *,
        code_commit: str,
    ) -> PreparedFeatureABIRuntime:
        return self.feature_abi_backend().prepare(runtime, code_commit=code_commit)

    def score_rank_feature_abi(
        self,
        prepared: PreparedFeatureABIRuntime,
        weights: WeightMatrix,
        request: KernelRequest,
        workspace: KernelWorkspace | None = None,
    ) -> KernelResult:
        from dehps.feature_runtime.compiler import FeatureRuntimeViolation

        backend = self.feature_abi_backend()
        if prepared.backend_name != backend.name:
            raise FeatureRuntimeViolation(
                "feature_abi_prepared_backend_mismatch",
                "prepared Feature ABI runtime belongs to another backend",
                prepared_backend=prepared.backend_name,
                selected_backend=backend.name,
            )
        return backend.score_rank(prepared, weights, request, workspace)
