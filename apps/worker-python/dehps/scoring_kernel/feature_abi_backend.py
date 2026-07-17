from __future__ import annotations

from dataclasses import dataclass
import resource
import time

import numpy as np

from dehps.contracts import canonical_digest
from dehps.feature_runtime.compiler import feature_array_digest
from dehps.feature_runtime.runtime import FeatureABIRuntime
from dehps.ranking_contract import STRICT_RANKING_CONTRACT
from dehps.runtime_envelope import (
    RuntimeEnvelopeCompiler,
    RuntimeEnvelopeV1,
    RuntimeEnvelopeVerifier,
    RuntimeState,
)
from dehps.scoring_kernel.contracts import (
    SCORE_ROUND_DIGITS,
    STRICT_CONTRACT_VERSION,
    KernelRequest,
    KernelResult,
    KernelWorkspace,
    WeightMatrix,
)
from dehps.scoring_kernel.numpy_backend import _ordered_topk
from dehps.scoring_kernel.telemetry import record_kernel_telemetry


@dataclass(frozen=True)
class PreparedFeatureABIRuntime:
    runtime: FeatureABIRuntime
    backend_name: str
    prepare_seconds: float
    runtime_envelope: RuntimeEnvelopeV1


@dataclass(frozen=True)
class FeatureABITileResult:
    scores: np.ndarray
    better: np.ndarray
    equal_before: np.ndarray
    red5_mask: np.ndarray
    kernel_seconds: float
    rank_seconds: float


class FeatureABINumpyReferenceBackend:
    name = "feature_abi_numpy_reference"
    contract_version = STRICT_CONTRACT_VERSION

    def prepare(
        self,
        runtime: FeatureABIRuntime,
        *,
        code_commit: str,
    ) -> PreparedFeatureABIRuntime:
        started = time.perf_counter()
        runtime.verify()
        runtime_envelope = RuntimeEnvelopeCompiler().compile_kernel_ready(
            runtime,
            backend=self.name,
            code_commit=code_commit,
        )
        return PreparedFeatureABIRuntime(
            runtime=runtime,
            backend_name=self.name,
            prepare_seconds=time.perf_counter() - started,
            runtime_envelope=runtime_envelope,
        )

    def _tile(
        self,
        *,
        values: np.ndarray,
        candidate_masks: np.ndarray,
        start: int,
        weights: np.ndarray,
        target_scores: np.ndarray,
        target_ids: np.ndarray,
        exact_rank: bool,
        target_mask: np.uint64,
        red5: bool,
        workspace: KernelWorkspace,
    ) -> FeatureABITileResult:
        row_count = len(values)
        kernel_started = time.perf_counter()
        scores = workspace.score_view(row_count, weights.shape[0])
        np.matmul(values, weights.T, out=scores)
        np.round(scores, SCORE_ROUND_DIGITS, out=scores)
        kernel_seconds = time.perf_counter() - kernel_started

        rank_started = time.perf_counter()
        ids = np.arange(start, start + row_count, dtype=np.int64)
        if exact_rank:
            better = (scores > target_scores).sum(axis=0, dtype=np.int64)
            equal_before = (
                (scores == target_scores) & (ids[:, None] < target_ids)
            ).sum(axis=0, dtype=np.int64)
        else:
            better = np.zeros(weights.shape[0], dtype=np.int64)
            equal_before = np.zeros(weights.shape[0], dtype=np.int64)
        red5_flags = workspace.red5_view(row_count)
        if red5:
            red5_flags[:] = np.bitwise_count(candidate_masks & target_mask) == 5
        else:
            red5_flags.fill(0)
        rank_seconds = time.perf_counter() - rank_started
        return FeatureABITileResult(
            scores=scores,
            better=np.ascontiguousarray(better),
            equal_before=np.ascontiguousarray(equal_before),
            red5_mask=red5_flags.view(np.bool_),
            kernel_seconds=kernel_seconds,
            rank_seconds=rank_seconds,
        )

    def score_rank(
        self,
        prepared: PreparedFeatureABIRuntime,
        weights: WeightMatrix,
        request: KernelRequest,
        workspace: KernelWorkspace | None = None,
    ) -> KernelResult:
        workspace = workspace or KernelWorkspace()
        runtime = prepared.runtime
        runtime.verify()
        RuntimeEnvelopeVerifier().verify(
            prepared.runtime_envelope,
            runtime=runtime,
            expected_backend=self.name,
        )
        if prepared.runtime_envelope.state is not RuntimeState.KERNEL_READY:
            raise ValueError("Feature ABI runtime envelope must be kernel_ready")
        executing_envelope = prepared.runtime_envelope.transition(RuntimeState.KERNEL_EXECUTING)
        candidate_count = runtime.candidate_count
        request.validate(config_count=weights.config_count, candidate_count=candidate_count)
        if weights.values.shape[1] != 32:
            raise ValueError("strict_v1 requires 32 components")

        started_wall = time.perf_counter()
        started_cpu = time.process_time()
        effective_top_k = min(request.top_k, candidate_count)
        better = np.zeros(weights.config_count, dtype=np.int64)
        equal_before = np.zeros(weights.config_count, dtype=np.int64)
        top_ids = [np.empty(0, dtype=np.int64) for _ in range(weights.config_count)]
        top_scores = [np.empty(0, dtype=np.float64) for _ in range(weights.config_count)]
        red5_ids = np.full(weights.config_count, -1, dtype=np.int64)
        red5_scores = np.full(weights.config_count, -np.inf, dtype=np.float64)
        target_ids = np.full(weights.config_count, request.target_lex_id, dtype=np.int64)
        kernel_seconds = 0.0
        rank_seconds = 0.0
        topk_merge_seconds = 0.0
        chunk_count = 0
        score_passes = 0

        if not request.target_excluded or request.top_k or request.red5:
            score_passes += 1
            for package in runtime.feature_tiles:
                start = package.header.start
                end = package.header.end
                tile = self._tile(
                    values=package.values,
                    candidate_masks=runtime.candidate_package.mask[start:end],
                    start=start,
                    weights=weights.values,
                    target_scores=request.target_scores,
                    target_ids=target_ids,
                    exact_rank=request.exact_rank and not request.target_excluded,
                    target_mask=request.target_mask,
                    red5=request.red5,
                    workspace=workspace,
                )
                kernel_seconds += tile.kernel_seconds
                rank_seconds += tile.rank_seconds
                merge_started = time.perf_counter()
                ids = np.arange(start, end, dtype=np.int64)
                better += tile.better
                equal_before += tile.equal_before
                for config_index in range(weights.config_count):
                    if effective_top_k:
                        merged_ids = np.concatenate((top_ids[config_index], ids))
                        merged_scores = np.concatenate(
                            (top_scores[config_index], tile.scores[:, config_index])
                        )
                        top_ids[config_index], top_scores[config_index] = _ordered_topk(
                            merged_ids, merged_scores, effective_top_k
                        )
                    if request.red5 and tile.red5_mask.any():
                        local_ids, local_scores = _ordered_topk(
                            ids[tile.red5_mask],
                            tile.scores[tile.red5_mask, config_index],
                            1,
                        )
                        merged_ids = np.concatenate(
                            (np.array([red5_ids[config_index]], dtype=np.int64), local_ids)
                        )
                        merged_scores = np.concatenate(
                            (np.array([red5_scores[config_index]], dtype=np.float64), local_scores)
                        )
                        valid = merged_ids >= 0
                        chosen_ids, chosen_scores = _ordered_topk(
                            merged_ids[valid], merged_scores[valid], 1
                        )
                        if len(chosen_ids):
                            red5_ids[config_index] = chosen_ids[0]
                            red5_scores[config_index] = chosen_scores[0]
                topk_merge_seconds += time.perf_counter() - merge_started
                chunk_count += 1

        if request.target_excluded and request.exact_rank:
            exact_ranks = np.full(weights.config_count, candidate_count + 1, dtype=np.int64)
        elif request.exact_rank:
            exact_ranks = better + equal_before + 1
        else:
            exact_ranks = np.zeros(weights.config_count, dtype=np.int64)

        red5_ranks = np.full(weights.config_count, -1, dtype=np.int64)
        if request.red5 and np.any(red5_ids >= 0):
            score_passes += 1
            red5_better = np.zeros(weights.config_count, dtype=np.int64)
            red5_equal = np.zeros(weights.config_count, dtype=np.int64)
            for package in runtime.feature_tiles:
                start = package.header.start
                end = package.header.end
                tile = self._tile(
                    values=package.values,
                    candidate_masks=runtime.candidate_package.mask[start:end],
                    start=start,
                    weights=weights.values,
                    target_scores=red5_scores,
                    target_ids=red5_ids,
                    exact_rank=True,
                    target_mask=request.target_mask,
                    red5=False,
                    workspace=workspace,
                )
                kernel_seconds += tile.kernel_seconds
                rank_seconds += tile.rank_seconds
                red5_better += tile.better
                red5_equal += tile.equal_before
                chunk_count += 1
            valid = red5_ids >= 0
            red5_ranks[valid] = red5_better[valid] + red5_equal[valid] + 1

        top_id_matrix = np.full(
            (weights.config_count, effective_top_k), -1, dtype=np.int64
        )
        top_score_matrix = np.full(
            (weights.config_count, effective_top_k), -np.inf, dtype=np.float64
        )
        for config_index in range(weights.config_count):
            count = len(top_ids[config_index])
            top_id_matrix[config_index, :count] = top_ids[config_index]
            top_score_matrix[config_index, :count] = top_scores[config_index]

        wall_seconds = time.perf_counter() - started_wall
        cpu_seconds = time.process_time() - started_cpu
        score_cells = candidate_count * weights.config_count * score_passes
        feature_envelope = runtime.feature_tiles[0].runtime_envelope.as_dict()
        candidate_envelope = runtime.candidate_package.runtime_envelope.as_dict()
        feature_contract = feature_envelope["feature_contract"]
        candidate_contract = candidate_envelope["candidate_contract"]
        if not isinstance(feature_contract, dict) or not isinstance(candidate_contract, dict):
            raise ValueError("runtime envelope contracts must be structured")
        max_tile_rows = max(package.header.row_count for package in runtime.feature_tiles)
        telemetry: dict[str, int | float | str] = {
            "backend": self.name,
            "contract_version": self.contract_version,
            "ranking_contract": STRICT_RANKING_CONTRACT,
            "candidate_count": candidate_count,
            "candidate_contract": str(candidate_contract["contract_key"]),
            "candidate_abi": str(candidate_envelope["candidate_abi"]),
            "candidate_package_digest": runtime.candidate_package.package_digest,
            "candidate_identity_id_kind": "candidate_abi_row_index",
            "feature_contract": str(feature_contract["contract_key"]),
            "feature_abi": str(feature_envelope["feature_abi"]),
            "feature_layout_digest": str(feature_envelope["layout_digest"]),
            "feature_runtime_digest": runtime.runtime_digest,
            "window_artifact_digest": str(feature_envelope["window_artifact_digest"]),
            "target_context_digest": str(feature_envelope["target_context_digest"]),
            "window_id": request.window_id,
            "config_count": weights.config_count,
            "score_cells": score_cells,
            "chunk_size": max_tile_rows,
            "chunk_count": chunk_count,
            "worker_count": 1,
            "prepare_time": prepared.prepare_seconds,
            "feature_time": 0.0,
            "kernel_time": kernel_seconds,
            "rank_time": rank_seconds,
            "topk_merge_time": topk_merge_seconds,
            "wall_time": wall_seconds,
            "cpu_time": cpu_seconds,
            "peak_rss": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
            "peak_rss_kib": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
            "cells_per_second": score_cells / wall_seconds if wall_seconds else 0.0,
            "bytes_read_estimate": int(
                candidate_count * weights.config_count * 32 * 8 * score_passes
            ),
            "workspace_bytes_estimate": int(
                max_tile_rows * weights.config_count * 8 + max_tile_rows
            ),
        }
        payload_digest = kernel_result_payload_digest(
            target_scores=request.target_scores,
            exact_ranks=exact_ranks,
            top_candidate_ids=top_id_matrix,
            top_scores=top_score_matrix,
            red5_candidate_ids=red5_ids,
            red5_scores=red5_scores,
            red5_ranks=red5_ranks,
        )
        produced_envelope = executing_envelope.produce_artifact(payload_digest)
        RuntimeEnvelopeVerifier().verify_artifact_payload(
            produced_envelope,
            payload_digest=payload_digest,
            runtime=runtime,
            expected_backend=self.name,
        )
        telemetry["runtime_envelope_version"] = produced_envelope.envelope_version
        telemetry["runtime_envelope_state"] = produced_envelope.state.value
        telemetry["runtime_envelope_digest"] = produced_envelope.envelope_digest
        telemetry["artifact_payload_digest"] = payload_digest
        result = KernelResult(
            backend=self.name,
            contract_version=self.contract_version,
            target_scores=np.ascontiguousarray(request.target_scores.copy()),
            exact_ranks=np.ascontiguousarray(exact_ranks),
            top_candidate_ids=np.ascontiguousarray(top_id_matrix),
            top_scores=np.ascontiguousarray(top_score_matrix),
            red5_candidate_ids=np.ascontiguousarray(red5_ids),
            red5_scores=np.ascontiguousarray(red5_scores),
            red5_ranks=np.ascontiguousarray(red5_ranks),
            telemetry=telemetry,
            runtime_envelope=produced_envelope.as_dict(),
        )
        record_kernel_telemetry(telemetry)
        return result


def kernel_result_payload_digest(
    *,
    target_scores: np.ndarray,
    exact_ranks: np.ndarray,
    top_candidate_ids: np.ndarray,
    top_scores: np.ndarray,
    red5_candidate_ids: np.ndarray,
    red5_scores: np.ndarray,
    red5_ranks: np.ndarray,
) -> str:
    arrays = {
        "target_scores": target_scores,
        "exact_ranks": exact_ranks,
        "top_candidate_ids": top_candidate_ids,
        "top_scores": top_scores,
        "red5_candidate_ids": red5_candidate_ids,
        "red5_scores": red5_scores,
        "red5_ranks": red5_ranks,
    }
    return canonical_digest(
        {
            name: feature_array_digest(
                np.ascontiguousarray(value),
                domain=f"dehps.kernel-result.{name}.v1",
            )
            for name, value in arrays.items()
        },
        domain="dehps.kernel-result-payload.v1",
    )
