from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any

from dehps.feature_runtime import RuntimeABICache, RuntimeABICacheCompilation
from dehps.input_contracts.history_window import (
    HistorySnapshotArtifact,
    WindowArtifact,
    WindowMode,
    WindowSpec,
)
from dehps.scoring_kernel.contracts import CandidateStore

if TYPE_CHECKING:
    from dehps.unified_runtime import VerifiedRuntimePackage


RUNTIME_INPUT_COMPILER_PROTOCOL = "runtime_input_compiler.v1"


@dataclass(frozen=True)
class RuntimeInputCompilation:
    history_snapshot: HistorySnapshotArtifact
    window_artifact: WindowArtifact
    abi_cache_compilation: RuntimeABICacheCompilation

    @property
    def verified_runtime(self) -> VerifiedRuntimePackage:
        return self.abi_cache_compilation.verified_runtime

    def as_dict(self) -> dict[str, Any]:
        return {
            "protocol": RUNTIME_INPUT_COMPILER_PROTOCOL,
            "history_snapshot": self.history_snapshot.as_dict(),
            "window_artifact": self.window_artifact.as_dict(),
            "runtime_abi_cache": self.abi_cache_compilation.as_dict(),
        }


class RuntimeInputCompiler:
    """Compile effective domain history into the only package kernels may trust."""

    def __init__(self, *, cache: RuntimeABICache | None = None) -> None:
        self.cache = cache or RuntimeABICache()

    def compile_effective_history(
        self,
        *,
        history: Sequence[object],
        candidate_store: CandidateStore,
        tile_size: int,
        target_draw_date: date | None = None,
        target_issue: str | None = None,
        source: str = "effective_scoring_history",
    ) -> RuntimeInputCompilation:
        history_snapshot = HistorySnapshotArtifact.from_history(history, source=source)
        if history_snapshot.latest_issue is None:
            raise ValueError("Runtime input compilation requires non-empty history")
        window = WindowSpec(
            mode=WindowMode.EXPANDING,
            size=None,
            as_of_issue=history_snapshot.latest_issue,
            include_as_of=True,
            minimum_size=1,
            target_issue=target_issue,
        ).materialize(history_snapshot)
        abi_cache_compilation = self.cache.compile_runtime(
            history_snapshot=history_snapshot,
            window=window,
            candidate_store=candidate_store,
            tile_size=tile_size,
            target_draw_date=target_draw_date,
        )
        return RuntimeInputCompilation(
            history_snapshot=history_snapshot,
            window_artifact=window,
            abi_cache_compilation=abi_cache_compilation,
        )


_DEFAULT_RUNTIME_INPUT_COMPILER = RuntimeInputCompiler()


def default_runtime_input_compiler() -> RuntimeInputCompiler:
    return _DEFAULT_RUNTIME_INPUT_COMPILER


__all__ = (
    "RUNTIME_INPUT_COMPILER_PROTOCOL",
    "RuntimeInputCompilation",
    "RuntimeInputCompiler",
    "default_runtime_input_compiler",
)
