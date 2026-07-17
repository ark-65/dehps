from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any

import numpy as np

from dehps.forward_runtime.shadow_adapter import (
    ForwardEvaluationCheck,
    compare_official_candidate_artifact,
    forward_operational_evidence,
)
from dehps.models.frequency_ranker import (
    FrequencyRankerConfig,
    HistoryDraw,
    train_frequency_stats,
)
from dehps.optimization.walk_forward import _config_weight_matrix
from dehps.scoring_kernel import (
    KernelRequest,
    WeightMatrix,
    candidate_store_from_matrix,
    compare_kernel_results,
    execute_shadow_pair,
    pack_window_state,
    resolve_backend_name,
)
from dehps.source_version import resolve_git_commit
from dehps.storage.postgres_store import forward_prediction_run_key


FORWARD_SHADOW_CAPTURE_ENV = "DEHPS_FORWARD_SHADOW_CAPTURE"
FORWARD_SHADOW_WORKERS_ENV = "DEHPS_FORWARD_SHADOW_WORKERS"


def forward_shadow_capture_enabled() -> bool:
    value = str(os.getenv(FORWARD_SHADOW_CAPTURE_ENV) or "").strip().lower()
    if value in {"", "0", "false", "no", "off"}:
        return False
    if value in {"1", "true", "yes", "on"}:
        return True
    raise ValueError(f"{FORWARD_SHADOW_CAPTURE_ENV} must be a boolean flag")


def forward_shadow_worker_count() -> int:
    value = int(os.getenv(FORWARD_SHADOW_WORKERS_ENV, "8"))
    if value < 1:
        raise ValueError(f"{FORWARD_SHADOW_WORKERS_ENV} must be positive")
    return value


def capture_forward_snapshot_shadow(
    *,
    metadata: dict[str, Any],
    candidates: Sequence[tuple[int, tuple[int, ...], float]],
    history: list[HistoryDraw],
    config: FrequencyRankerConfig,
    ranked_universe,
    target_draw_date,
    worker_count: int,
) -> dict[str, Any]:
    """Capture immutable pre-draw evidence before a new prediction is persisted."""

    if resolve_backend_name() != "numpy_reference":
        raise ValueError("forward shadow capture requires numpy_reference as official backend")
    source_commit = str(metadata.get("git_commit") or "")
    replay_commit = resolve_git_commit()
    if not source_commit or source_commit != replay_commit:
        raise ValueError("forward shadow capture code commit does not match snapshot metadata")
    store = getattr(ranked_universe, "_kernel_store", None)
    if store is None:
        store = candidate_store_from_matrix(ranked_universe)
        ranked_universe._kernel_store = store
    stats = train_frequency_stats(history, target_draw_date=target_draw_date)
    weights = WeightMatrix(
        np.ascontiguousarray(_config_weight_matrix((config,)), dtype=np.float64)
    )
    request = KernelRequest(
        target_scores=np.zeros(1, dtype=np.float64),
        target_lex_id=0,
        target_mask=np.uint64(0),
        top_k=int(metadata["top_n"]),
        chunk_size=max(1, int(os.getenv("DEHPS_SCORING_CHUNK_SIZE", "262144"))),
        worker_count=worker_count,
        exact_rank=False,
        red5=False,
    )
    official, shadow = execute_shadow_pair(
        candidate_store=store,
        window_state=pack_window_state(stats),
        weights=weights,
        request=request,
    )
    stored_rows = [
        {"rank": rank, "red_numbers": numbers, "score": score}
        for rank, numbers, score in candidates
    ]
    artifact_check = compare_official_candidate_artifact(
        candidate_store=store,
        official_result=official,
        stored_candidates=stored_rows,
    )
    operational = forward_operational_evidence(
        prediction_run={
            **metadata,
            "prediction_run_key": forward_prediction_run_key(metadata),
            "target_issue": metadata["next_issue"],
        },
        artifact_check=artifact_check,
        evaluation_check=ForwardEvaluationCheck(status="pending", mismatch_count=0),
        source_code_commit=source_commit,
        replay_code_commit=replay_commit,
        capture_mode="simultaneous",
        restart_recovery_result="pending",
        watchdog_result="pending",
    )
    return compare_kernel_results(
        target_issue=str(metadata["next_issue"]),
        line_key=str(metadata["line_key"]),
        config_fingerprint=str(metadata["config_hash"]),
        candidate_store_version=store.store_version,
        official=official,
        shadow=shadow,
        operational=operational,
    )
