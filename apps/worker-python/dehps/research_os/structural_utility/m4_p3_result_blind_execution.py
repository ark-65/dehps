from __future__ import annotations

import hashlib
import json
import math
import struct
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from dehps.contracts import canonical_digest
from dehps.input_contracts.candidate_abi import (
    CandidateUniverseManifest,
    candidate_unrank,
)
from dehps.input_contracts.history_window import (
    HistorySnapshotArtifact,
    WindowMode,
    WindowSpec,
)
from dehps.models.frequency_ranker import (
    FrequencyRankerConfig,
    infer_next_ssq_draw_date,
)
from dehps.optimization.walk_forward import _config_weight_matrix, build_ranked_universe
from dehps.portfolio.models import (
    PortfolioRequest,
    ScoredCandidate,
    compute_candidate_pool_digest,
)
from dehps.portfolio.selectors import select_portfolio
from dehps.research_os.information_theory.digest import config_digest
from dehps.scoring_kernel import (
    KernelPlanner,
    KernelRequest,
    KernelWorkspace,
    WeightMatrix,
    candidate_store_from_matrix,
)
from dehps.scoring_kernel.runtime_input import RuntimeInputCompiler

from .m4_p3_result_blind_design import M4_P3_STRUCTURAL_UTILITY_GOAL_KEY
from .m4_p3_result_blind_preregistration import (
    M4_P3_STRUCTURAL_UTILITY_EXECUTION_APPROVED_EVENT,
    M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY,
)

M4_P3_STRUCTURAL_UTILITY_EXECUTION_CAPABILITY = (
    "m4_p3_result_blind_structural_utility_blind_generator_and_walk_forward"
)
M4_P3_STRUCTURAL_UTILITY_EXECUTION_COMPLETION_FACT = (
    "m4-p3-result-blind-structural-utility-blind-generator-and-walk-forward:COMPLETE"
)
M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_TASK_KEY = (
    "m4-p3-result-blind-structural-utility-evidence-compiler"
)
M4_P3_STRUCTURAL_UTILITY_EXECUTION_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/"
    "m4-p3-result-blind-structural-utility-blind-execution-source-v1.json"
)

RESEARCH_REQUEST_KEY = (
    "research-m4-p3-result-blind-structural-utility-blind-execution-round-125-20260810"
)
RESEARCH_REQUEST_ID = 457
RESEARCH_EXECUTION_ID = 378
RESEARCH_PARENT_REQUEST_ID = 456
RESEARCH_CONTEXT_FINGERPRINT = (
    "12ce0a5ba65d2d9ff1d3bebe43792bb6671aba9f2c24f2a572aa51e987fc9bb3"
)
RESEARCH_CONTRACT_DOMAIN = (
    "dehps.m4-p3.result-blind-structural-utility-blind-execution-research-contract.v1"
)
RESEARCH_EXECUTION_CONTRACT_DIGEST = (
    "a4167973da82dcdf212dd22ad5e8cf30f4ecf5cbd2ba8c2751a89dd04a4d4660"
)

PARENT_PREREGISTRATION_EXECUTION_ID = (
    "4263c9e224bd09cc416afa4fa9b50c7ed758d96cb38e7405f4c2efc9735c3ce9"
)
PARENT_PREREGISTRATION_EXECUTION_DIGEST = (
    "b46e8b3853ebcd2d47f0d6d68d930a0d1e677261113f908106a37e933f4e8d79"
)
PARENT_PREREGISTRATION_DIGEST = (
    "89d0c2c9d4fdeec96241ad1543d06a39bfd822f63042cdecf6703cd7e67ae4e8"
)
PARENT_HANDOFF_DIGEST = (
    "310a13a11d0ba3dd6289cf085cb5fb95d2383a4771aa515beea1a1a518bd47d7"
)
PARENT_COMPLETION_DIGEST = (
    "79bcdaaed4dd0ffe9321b5de211e97467bcc221c5c8db8b68b7aae82597a247d"
)

FOLD_COUNT = 90
PORTFOLIO_SIZE = 100
RANDOM_REPLICATES = 32
LEGAL_UNIVERSE_SIZE = math.comb(33, 6)
PAIR_COUNT = math.comb(33, 2)
TRIPLE_COUNT = math.comb(33, 3)
TICKET_PAIR_COUNT = math.comb(PORTFOLIO_SIZE, 2)
PAIR_USES = PORTFOLIO_SIZE * math.comb(6, 2)
SCORING_TOP_K = 10_000
SCORING_CHUNK_SIZE = 262_144
SCORING_WORKERS = 8
EXPECTED_CAPABILITY_ARTIFACTS = FOLD_COUNT + 2

FOLD_MANIFEST_DIGEST = (
    "ce03c0d0c42a7eed24c354ac236e143d686b39415a3d4544144d1635b085abd5"
)
RANDOM_SEED_ROOT = "40e7aa77845b2e7f0365e4ab2a26a219304a83c236e66b09e1036d9dfda83f60"
FROZEN_SCORE_CONFIG_DIGEST = (
    "3a021a36e6bb94e6ee8cf64778d4667ce87f06d9e576e195cb53bd20f4a565e0"
)
FAMILY_PARTITION_DIGEST = (
    "448d0ab7bbf021ec3764982439f3d7fd51c8b66bfddb5e0fa0ea7aa586b1b86a"
)

COORDINATE_ORDER = (
    "pair_coverage_ratio",
    "triple_coverage_ratio",
    "high_overlap_ticket_pair_rate",
    "normalized_pair_usage_entropy",
    "largest_similarity_cluster_fraction",
    "family_concentration_hhi",
)
HIGHER_IS_BETTER = frozenset(
    {
        "pair_coverage_ratio",
        "triple_coverage_ratio",
        "normalized_pair_usage_entropy",
    }
)
DEGREE_BINS = ((0, 0), (1, 1), (2, 3), (4, 7), (8, 99))
COMPONENT_SIZE_BINS = (
    (1, 1),
    (2, 3),
    (4, 7),
    (8, 15),
    (16, 31),
    (32, 63),
    (64, 100),
)
SSQ_UNIVERSE = CandidateUniverseManifest(domain_size=33, pick_count=6)

_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/structural_utility/"
    "m4_p3_result_blind_execution.py"
)
_FOLD_DOMAIN = "dehps.m4-p3.result-blind-structural-utility.fold.v1"
_INDEX_DOMAIN = "dehps.m4-p3.result-blind-structural-utility.result-index.v1"
_COMPLETION_DOMAIN = "dehps.m4-p3.result-blind-structural-utility.completion.v1"
_RANDOM_PORTFOLIO_DOMAIN = (
    "dehps.m4-p3.result-blind-structural-utility.random-portfolio.v1"
)


class M4P3ResultBlindStructuralUtilityExecutionError(RuntimeError):
    pass


HistoryLoader = Callable[[str], Sequence[object]]
FoldPersistor = Callable[[Mapping[str, Any]], None]
FoldLoader = Callable[[str], Mapping[str, Any] | None]
CheckpointPersistor = Callable[[Sequence[Mapping[str, Any]]], None]


@dataclass(frozen=True)
class M4P3ResultBlindStructuralUtilityExecutionRun:
    fold_artifacts: tuple[Mapping[str, Any], ...]
    result_index: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return (*self.fold_artifacts, self.result_index, self.completion)


def target_issues() -> tuple[str, ...]:
    return tuple(str(value) for value in range(2_026_002, 2_026_092))


def as_of_issue(target_issue: str) -> str:
    if target_issue not in target_issues():
        raise M4P3ResultBlindStructuralUtilityExecutionError(
            f"m4_p3_structural_utility_unregistered_target:{target_issue}"
        )
    return str(int(target_issue) - 1)


def load_m4_p3_result_blind_structural_utility_execution_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise M4P3ResultBlindStructuralUtilityExecutionError(
            f"m4_p3_structural_utility_execution_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-m4-p3-result-blind-structural-utility-execution-source.v1"
        or payload.get("artifact_type")
        != "m4_p3_result_blind_structural_utility_execution_source"
        or payload.get("contract_key")
        != "M4_P3_RESULT_BLIND_STRUCTURAL_UTILITY_EXECUTION_SOURCE"
        or payload.get("research_request_key") != RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != RESEARCH_REQUEST_ID
        or payload.get("research_execution_id") != RESEARCH_EXECUTION_ID
        or payload.get("research_context_fingerprint") != RESEARCH_CONTEXT_FINGERPRINT
        or payload.get("research_execution_contract_digest")
        != RESEARCH_EXECUTION_CONTRACT_DIGEST
        or payload.get("result_blind") is not True
        or payload.get("execution_authorized") is not False
        or not isinstance(entries, list)
        or len(entries) != 1
        or entries[0].get("path") != _SOURCE_MODULE_PATH
        or payload.get("source_set_digest")
        != config_digest({"source_entries": entries})
        or payload.get("artifact_digest")
        != config_digest(
            {key: value for key, value in payload.items() if key != "artifact_digest"}
        )
    ):
        raise M4P3ResultBlindStructuralUtilityExecutionError(
            "m4_p3_structural_utility_execution_source_invalid"
        )
    return payload


def verify_m4_p3_result_blind_structural_utility_execution_source_bytes(
    *, root_dir: Path, contract: Mapping[str, Any]
) -> None:
    root = root_dir.resolve()
    entry = contract["source_entries"][0]
    path = (root / str(entry["path"])).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise M4P3ResultBlindStructuralUtilityExecutionError(
            "m4_p3_structural_utility_execution_source_missing"
        )
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry.get("content_sha256"):
        raise M4P3ResultBlindStructuralUtilityExecutionError(
            "m4_p3_structural_utility_execution_source_modified"
        )


def validate_research_execution_contract(
    request: Mapping[str, Any], execution: Mapping[str, Any]
) -> Mapping[str, Any]:
    payload = request.get("payload")
    contract = (
        payload.get("execution_contract") if isinstance(payload, Mapping) else None
    )
    metadata = request.get("metadata")
    result = execution.get("result")
    if (
        request.get("request_key") != RESEARCH_REQUEST_KEY
        or request.get("id") != RESEARCH_REQUEST_ID
        or request.get("request_type") != "research_scheduler_request"
        or request.get("status") != "completed"
        or request.get("parent_request_id") != RESEARCH_PARENT_REQUEST_ID
        or not isinstance(metadata, Mapping)
        or metadata.get("result_blind") is not True
        or metadata.get("result_aware") is not False
        or metadata.get("new_model_authorized") is not False
        or not isinstance(payload, Mapping)
        or payload.get("context_fingerprint") != RESEARCH_CONTEXT_FINGERPRINT
        or not isinstance(contract, Mapping)
        or contract.get("status") != "FROZEN_BEFORE_IMPLEMENTATION"
        or canonical_digest(contract, domain=RESEARCH_CONTRACT_DOMAIN)
        != RESEARCH_EXECUTION_CONTRACT_DIGEST
        or execution.get("id") != RESEARCH_EXECUTION_ID
        or execution.get("request_id") != RESEARCH_REQUEST_ID
        or execution.get("status") != "completed"
        or not isinstance(result, Mapping)
        or result.get("contract_status") != "FROZEN_BEFORE_IMPLEMENTATION"
        or result.get("fold_count") != FOLD_COUNT
        or result.get("portfolios_generated") != 0
        or result.get("folds_executed") != 0
        or result.get("target_draw_rows_read") != 0
        or result.get("metric_results_read") != 0
        or result.get("bootstrap_resamples_executed") != 0
        or result.get("candidate_abi_lex_id_origin") != 0
        or result.get("engineering_authorized") is not False
        or result.get("mainline_execution_authorized") is not False
    ):
        raise M4P3ResultBlindStructuralUtilityExecutionError(
            "m4_p3_structural_utility_execution_research_identity_changed"
        )
    return contract


class Sha256CounterStream:
    def __init__(self, seed: bytes) -> None:
        if len(seed) != 32:
            raise ValueError("seed must contain 32 bytes")
        self.seed = seed
        self.counter = 0

    def bounded(self, modulus: int) -> int:
        if not 1 <= modulus <= LEGAL_UNIVERSE_SIZE:
            raise ValueError("modulus is outside the legal universe")
        threshold = (1 << 64) // modulus * modulus
        while True:
            digest = hashlib.sha256(
                self.seed + struct.pack(">Q", self.counter)
            ).digest()
            self.counter += 1
            value = int.from_bytes(digest[:8], "big")
            if value < threshold:
                return value % modulus


def random_seed(*, target_issue: str, replicate_index: int) -> bytes:
    if target_issue not in target_issues() or not 0 <= replicate_index < 32:
        raise ValueError("random seed coordinates are outside the frozen manifest")
    material = "|".join(
        (
            RANDOM_SEED_ROOT,
            FOLD_MANIFEST_DIGEST,
            target_issue,
            f"{replicate_index:02d}",
        )
    )
    return hashlib.sha256(material.encode("utf-8")).digest()


def sample_uniform_legal_lex_ids(
    *, target_issue: str, replicate_index: int
) -> tuple[int, ...]:
    stream = Sha256CounterStream(
        random_seed(target_issue=target_issue, replicate_index=replicate_index)
    )
    swaps: dict[int, int] = {}
    selected: list[int] = []
    for position in range(PORTFOLIO_SIZE):
        chosen_position = position + stream.bounded(LEGAL_UNIVERSE_SIZE - position)
        chosen_value = swaps.get(chosen_position, chosen_position)
        swaps[chosen_position] = swaps.get(position, position)
        swaps.pop(position, None)
        selected.append(chosen_value)
    if len(set(selected)) != PORTFOLIO_SIZE:
        raise M4P3ResultBlindStructuralUtilityExecutionError(
            "m4_p3_structural_utility_random_duplicate"
        )
    return tuple(selected)


def sample_uniform_legal_portfolio(
    *, target_issue: str, replicate_index: int
) -> tuple[tuple[int, ...], ...]:
    return tuple(
        candidate_unrank(lex_id, universe=SSQ_UNIVERSE)
        for lex_id in sample_uniform_legal_lex_ids(
            target_issue=target_issue,
            replicate_index=replicate_index,
        )
    )


def calculate_structural_metrics(
    tickets: Sequence[Sequence[int]],
) -> dict[str, Any]:
    canonical = tuple(tuple(int(number) for number in ticket) for ticket in tickets)
    if len(canonical) != PORTFOLIO_SIZE or len(set(canonical)) != PORTFOLIO_SIZE:
        raise M4P3ResultBlindStructuralUtilityExecutionError(
            "m4_p3_structural_utility_portfolio_identity_invalid"
        )
    for ticket in canonical:
        if (
            len(ticket) != 6
            or ticket != tuple(sorted(ticket))
            or len(set(ticket)) != 6
            or any(number < 1 or number > 33 for number in ticket)
        ):
            raise M4P3ResultBlindStructuralUtilityExecutionError(
                "m4_p3_structural_utility_ticket_invalid"
            )

    pair_order = tuple(
        (left, right) for left in range(1, 34) for right in range(left + 1, 34)
    )
    pair_index = {pair: index for index, pair in enumerate(pair_order)}
    pair_use_counts = [0] * PAIR_COUNT
    triples: set[tuple[int, int, int]] = set()
    for ticket in canonical:
        for left_index in range(6):
            for right_index in range(left_index + 1, 6):
                pair_use_counts[
                    pair_index[(ticket[left_index], ticket[right_index])]
                ] += 1
        for first in range(4):
            for second in range(first + 1, 5):
                for third in range(second + 1, 6):
                    triples.add((ticket[first], ticket[second], ticket[third]))

    adjacency = [set() for _ in range(PORTFOLIO_SIZE)]
    for left in range(PORTFOLIO_SIZE):
        left_set = set(canonical[left])
        for right in range(left + 1, PORTFOLIO_SIZE):
            if len(left_set.intersection(canonical[right])) >= 3:
                adjacency[left].add(right)
                adjacency[right].add(left)
    degrees = [len(neighbors) for neighbors in adjacency]
    components: list[tuple[int, ...]] = []
    remaining = set(range(PORTFOLIO_SIZE))
    while remaining:
        root = min(remaining)
        stack = [root]
        component: set[int] = set()
        while stack:
            vertex = stack.pop()
            if vertex in component:
                continue
            component.add(vertex)
            stack.extend(sorted(adjacency[vertex] - component, reverse=True))
        remaining -= component
        components.append(tuple(sorted(component)))
    components.sort(key=lambda item: (-len(item), item))
    component_size_by_vertex = [0] * PORTFOLIO_SIZE
    for component in components:
        for vertex in component:
            component_size_by_vertex[vertex] = len(component)

    family_counts: Counter[str] = Counter()
    for degree, component_size in zip(degrees, component_size_by_vertex, strict=True):
        degree_bin = _bin_index(degree, DEGREE_BINS)
        size_bin = _bin_index(component_size, COMPONENT_SIZE_BINS)
        family_counts[f"d{degree_bin}:c{size_bin}"] += 1
    all_family_counts = {
        f"d{degree}:c{component}": family_counts.get(f"d{degree}:c{component}", 0)
        for degree in range(len(DEGREE_BINS))
        for component in range(len(COMPONENT_SIZE_BINS))
    }

    distinct_pair_count = sum(count > 0 for count in pair_use_counts)
    high_overlap_count = sum(degrees) // 2
    entropy = -sum(
        (count / PAIR_USES) * math.log(count / PAIR_USES)
        for count in pair_use_counts
        if count > 0
    ) / math.log(PAIR_COUNT)
    values = {
        "pair_coverage_ratio": distinct_pair_count / PAIR_COUNT,
        "triple_coverage_ratio": len(triples) / TRIPLE_COUNT,
        "high_overlap_ticket_pair_rate": high_overlap_count / TICKET_PAIR_COUNT,
        "normalized_pair_usage_entropy": entropy,
        "largest_similarity_cluster_fraction": len(components[0]) / PORTFOLIO_SIZE,
        "family_concentration_hhi": sum(
            (count / PORTFOLIO_SIZE) ** 2 for count in all_family_counts.values()
        ),
    }
    if tuple(values) != COORDINATE_ORDER or not all(
        math.isfinite(value) for value in values.values()
    ):
        raise M4P3ResultBlindStructuralUtilityExecutionError(
            "m4_p3_structural_utility_metric_nonfinite"
        )
    return {
        "protocol": "m4_p3_result_blind_structural_metrics.v1",
        "sufficient_statistics": {
            "distinct_pair_count": distinct_pair_count,
            "distinct_triple_count": len(triples),
            "high_overlap_ticket_pair_count": high_overlap_count,
            "pair_use_counts": pair_use_counts,
            "similarity_graph_degrees": degrees,
            "similarity_component_sizes": [len(item) for item in components],
            "family_counts": all_family_counts,
        },
        "coordinates": values,
    }


def _bin_index(value: int, bins: Sequence[tuple[int, int]]) -> int:
    matches = [index for index, (low, high) in enumerate(bins) if low <= value <= high]
    if len(matches) != 1:
        raise M4P3ResultBlindStructuralUtilityExecutionError(
            "m4_p3_structural_utility_family_bin_invalid"
        )
    return matches[0]


def _artifact(
    *,
    schema_version: str,
    artifact_type: str,
    body: Mapping[str, Any],
    parent_digests: Sequence[str],
    domain: str,
) -> dict[str, Any]:
    payload = {
        "schema_version": schema_version,
        "artifact_type": artifact_type,
        "artifact_digest": "",
        "parent_digests": list(parent_digests),
        **dict(body),
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(identity, domain=domain)
    return payload


def verify_artifact_digest(payload: Mapping[str, Any], *, domain: str) -> None:
    identity = dict(payload)
    digest = identity.pop("artifact_digest", None)
    if digest != canonical_digest(identity, domain=domain):
        raise M4P3ResultBlindStructuralUtilityExecutionError(
            "m4_p3_structural_utility_artifact_digest_mismatch"
        )


class BlindStructuralUtilityFoldRunner:
    def __init__(self, *, code_commit: str) -> None:
        self.code_commit = code_commit
        matrix = build_ranked_universe(include_hard_filter_exclusions=True)
        if len(matrix.numbers) != LEGAL_UNIVERSE_SIZE:
            raise M4P3ResultBlindStructuralUtilityExecutionError(
                "m4_p3_structural_utility_legal_universe_changed"
            )
        self.matrix = matrix
        self.store = candidate_store_from_matrix(matrix)
        verification = self.store.validate()
        self.candidate_verification_id = verification.verified_candidate_id
        self.runtime_compiler = RuntimeInputCompiler()
        self.planner = KernelPlanner("numpy_reference")

    def execute_fold(
        self,
        *,
        target_issue: str,
        history: Sequence[object],
        preregistration: Mapping[str, Any],
        source_contract_digest: str,
    ) -> dict[str, Any]:
        as_of = as_of_issue(target_issue)
        snapshot = HistorySnapshotArtifact.from_history(
            history, source="m4_p3_result_blind_prior_only"
        )
        if snapshot.latest_issue != as_of or snapshot.draw_count < 900:
            raise M4P3ResultBlindStructuralUtilityExecutionError(
                "m4_p3_structural_utility_history_boundary_invalid"
            )
        window = WindowSpec(
            mode=WindowMode.EXPANDING,
            size=None,
            as_of_issue=as_of,
            include_as_of=True,
            minimum_size=900,
            target_issue=target_issue,
        ).materialize(snapshot)
        frozen = preregistration.get("frozen_contract")
        if not isinstance(frozen, Mapping):
            raise M4P3ResultBlindStructuralUtilityExecutionError(
                "m4_p3_structural_utility_preregistration_invalid"
            )
        scored_pool = frozen["shared_scored_pool"]
        weights_payload = scored_pool["frozen_weights"]
        if (
            scored_pool.get("frozen_config_hash") != FROZEN_SCORE_CONFIG_DIGEST
            or not isinstance(weights_payload, Mapping)
            or frozen["fold_manifest"].get("fold_manifest_digest")
            != FOLD_MANIFEST_DIGEST
            or frozen["family_partition"].get("partition_digest")
            != FAMILY_PARTITION_DIGEST
        ):
            raise M4P3ResultBlindStructuralUtilityExecutionError(
                "m4_p3_structural_utility_preregistered_identity_changed"
            )
        config = FrequencyRankerConfig(
            **{str(key): float(value) for key, value in weights_payload.items()}
        )
        weights = WeightMatrix(
            np.ascontiguousarray(_config_weight_matrix((config,)), dtype=np.float64)
        )
        history_rows = window.as_history()
        target_draw_date = infer_next_ssq_draw_date(history_rows)
        runtime = self.runtime_compiler.compile_effective_history(
            history=history_rows,
            candidate_store=self.store,
            tile_size=SCORING_CHUNK_SIZE,
            target_draw_date=target_draw_date,
            target_issue=target_issue,
            source="m4_p3_result_blind_prior_only",
        )
        request = KernelRequest(
            target_scores=np.zeros(1, dtype=np.float64),
            target_lex_id=0,
            target_mask=np.uint64(0),
            top_k=SCORING_TOP_K,
            chunk_size=SCORING_CHUNK_SIZE,
            worker_count=SCORING_WORKERS,
            exact_rank=False,
            red5=False,
            target_excluded=True,
            window_id=target_issues().index(target_issue),
        )
        result = self.planner.score_rank_feature_abi(
            self.planner.prepare_feature_abi(
                runtime.verified_runtime, code_commit=self.code_commit
            ),
            weights,
            request,
            KernelWorkspace(),
        )
        ids = result.top_candidate_ids[0]
        scores = result.top_scores[0]
        if (
            len(ids) != SCORING_TOP_K
            or len({int(item) for item in ids}) != SCORING_TOP_K
        ):
            raise M4P3ResultBlindStructuralUtilityExecutionError(
                "m4_p3_structural_utility_topk_invalid"
            )
        candidates = tuple(
            ScoredCandidate.build(
                source_rank=rank,
                red_numbers=tuple(
                    int(value) for value in self.store.numbers[int(row_id)]
                ),
                score=float(score),
                lex_id=int(row_id),
            )
            for rank, (row_id, score) in enumerate(zip(ids, scores, strict=True), 1)
        )
        pool_digest = compute_candidate_pool_digest(candidates)
        context = {
            "line_key": "m4_p3_result_blind_structural_utility",
            "as_of_issue": as_of,
            "target_issue": target_issue,
            "replicate_id": 0,
        }
        legacy = select_portfolio(
            PortfolioRequest.build(
                candidates=candidates,
                budget=PORTFOLIO_SIZE,
                selector_key="score_topk",
                selector_config={},
                candidate_pool_digest=pool_digest,
                history_digest=snapshot.history_digest,
                score_config_digest=FROZEN_SCORE_CONFIG_DIGEST,
                seed=None,
                context=context,
            )
        )
        candidate = select_portfolio(
            PortfolioRequest.build(
                candidates=candidates,
                budget=PORTFOLIO_SIZE,
                selector_key="greedy_score_diversity",
                selector_config={
                    "alpha": 0.01,
                    "lambda": 10.0,
                    "nu": 2.0,
                    "mu2": 2.0,
                    "mu3": 2.0,
                },
                candidate_pool_digest=pool_digest,
                history_digest=snapshot.history_digest,
                score_config_digest=FROZEN_SCORE_CONFIG_DIGEST,
                seed=None,
                context=context,
            )
        )
        legacy_tickets = tuple(item.red_numbers for item in legacy.selected)
        candidate_tickets = tuple(item.red_numbers for item in candidate.selected)
        random_portfolios = tuple(
            _random_portfolio_payload(target_issue=target_issue, replicate_index=index)
            for index in range(RANDOM_REPLICATES)
        )
        random_means = {
            coordinate: sum(
                float(item["metrics"]["coordinates"][coordinate])
                for item in random_portfolios
            )
            / RANDOM_REPLICATES
            for coordinate in COORDINATE_ORDER
        }
        parent_digests = (
            source_contract_digest,
            PARENT_PREREGISTRATION_DIGEST,
            PARENT_HANDOFF_DIGEST,
            PARENT_COMPLETION_DIGEST,
        )
        return _artifact(
            schema_version="dehps-m4-p3-result-blind-structural-utility-fold.v1",
            artifact_type="m4_p3_result_blind_structural_utility_fold",
            body={
                "status": "COMPLETE",
                "goal_key": M4_P3_STRUCTURAL_UTILITY_GOAL_KEY,
                "task_key": M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY,
                "target_issue": target_issue,
                "as_of_issue": as_of,
                "fold_ordinal": target_issues().index(target_issue),
                "result_blind": True,
                "history_snapshot": snapshot.as_dict(),
                "window_artifact": window.as_dict(),
                "target_draw_date_derivation": "infer_next_ssq_draw_date_from_prior_only_history",
                "target_draw_date": (
                    target_draw_date.isoformat()
                    if target_draw_date is not None
                    else None
                ),
                "candidate_store": {
                    "row_count": len(self.store),
                    "fingerprint": self.store.fingerprint,
                    "candidate_verification_id": self.candidate_verification_id,
                    "lex_id_origin": 0,
                },
                "scoring": {
                    "config_digest": FROZEN_SCORE_CONFIG_DIGEST,
                    "pool_digest": pool_digest,
                    "top_k": SCORING_TOP_K,
                    "backend": result.backend,
                    "contract_version": result.contract_version,
                    "telemetry": result.telemetry,
                    "candidates": [item.as_dict() for item in candidates],
                },
                "arms": {
                    "legacy_structural_top100": {
                        "selection": legacy.as_dict(),
                        "metrics": calculate_structural_metrics(legacy_tickets),
                    },
                    "prediction_v2_structural_selection_100": {
                        "selection": candidate.as_dict(),
                        "metrics": calculate_structural_metrics(candidate_tickets),
                    },
                    "uniform_random_without_replacement": {
                        "replicates": list(random_portfolios),
                        "fold_coordinate_means": random_means,
                    },
                },
                "portfolios_generated": 34,
                "random_replicates_executed": 32,
                "metric_portfolios_evaluated": 34,
                "target_draw_rows_read": 0,
                "winning_labels_read": 0,
                "payout_or_reward_values_read": 0,
                "outcome_rank_values_read": 0,
                "bootstrap_resamples_executed": 0,
                "production_action": "none",
            },
            parent_digests=parent_digests,
            domain=_FOLD_DOMAIN,
        )


def _random_portfolio_payload(
    *, target_issue: str, replicate_index: int
) -> dict[str, Any]:
    lex_ids = sample_uniform_legal_lex_ids(
        target_issue=target_issue, replicate_index=replicate_index
    )
    tickets = tuple(candidate_unrank(item, universe=SSQ_UNIVERSE) for item in lex_ids)
    payload = {
        "replicate_index": replicate_index,
        "seed_sha256": random_seed(
            target_issue=target_issue, replicate_index=replicate_index
        ).hex(),
        "lex_ids": list(lex_ids),
        "tickets": [list(ticket) for ticket in tickets],
        "metrics": calculate_structural_metrics(tickets),
    }
    payload["portfolio_digest"] = canonical_digest(
        payload, domain=_RANDOM_PORTFOLIO_DOMAIN
    )
    return payload


def build_result_index(
    fold_artifacts: Sequence[Mapping[str, Any]], *, source_contract_digest: str
) -> dict[str, Any]:
    folds = tuple(fold_artifacts)
    if tuple(item.get("target_issue") for item in folds) != target_issues():
        raise M4P3ResultBlindStructuralUtilityExecutionError(
            "m4_p3_structural_utility_fold_sequence_invalid"
        )
    favorable_series: dict[str, list[float]] = {}
    for control in ("uniform_random_without_replacement", "legacy_structural_top100"):
        for coordinate in COORDINATE_ORDER:
            key = f"{coordinate}:{control}"
            values: list[float] = []
            for fold in folds:
                arms = fold["arms"]
                candidate_value = float(
                    arms["prediction_v2_structural_selection_100"]["metrics"][
                        "coordinates"
                    ][coordinate]
                )
                control_value = (
                    float(arms[control]["fold_coordinate_means"][coordinate])
                    if control == "uniform_random_without_replacement"
                    else float(arms[control]["metrics"]["coordinates"][coordinate])
                )
                values.append(
                    candidate_value - control_value
                    if coordinate in HIGHER_IS_BETTER
                    else control_value - candidate_value
                )
            favorable_series[key] = values
    return _artifact(
        schema_version=("dehps-m4-p3-result-blind-structural-utility-result-index.v1"),
        artifact_type="m4_p3_result_blind_structural_utility_result_index",
        body={
            "status": "COMPLETE",
            "goal_key": M4_P3_STRUCTURAL_UTILITY_GOAL_KEY,
            "fold_count": FOLD_COUNT,
            "fold_manifest_digest": FOLD_MANIFEST_DIGEST,
            "coordinate_order": list(COORDINATE_ORDER),
            "control_order": [
                "uniform_random_without_replacement",
                "legacy_structural_top100",
            ],
            "fold_artifact_digests": [item["artifact_digest"] for item in folds],
            "favorable_difference_series": favorable_series,
            "bootstrap_resamples_executed": 0,
            "holm_executed": False,
            "evidence_created": False,
            "route_decision_created": False,
            "target_draw_rows_read": 0,
            "next_consumer": M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_TASK_KEY,
            "production_action": "none",
        },
        parent_digests=(
            source_contract_digest,
            PARENT_PREREGISTRATION_DIGEST,
            *(str(item["artifact_digest"]) for item in folds),
        ),
        domain=_INDEX_DOMAIN,
    )


def build_completion(
    *,
    result_index: Mapping[str, Any],
    fold_artifacts: Sequence[Mapping[str, Any]],
    source_contract_digest: str,
) -> dict[str, Any]:
    folds = tuple(fold_artifacts)
    if len(folds) != FOLD_COUNT:
        raise M4P3ResultBlindStructuralUtilityExecutionError(
            "m4_p3_structural_utility_incomplete_folds"
        )
    return _artifact(
        schema_version="dehps-m4-p3-result-blind-structural-utility-completion.v1",
        artifact_type="m4_p3_result_blind_structural_utility_execution_completion",
        body={
            "status": "COMPLETE",
            "completion_fact": M4_P3_STRUCTURAL_UTILITY_EXECUTION_COMPLETION_FACT,
            "fold_count": FOLD_COUNT,
            "portfolio_budget": PORTFOLIO_SIZE,
            "portfolios_generated": FOLD_COUNT * (2 + RANDOM_REPLICATES),
            "random_replicates_executed": FOLD_COUNT * RANDOM_REPLICATES,
            "metric_portfolios_evaluated": FOLD_COUNT * (2 + RANDOM_REPLICATES),
            "result_index_digest": result_index["artifact_digest"],
            "fold_artifact_digests": [item["artifact_digest"] for item in folds],
            "registered_child_count": EXPECTED_CAPABILITY_ARTIFACTS,
            "target_draw_rows_read": 0,
            "winning_labels_read": 0,
            "payout_or_reward_values_read": 0,
            "outcome_rank_values_read": 0,
            "bootstrap_resamples_executed": 0,
            "new_prediction_evidence_created": False,
            "new_structural_decision_evidence_created": False,
            "old_training_lines": "FROZEN",
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "promotion_gate_opened": False,
            "predictive_p3_authorized": False,
            "next_consumer": M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_TASK_KEY,
            "production_action": "none",
        },
        parent_digests=(
            source_contract_digest,
            PARENT_PREREGISTRATION_DIGEST,
            str(result_index["artifact_digest"]),
            *(str(item["artifact_digest"]) for item in folds),
        ),
        domain=_COMPLETION_DOMAIN,
    )


def execute_result_blind_walk_forward(
    *,
    history_loader: HistoryLoader,
    preregistration: Mapping[str, Any],
    source_contract_digest: str,
    code_commit: str,
    persist_fold: FoldPersistor | None = None,
    load_fold: FoldLoader | None = None,
    persist_checkpoint: CheckpointPersistor | None = None,
) -> M4P3ResultBlindStructuralUtilityExecutionRun:
    if preregistration.get("artifact_digest") != PARENT_PREREGISTRATION_DIGEST:
        raise M4P3ResultBlindStructuralUtilityExecutionError(
            "m4_p3_structural_utility_parent_preregistration_changed"
        )
    runner = BlindStructuralUtilityFoldRunner(code_commit=code_commit)
    folds: list[Mapping[str, Any]] = []
    for ordinal, issue in enumerate(target_issues()):
        fold = load_fold(issue) if load_fold is not None else None
        if fold is not None:
            _verify_reusable_fold(
                fold,
                target_issue=issue,
                fold_ordinal=ordinal,
                source_contract_digest=source_contract_digest,
            )
        else:
            fold = runner.execute_fold(
                target_issue=issue,
                history=history_loader(as_of_issue(issue)),
                preregistration=preregistration,
                source_contract_digest=source_contract_digest,
            )
            if persist_fold is not None:
                persist_fold(fold)
        folds.append(fold)
        if persist_checkpoint is not None and len(folds) % 5 == 0:
            persist_checkpoint(tuple(folds))
    result_index = build_result_index(
        folds, source_contract_digest=source_contract_digest
    )
    completion = build_completion(
        result_index=result_index,
        fold_artifacts=folds,
        source_contract_digest=source_contract_digest,
    )
    return M4P3ResultBlindStructuralUtilityExecutionRun(
        fold_artifacts=tuple(folds),
        result_index=result_index,
        completion=completion,
    )


def _verify_reusable_fold(
    fold: Mapping[str, Any],
    *,
    target_issue: str,
    fold_ordinal: int,
    source_contract_digest: str,
) -> None:
    verify_artifact_digest(fold, domain=_FOLD_DOMAIN)
    expected_parents = [
        source_contract_digest,
        PARENT_PREREGISTRATION_DIGEST,
        PARENT_HANDOFF_DIGEST,
        PARENT_COMPLETION_DIGEST,
    ]
    if (
        fold.get("schema_version")
        != "dehps-m4-p3-result-blind-structural-utility-fold.v1"
        or fold.get("artifact_type") != "m4_p3_result_blind_structural_utility_fold"
        or fold.get("status") != "COMPLETE"
        or fold.get("target_issue") != target_issue
        or fold.get("as_of_issue") != as_of_issue(target_issue)
        or fold.get("fold_ordinal") != fold_ordinal
        or fold.get("parent_digests") != expected_parents
        or fold.get("result_blind") is not True
        or fold.get("target_draw_rows_read") != 0
        or fold.get("winning_labels_read") != 0
        or fold.get("payout_or_reward_values_read") != 0
        or fold.get("outcome_rank_values_read") != 0
        or fold.get("bootstrap_resamples_executed") != 0
        or fold.get("portfolios_generated") != 34
        or fold.get("random_replicates_executed") != RANDOM_REPLICATES
        or fold.get("metric_portfolios_evaluated") != 34
    ):
        raise M4P3ResultBlindStructuralUtilityExecutionError(
            "m4_p3_structural_utility_reusable_fold_invalid"
        )


def replay_result_blind_walk_forward_artifacts(
    *,
    fold_artifacts: Sequence[Mapping[str, Any]],
    result_index: Mapping[str, Any],
    completion: Mapping[str, Any],
    source_contract_digest: str,
) -> dict[str, Any]:
    folds = tuple(fold_artifacts)
    for fold in folds:
        verify_artifact_digest(fold, domain=_FOLD_DOMAIN)
        if (
            fold.get("result_blind") is not True
            or fold.get("target_draw_rows_read") != 0
            or fold.get("winning_labels_read") != 0
            or fold.get("payout_or_reward_values_read") != 0
            or fold.get("outcome_rank_values_read") != 0
            or fold.get("bootstrap_resamples_executed") != 0
        ):
            raise M4P3ResultBlindStructuralUtilityExecutionError(
                "m4_p3_structural_utility_replay_blindness_changed"
            )
    rebuilt_index = build_result_index(
        folds, source_contract_digest=source_contract_digest
    )
    rebuilt_completion = build_completion(
        result_index=rebuilt_index,
        fold_artifacts=folds,
        source_contract_digest=source_contract_digest,
    )
    if rebuilt_index != dict(result_index) or rebuilt_completion != dict(completion):
        raise M4P3ResultBlindStructuralUtilityExecutionError(
            "m4_p3_structural_utility_replay_identity_changed"
        )
    return {
        "schema_version": (
            "dehps-m4-p3-result-blind-structural-utility-execution-replay.v1"
        ),
        "status": "REPLAY_VERIFIED",
        "same_registered_content": True,
        "manual_input_assembly": False,
        "workload_rerun": False,
        "folds_replayed": FOLD_COUNT,
        "registered_capability_artifact_count": EXPECTED_CAPABILITY_ARTIFACTS,
        "target_draw_rows_read": 0,
        "bootstrap_resamples_executed": 0,
        "next_consumer": M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_TASK_KEY,
    }


__all__ = (
    "M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_TASK_KEY",
    "M4_P3_STRUCTURAL_UTILITY_EXECUTION_APPROVED_EVENT",
    "M4_P3_STRUCTURAL_UTILITY_EXECUTION_CAPABILITY",
    "M4_P3_STRUCTURAL_UTILITY_EXECUTION_COMPLETION_FACT",
    "M4_P3_STRUCTURAL_UTILITY_EXECUTION_SOURCE_CONTRACT_PATH",
    "M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY",
    "BlindStructuralUtilityFoldRunner",
    "M4P3ResultBlindStructuralUtilityExecutionError",
    "M4P3ResultBlindStructuralUtilityExecutionRun",
    "as_of_issue",
    "build_completion",
    "build_result_index",
    "calculate_structural_metrics",
    "execute_result_blind_walk_forward",
    "load_m4_p3_result_blind_structural_utility_execution_source_contract",
    "random_seed",
    "replay_result_blind_walk_forward_artifacts",
    "sample_uniform_legal_lex_ids",
    "sample_uniform_legal_portfolio",
    "target_issues",
    "validate_research_execution_contract",
    "verify_m4_p3_result_blind_structural_utility_execution_source_bytes",
)
