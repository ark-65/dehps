"""Deterministic, chunked scoring kernels shared by research and production."""

from dehps.scoring_kernel.contracts import (
    STRICT_CONTRACT_VERSION,
    CandidateStore,
    KernelRequest,
    KernelResult,
    KernelWorkspace,
    PackedWindowState,
    PreparedCandidateStore,
    ScoringKernelBackend,
    WeightMatrix,
)
from dehps.scoring_kernel.packing import (
    candidate_store_from_matrix,
    numbers_mask,
    pack_window_state,
    target_lex_id,
)
from dehps.scoring_kernel.planner import KernelPlanner, resolve_backend_name
from dehps.scoring_kernel.topk_reducer import (
    PartitionMergeReducer,
    SmallKReducer,
    TileSelectionReducer,
    TopKReducer,
    TopKReducerPlanner,
    TopKReductionPool,
    TopKResult,
)

__all__ = (
    "STRICT_CONTRACT_VERSION",
    "CandidateStore",
    "KernelPlanner",
    "KernelRequest",
    "KernelResult",
    "KernelWorkspace",
    "PackedWindowState",
    "PreparedCandidateStore",
    "ScoringKernelBackend",
    "SmallKReducer",
    "TileSelectionReducer",
    "PartitionMergeReducer",
    "TopKReducer",
    "TopKReducerPlanner",
    "TopKReductionPool",
    "TopKResult",
    "WeightMatrix",
    "candidate_store_from_matrix",
    "numbers_mask",
    "pack_window_state",
    "resolve_backend_name",
    "target_lex_id",
)
