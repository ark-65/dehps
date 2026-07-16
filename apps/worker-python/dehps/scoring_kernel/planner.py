from __future__ import annotations

import os

from dehps.scoring_kernel.contracts import ScoringKernelBackend
from dehps.scoring_kernel.numpy_backend import NumpyReferenceBackend


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
