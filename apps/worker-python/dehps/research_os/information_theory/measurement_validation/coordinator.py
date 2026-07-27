from __future__ import annotations

import json
import time
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from dehps.artifacts import atomic_write_text
from dehps.research_os.information_theory.synthetic.contracts import (
    SyntheticRunManifest,
)

from .contracts import MeasurementValidationContractError, MeasurementValidationManifest
from .executor import (
    ReplicateEvaluator,
    _load_object,
    _replicate_path,
    _validate_replicate_result,
    persist_immutable,
)
from .schedule import AnalysisReplicate, execution_plan_summary, iter_replicates


_WORKER_EVALUATOR: ReplicateEvaluator | None = None


def _initialize_worker(evaluator: ReplicateEvaluator) -> None:
    global _WORKER_EVALUATOR
    _WORKER_EVALUATOR = evaluator


def _evaluate_replicate(replicate: AnalysisReplicate) -> Mapping[str, Any]:
    if _WORKER_EVALUATOR is None:
        raise RuntimeError("measurement-validation worker was not initialized")
    return _WORKER_EVALUATOR.evaluate(replicate)


@dataclass(frozen=True)
class CoordinatorResult:
    execution_plan: Mapping[str, Any]
    execution_plan_path: Path
    state_path: Path
    completed_replicates: int
    reused_replicates: int
    retried_replicates: int
    status: str


def _write_state(path: Path, payload: Mapping[str, Any]) -> None:
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )


def run_parallel_execution(
    *,
    manifest: MeasurementValidationManifest,
    synthetic: SyntheticRunManifest,
    parent_execution_id: str,
    output_dir: Path,
    evaluator: ReplicateEvaluator,
    worker_count: int,
    maximum_retries: int = 2,
    progress_projection_path: Path | None = None,
    stop_after_new_replicates: int | None = None,
) -> CoordinatorResult:
    if worker_count < 1:
        raise ValueError("worker_count must be positive")
    if stop_after_new_replicates is not None and stop_after_new_replicates < 1:
        raise ValueError("stop_after_new_replicates must be positive")
    plan = execution_plan_summary(
        manifest=manifest,
        synthetic=synthetic,
        parent_execution_id=parent_execution_id,
        shard_count=worker_count,
    )
    plan_path = (
        output_dir
        / "plan"
        / str(plan["artifact_digest"])
        / "execution-plan.json"
    )
    persist_immutable(plan_path, plan)
    state_path = output_dir / "coordinator-state.json"

    def project_state(payload: Mapping[str, Any]) -> None:
        _write_state(state_path, payload)
        if progress_projection_path is not None:
            _write_state(progress_projection_path, payload)

    all_replicates = tuple(
        iter_replicates(
            manifest=manifest,
            synthetic=synthetic,
            parent_execution_id=parent_execution_id,
        )
    )
    pending: list[AnalysisReplicate] = []
    reused = 0
    for replicate in all_replicates:
        path = _replicate_path(output_dir, replicate)
        if path.is_file():
            payload = _load_object(path)
            if payload.get("identity_artifact_digest") != replicate.artifact_digest:
                raise MeasurementValidationContractError(
                    "measurement_validation_resume_identity_mismatch",
                    f"resume identity changed: {path}",
                )
            reused += 1
        else:
            pending.append(replicate)
    pending.sort(
        key=lambda item: (
            item.cell.outer_issue_count,
            item.cell.cell_id,
            item.replicate_index,
        )
    )
    if stop_after_new_replicates is not None:
        pending = pending[:stop_after_new_replicates]
    target_completed = reused + len(pending)
    completed = reused
    retried = 0
    started_monotonic = time.monotonic()
    completed_this_run = 0
    retry_count: dict[str, int] = {}
    state: dict[str, Any] = {
        "schema_version": "dehps-m4-p2-analysis-coordinator-state.v1",
        "status": "RUNNING",
        "parent_execution_id": parent_execution_id,
        "measurement_validation_manifest_digest": manifest.artifact_digest,
        "execution_plan_digest": plan["artifact_digest"],
        "worker_count": worker_count,
        "total_replicates": len(all_replicates),
        "completed_replicates": completed,
        "reused_replicates": reused,
        "retried_replicates": retried,
        "failed_replicates": 0,
        "execution_order": (
            "shortest_outer_scale_first_then_cell_then_replicate"
        ),
        "result_selection_used": False,
        "elapsed_seconds": 0.0,
        "mean_seconds_per_new_replicate": None,
        "estimated_remaining_seconds": None,
        "heartbeat_at": datetime.now(timezone.utc).isoformat(),
    }
    project_state(state)
    if not pending:
        state["status"] = "COMPLETE"
        project_state(state)
        return CoordinatorResult(
            execution_plan=plan,
            execution_plan_path=plan_path,
            state_path=state_path,
            completed_replicates=completed,
            reused_replicates=reused,
            retried_replicates=retried,
            status="COMPLETE",
        )

    queue_limit = max(worker_count, worker_count * 2)
    pending_iter = iter(pending)
    futures: dict[Future[Mapping[str, Any]], AnalysisReplicate] = {}
    with ProcessPoolExecutor(
        max_workers=worker_count,
        initializer=_initialize_worker,
        initargs=(evaluator,),
    ) as pool:
        for _ in range(min(queue_limit, len(pending))):
            replicate = next(pending_iter, None)
            if replicate is None:
                break
            futures[pool.submit(_evaluate_replicate, replicate)] = replicate
        while futures:
            done, _not_done = wait(
                futures,
                timeout=30.0,
                return_when=FIRST_COMPLETED,
            )
            if not done:
                state.update(
                    {
                        "elapsed_seconds": (
                            time.monotonic() - started_monotonic
                        ),
                        "heartbeat_at": datetime.now(
                            timezone.utc
                        ).isoformat(),
                    }
                )
                project_state(state)
                continue
            for future in done:
                replicate = futures.pop(future)
                try:
                    raw = future.result()
                    result = _validate_replicate_result(
                        raw,
                        replicate=replicate,
                        manifest=manifest,
                    )
                    persist_immutable(_replicate_path(output_dir, replicate), result)
                    completed += 1
                    completed_this_run += 1
                except Exception:
                    count = retry_count.get(replicate.artifact_digest, 0)
                    if count >= maximum_retries:
                        state.update(
                            {
                                "status": "FAILED",
                                "completed_replicates": completed,
                                "retried_replicates": retried,
                                "failed_replicates": 1,
                                "failed_replicate_identity": (
                                    replicate.artifact_digest
                                ),
                                "heartbeat_at": (
                                    datetime.now(timezone.utc).isoformat()
                                ),
                            }
                        )
                        project_state(state)
                        raise
                    retry_count[replicate.artifact_digest] = count + 1
                    retried += 1
                    futures[pool.submit(_evaluate_replicate, replicate)] = replicate
                    continue
                next_replicate = next(pending_iter, None)
                if next_replicate is not None:
                    futures[pool.submit(_evaluate_replicate, next_replicate)] = (
                        next_replicate
                    )
                state.update(
                    {
                        "completed_replicates": completed,
                        "retried_replicates": retried,
                        "failed_replicates": 0,
                        "elapsed_seconds": (
                            time.monotonic() - started_monotonic
                        ),
                        "mean_seconds_per_new_replicate": (
                            (time.monotonic() - started_monotonic)
                            / completed_this_run
                        ),
                        "estimated_remaining_seconds": (
                            (time.monotonic() - started_monotonic)
                            / completed_this_run
                            * (len(all_replicates) - completed)
                        ),
                        "heartbeat_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                project_state(state)
    if completed != target_completed:
        raise MeasurementValidationContractError(
            "measurement_validation_workload_incomplete",
            f"coordinator completed {completed} of target {target_completed}",
        )
    final_status = (
        "INTERRUPTED"
        if stop_after_new_replicates is not None
        and completed != len(all_replicates)
        else "COMPLETE"
    )
    state.update(
        {
            "status": final_status,
            "completed_replicates": completed,
            "retried_replicates": retried,
            "failed_replicates": 0,
            "elapsed_seconds": time.monotonic() - started_monotonic,
            "estimated_remaining_seconds": 0.0,
            "heartbeat_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    project_state(state)
    return CoordinatorResult(
        execution_plan=plan,
        execution_plan_path=plan_path,
        state_path=state_path,
        completed_replicates=completed,
        reused_replicates=reused,
        retried_replicates=retried,
        status=final_status,
    )
