from __future__ import annotations

import json
import os
import resource
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations, pairwise
from math import comb
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_TASK_KEY = (
    "prediction-v2-balanced-design-feasibility-execution"
)
PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_CAPABILITY = (
    "prediction_v2_balanced_design_feasibility_execution"
)
PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_COMPLETION_FACT = (
    "prediction-v2-balanced-design-feasibility-execution:COMPLETE"
)
PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_TASK_KEY = (
    "prediction-v2-balanced-design-feasibility-result-decision"
)
PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/"
    "prediction-v2-balanced-design-feasibility-execution-source-v1.json"
)
PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_APPROVED_EVENT = (
    "research-contract:prediction-v2-balanced-design-feasibility-execution:approved"
)

PREREGISTRATION_DIGEST = (
    "64eb0919244444dda16997153c7de747c83284bbad091bdb8e36e64335ce88ce"
)
EXECUTION_HANDOFF_DIGEST = (
    "4693522bbbde211aec777d4e6644773fcf9c8a1bfe818100d1e7117cd28f1d69"
)
PREREGISTRATION_COMPLETION_DIGEST = (
    "4bc8585d86c9f8e8c25d9f31f26c92189fed46e4dfb607717477f0c6a2225a47"
)
PREREGISTRATION_MAINLINE_EXECUTION_DIGEST = (
    "87dbea81af5816b06a09857bc61795ae1c719ae984ed8df7e01b339f9c4bb597"
)

CONSTRUCTOR_FAMILY = "Z33_TRANSLATION_ORBIT_EXACT_MULTICOVER_V1"
POSITIVE_OUTCOME = "FOUND_EXACT_2_33_6_5_DESIGN"
BOUNDED_NEGATIVE_OUTCOME = "NOT_FOUND_WITHIN_FROZEN_BUDGET"
INVALID_OUTCOME = "INVALID_EXECUTION_NO_DECISION"
REPETITION_SCAN = "ABSENT_BY_CONSTRUCTION"

POINT_COUNT = 33
BLOCK_SIZE = 6
BLOCK_COUNT = 176
POINT_REPLICATION_TARGET = 32
PAIR_COUNT = 528
PAIR_REPLICATION_TARGET = 5
PAIR_COORDINATE_COUNT = 16
LEGAL_BLOCK_COUNT = 1_107_568
CANONICAL_CANDIDATE_COUNT = 201_376
FULL_ORBIT_COUNT = 33_561
SHORT_ORBIT_COUNT = 5
FULL_ORBIT_SIZE = 33
SHORT_ORBIT_SIZE = 11
MAXIMUM_MULTICOVER_NODE_EXPANSIONS = 100_000_000
CHECKPOINT_INTERVAL_NODE_EXPANSIONS = 1_000_000
MAXIMUM_RESIDENT_BYTES = 4_294_967_296
SIGNATURE_WEIGHT = 15
TARGET_SIGNATURE = (PAIR_REPLICATION_TARGET,) * PAIR_COORDINATE_COUNT
PROFILE_ORDER = ((5, 1), (4, 4))

_SOURCE_SCHEMA = "dehps-prediction-v2-balanced-design-feasibility-execution-source.v1"
_SOURCE_ARTIFACT_TYPE = "prediction_v2_balanced_design_feasibility_execution_source"
_CHECKPOINT_DOMAIN = "dehps.prediction-v2.balanced-design.checkpoint.v1"
_TRANSCRIPT_DOMAIN = "dehps.prediction-v2.balanced-design.search-transcript.v1"
_CERTIFICATE_DOMAIN = "dehps.prediction-v2.balanced-design.certificate.v1"
_INVENTORY_DOMAIN = "dehps.prediction-v2.balanced-design.orbit-inventory.v1"
_RESULT_DOMAIN = "dehps.prediction-v2.balanced-design.search-result.v1"
_COMPLETION_DOMAIN = "dehps.prediction-v2.balanced-design.execution-completion.v1"

_EXPECTED_RESEARCH_REQUEST_KEY = (
    "research-prediction-v2-balanced-design-preregistration-round-90-20260809"
)
_EXPECTED_ENGINEERING_REQUEST_KEY = (
    "engineering-prediction-v2-balanced-design-search-index-optimization-"
    "round-95-20260809"
)
_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/information_theory/measurement_system_v2/"
    "prediction_v2_balanced_design_feasibility_execution.py"
)


class BalancedDesignExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class OrbitRepresentative:
    representative_id: int
    block: tuple[int, ...]
    orbit_size: int
    stabilizer_size: int
    signature: tuple[int, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "representative_id": self.representative_id,
            "block": list(self.block),
            "orbit_size": self.orbit_size,
            "stabilizer_size": self.stabilizer_size,
            "signature": list(self.signature),
        }


@dataclass(frozen=True)
class SignatureGroup:
    signature: tuple[int, ...]
    representative_ids: tuple[int, ...]

    @property
    def multiplicity(self) -> int:
        return len(self.representative_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "signature": list(self.signature),
            "representative_ids": list(self.representative_ids),
            "multiplicity": self.multiplicity,
        }


@dataclass(frozen=True)
class _SignatureCompatibilityIndex:
    signature_weight: int
    all_groups_bits: int
    positive_bits_by_coordinate: tuple[int, ...]
    allowed_bits_by_coordinate: tuple[tuple[int, ...], ...]
    value_bits_by_coordinate: tuple[tuple[int, ...], ...]

    @classmethod
    def build(
        cls,
        groups: Sequence[SignatureGroup],
    ) -> _SignatureCompatibilityIndex:
        if not groups or not groups[0].signature:
            raise BalancedDesignExecutionError("signature_groups_empty")
        width = len(groups[0].signature)
        signature_weight = sum(groups[0].signature)
        maximum_values = [0] * width
        for group in groups:
            if (
                len(group.signature) != width
                or sum(group.signature) != signature_weight
                or any(value < 0 for value in group.signature)
                or group.multiplicity <= 0
            ):
                raise BalancedDesignExecutionError("signature_group_weight_changed")
            for coordinate, value in enumerate(group.signature):
                maximum_values[coordinate] = max(
                    maximum_values[coordinate],
                    value,
                )

        value_bits = [[0] * (maximum_value + 1) for maximum_value in maximum_values]
        for group_index, group in enumerate(groups):
            group_bit = 1 << group_index
            for coordinate, value in enumerate(group.signature):
                value_bits[coordinate][value] |= group_bit

        all_groups_bits = (1 << len(groups)) - 1
        positive_bits: list[int] = []
        allowed_bits: list[tuple[int, ...]] = []
        for coordinate_values in value_bits:
            positive = 0
            cumulative = 0
            allowed_for_coordinate: list[int] = []
            for value, bits in enumerate(coordinate_values):
                cumulative |= bits
                allowed_for_coordinate.append(cumulative)
                if value > 0:
                    positive |= bits
            positive_bits.append(positive)
            allowed_bits.append(tuple(allowed_for_coordinate))

        return cls(
            signature_weight=signature_weight,
            all_groups_bits=all_groups_bits,
            positive_bits_by_coordinate=tuple(positive_bits),
            allowed_bits_by_coordinate=tuple(allowed_bits),
            value_bits_by_coordinate=tuple(tuple(bits) for bits in value_bits),
        )

    def compatible_bits(
        self,
        *,
        groups: Sequence[SignatureGroup],
        residual: Sequence[int],
        selected_counts: Sequence[tuple[int, int]],
    ) -> int:
        if len(residual) != len(self.allowed_bits_by_coordinate):
            raise BalancedDesignExecutionError("search_contract_invalid")
        compatible = self.all_groups_bits
        for available, allowed in zip(
            residual,
            self.allowed_bits_by_coordinate,
        ):
            if available < 0:
                return 0
            if available < len(allowed) - 1:
                compatible &= allowed[available]
            if not compatible:
                return 0
        for group_index, count in selected_counts:
            if count >= groups[group_index].multiplicity:
                compatible &= ~(1 << group_index)
        return compatible

    def maximum_value(self, *, coordinate: int, compatible_bits: int) -> int:
        for value in range(
            len(self.value_bits_by_coordinate[coordinate]) - 1,
            -1,
            -1,
        ):
            if compatible_bits & self.value_bits_by_coordinate[coordinate][value]:
                return value
        return 0


@dataclass(frozen=True)
class OrbitInventory:
    point_count: int
    block_size: int
    legal_block_count: int
    canonical_candidates_visited: int
    full_representatives: tuple[OrbitRepresentative, ...]
    short_representatives: tuple[OrbitRepresentative, ...]
    signature_groups: tuple[SignatureGroup, ...]

    @property
    def legal_block_ids_accounted(self) -> int:
        return sum(
            item.orbit_size
            for item in (*self.full_representatives, *self.short_representatives)
        )

    def to_artifact(self) -> dict[str, Any]:
        body = {
            "schema_version": "dehps-prediction-v2-balanced-design-orbit-inventory.v1",
            "artifact_type": "PredictionV2BalancedDesignOrbitInventoryArtifact",
            "status": "COMPLETE",
            "constructor_family": CONSTRUCTOR_FAMILY,
            "point_count": self.point_count,
            "block_size": self.block_size,
            "legal_block_count": self.legal_block_count,
            "canonical_candidates_visited": self.canonical_candidates_visited,
            "legal_block_ids_accounted": self.legal_block_ids_accounted,
            "full_orbit_count": len(self.full_representatives),
            "short_orbit_count": len(self.short_representatives),
            "full_representatives": [
                item.to_dict() for item in self.full_representatives
            ],
            "short_representatives": [
                item.to_dict() for item in self.short_representatives
            ],
            "signature_groups": [item.to_dict() for item in self.signature_groups],
            "signature_group_count": len(self.signature_groups),
            "repetition_scan": REPETITION_SCAN,
            "separate_duplicate_membership_or_uniqueness_scan": False,
        }
        return _artifact(body, domain=_INVENTORY_DOMAIN)


@dataclass(frozen=True)
class SearchFrameSnapshot:
    residual: tuple[int, ...]
    remaining: int
    selected_counts: tuple[tuple[int, int], ...]
    coordinate: int
    next_allocation_index: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "residual": list(self.residual),
            "remaining": self.remaining,
            "selected_counts": [list(item) for item in self.selected_counts],
            "coordinate": self.coordinate,
            "next_allocation_index": self.next_allocation_index,
        }


@dataclass
class _RuntimeFrame:
    snapshot: SearchFrameSnapshot
    allocations: Iterator[tuple[tuple[int, int], ...]]


@dataclass(frozen=True)
class MulticoverSearchResult:
    outcome: str
    profile: tuple[int, int] | None
    short_subset_indices: tuple[int, ...]
    selected_full_representative_ids: tuple[int, ...]
    selected_short_representative_ids: tuple[int, ...]
    node_expansions: int
    completed_branch_count: int
    total_branch_count: int
    search_exhausted: bool
    transcript_digest: str
    checkpoint_count: int
    terminal_checkpoint_digest: str

    @property
    def found(self) -> bool:
        return self.outcome == POSITIVE_OUTCOME


@dataclass(frozen=True)
class CertificateVerification:
    certificate_digest: str
    decoded_block_ids: tuple[int, ...]
    point_counts: tuple[int, ...]
    pair_counts: tuple[int, ...]


@dataclass(frozen=True)
class BalancedDesignExecutionRun:
    inventory: Mapping[str, Any]
    result: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return self.inventory, self.result, self.completion


def lexicographic_combination_rank(
    block: Sequence[int],
    *,
    point_count: int,
    block_size: int,
) -> int:
    canonical = tuple(int(value) for value in block)
    if (
        len(canonical) != block_size
        or tuple(sorted(canonical)) != canonical
        or canonical[0] < 0
        or canonical[-1] >= point_count
        or any(left == right for left, right in pairwise(canonical))
    ):
        raise BalancedDesignExecutionError("combination_rank_input_invalid")
    rank = 0
    lower = 0
    for position, value in enumerate(canonical):
        remaining = block_size - position - 1
        for candidate in range(lower, value):
            rank += comb(point_count - candidate - 1, remaining)
        lower = value + 1
    if rank < 0 or rank >= comb(point_count, block_size):
        raise BalancedDesignExecutionError("combination_rank_out_of_range")
    return rank


def lexicographic_combination_unrank(
    rank: int,
    *,
    point_count: int,
    block_size: int,
) -> tuple[int, ...]:
    remaining_rank = int(rank)
    if remaining_rank < 0 or remaining_rank >= comb(point_count, block_size):
        raise BalancedDesignExecutionError("combination_unrank_out_of_range")
    values: list[int] = []
    lower = 0
    for position in range(block_size):
        remaining = block_size - position - 1
        upper = point_count - remaining
        for candidate in range(lower, upper):
            width = comb(point_count - candidate - 1, remaining)
            if remaining_rank < width:
                values.append(candidate)
                lower = candidate + 1
                break
            remaining_rank -= width
        else:
            raise BalancedDesignExecutionError("combination_unrank_failed")
    return tuple(values)


def translate_block(
    block: Sequence[int],
    shift: int,
    *,
    point_count: int,
) -> tuple[int, ...]:
    return tuple(sorted((int(value) + shift) % point_count for value in block))


def canonical_translation_representative(
    block: Sequence[int],
    *,
    point_count: int,
) -> tuple[int, ...]:
    canonical = tuple(sorted(int(value) for value in block))
    if any(left == right for left, right in pairwise(canonical)):
        raise BalancedDesignExecutionError("orbit_block_invalid")
    # A lexicographically minimum translate starts at zero, so exactly the
    # translations that move a selected point to zero need to be compared.
    return min(
        translate_block(canonical, -origin, point_count=point_count)
        for origin in canonical
    )


def translation_orbit_size(
    block: Sequence[int],
    *,
    point_count: int,
) -> tuple[int, int]:
    canonical = tuple(sorted(int(value) for value in block))
    stabilizer_size = sum(
        translate_block(canonical, shift, point_count=point_count) == canonical
        for shift in range(point_count)
    )
    if stabilizer_size <= 0 or point_count % stabilizer_size:
        raise BalancedDesignExecutionError("orbit_stabilizer_invalid")
    return point_count // stabilizer_size, stabilizer_size


def circular_distance_signature(
    block: Sequence[int],
    *,
    point_count: int,
) -> tuple[int, ...]:
    if point_count % 2 == 0:
        raise BalancedDesignExecutionError("odd_point_count_required")
    counts = [0] * (point_count // 2)
    canonical = tuple(sorted(int(value) for value in block))
    for left_index, left in enumerate(canonical):
        for right in canonical[left_index + 1 :]:
            difference = (right - left) % point_count
            distance = min(difference, point_count - difference)
            counts[distance - 1] += 1
    return tuple(counts)


def compile_translation_orbit_inventory(
    *,
    point_count: int = POINT_COUNT,
    block_size: int = BLOCK_SIZE,
    require_formal_identity: bool = True,
) -> OrbitInventory:
    if point_count < block_size or block_size < 2 or point_count % 2 == 0:
        raise BalancedDesignExecutionError("orbit_inventory_parameters_invalid")
    full: list[OrbitRepresentative] = []
    short: list[OrbitRepresentative] = []
    for tail in combinations(range(1, point_count), block_size - 1):
        block = (0, *tail)
        if (
            canonical_translation_representative(
                block,
                point_count=point_count,
            )
            != block
        ):
            continue
        orbit_size, stabilizer_size = translation_orbit_size(
            block,
            point_count=point_count,
        )
        raw_signature = circular_distance_signature(
            block,
            point_count=point_count,
        )
        if any(value % stabilizer_size for value in raw_signature):
            raise BalancedDesignExecutionError("orbit_signature_not_integral")
        signature = tuple(value // stabilizer_size for value in raw_signature)
        representative = OrbitRepresentative(
            representative_id=lexicographic_combination_rank(
                block,
                point_count=point_count,
                block_size=block_size,
            ),
            block=block,
            orbit_size=orbit_size,
            stabilizer_size=stabilizer_size,
            signature=signature,
        )
        if stabilizer_size == 1:
            full.append(representative)
        else:
            short.append(representative)
    full.sort(key=lambda item: item.representative_id)
    short.sort(key=lambda item: item.representative_id)
    grouped: dict[tuple[int, ...], list[int]] = {}
    for item in full:
        grouped.setdefault(item.signature, []).append(item.representative_id)
    signature_groups = tuple(
        SignatureGroup(signature=signature, representative_ids=tuple(ids))
        for signature, ids in sorted(
            grouped.items(),
            key=lambda item: (item[0], item[1][0]),
        )
    )
    inventory = OrbitInventory(
        point_count=point_count,
        block_size=block_size,
        legal_block_count=comb(point_count, block_size),
        canonical_candidates_visited=comb(point_count - 1, block_size - 1),
        full_representatives=tuple(full),
        short_representatives=tuple(short),
        signature_groups=signature_groups,
    )
    if require_formal_identity:
        _require_formal_inventory(inventory)
    return inventory


def _require_formal_inventory(inventory: OrbitInventory) -> None:
    subgroup = (0, 11, 22)
    expected_short = tuple(
        canonical_translation_representative(
            (*subgroup, distance, distance + 11, distance + 22),
            point_count=POINT_COUNT,
        )
        for distance in range(1, 6)
    )
    if (
        inventory.point_count != POINT_COUNT
        or inventory.block_size != BLOCK_SIZE
        or inventory.legal_block_count != LEGAL_BLOCK_COUNT
        or inventory.canonical_candidates_visited != CANONICAL_CANDIDATE_COUNT
        or len(inventory.full_representatives) != FULL_ORBIT_COUNT
        or len(inventory.short_representatives) != SHORT_ORBIT_COUNT
        or inventory.legal_block_ids_accounted != LEGAL_BLOCK_COUNT
        or tuple(item.block for item in inventory.short_representatives)
        != tuple(sorted(expected_short))
        or any(
            item.orbit_size != FULL_ORBIT_SIZE
            for item in inventory.full_representatives
        )
        or any(
            item.orbit_size != SHORT_ORBIT_SIZE
            for item in inventory.short_representatives
        )
        or any(
            sum(item.signature) != SIGNATURE_WEIGHT
            for item in inventory.full_representatives
        )
        or any(
            sum(item.signature) != BLOCK_SIZE - 1
            for item in inventory.short_representatives
        )
    ):
        raise BalancedDesignExecutionError("formal_orbit_inventory_identity_changed")


def _selected_count(
    selected_counts: Sequence[tuple[int, int]],
    group_index: int,
) -> int:
    for index, count in selected_counts:
        if index == group_index:
            return count
    return 0


def _choose_branch_coordinate(
    *,
    groups: Sequence[SignatureGroup],
    residual: Sequence[int],
    selected_counts: Sequence[tuple[int, int]],
    compatibility_index: _SignatureCompatibilityIndex | None = None,
    compatible_bits: int | None = None,
) -> int:
    index = compatibility_index or _SignatureCompatibilityIndex.build(groups)
    if compatible_bits is None:
        compatible_bits = index.compatible_bits(
            groups=groups,
            residual=residual,
            selected_counts=selected_counts,
        )
    choices: list[tuple[int, int]] = []
    for coordinate, need in enumerate(residual):
        if need <= 0:
            continue
        compatible = (
            compatible_bits & index.positive_bits_by_coordinate[coordinate]
        ).bit_count()
        choices.append((compatible, coordinate))
    if not choices:
        return -1
    compatible, coordinate = min(choices)
    return coordinate if compatible else -1


def _coordinate_allocations(
    *,
    groups: Sequence[SignatureGroup],
    residual: tuple[int, ...],
    remaining: int,
    selected_counts: tuple[tuple[int, int], ...],
    coordinate: int,
    compatibility_index: _SignatureCompatibilityIndex | None = None,
    compatible_bits: int | None = None,
) -> Iterator[tuple[tuple[int, int], ...]]:
    index = compatibility_index or _SignatureCompatibilityIndex.build(groups)
    if compatible_bits is None:
        compatible_bits = index.compatible_bits(
            groups=groups,
            residual=residual,
            selected_counts=selected_counts,
        )
    selected_by_group = dict(selected_counts)

    def walk(
        minimum_group_index: int,
        coordinate_need: int,
        slots: int,
        contribution: tuple[int, ...],
        allocation: tuple[tuple[int, int], ...],
    ) -> Iterator[tuple[tuple[int, int], ...]]:
        if coordinate_need == 0:
            yield allocation
            return
        if slots <= 0:
            return
        remaining_capacity = tuple(
            available - current for available, current in zip(residual, contribution)
        )
        candidate_bits = (
            index.compatible_bits(
                groups=groups,
                residual=remaining_capacity,
                selected_counts=selected_counts,
            )
            & compatible_bits
            & index.positive_bits_by_coordinate[coordinate]
            & ~((1 << minimum_group_index) - 1)
        )
        while candidate_bits:
            least_bit = candidate_bits & -candidate_bits
            group_index = least_bit.bit_length() - 1
            candidate_bits ^= least_bit
            group = groups[group_index]
            available_count = group.multiplicity - selected_by_group.get(
                group_index,
                0,
            )
            maximum = min(
                available_count,
                slots,
                coordinate_need // group.signature[coordinate],
                *(
                    available // value
                    for available, value in zip(
                        remaining_capacity,
                        group.signature,
                    )
                    if value > 0
                ),
            )
            for count in range(1, maximum + 1):
                next_contribution = tuple(
                    current + count * value
                    for current, value in zip(contribution, group.signature)
                )
                yield from walk(
                    group_index + 1,
                    coordinate_need - count * group.signature[coordinate],
                    slots - count,
                    next_contribution,
                    (*allocation, (group_index, count)),
                )

    yield from walk(
        0,
        residual[coordinate],
        remaining,
        (0,) * len(residual),
        (),
    )


def _merge_selected_counts(
    selected: Sequence[tuple[int, int]],
    allocation: Sequence[tuple[int, int]],
) -> tuple[tuple[int, int], ...]:
    merged = dict(selected)
    for index, count in allocation:
        merged[index] = merged.get(index, 0) + count
    return tuple(sorted(merged.items()))


def _allocation_contribution(
    groups: Sequence[SignatureGroup],
    allocation: Sequence[tuple[int, int]],
) -> tuple[int, ...]:
    width = len(groups[0].signature)
    result = [0] * width
    for group_index, count in allocation:
        for coordinate, value in enumerate(groups[group_index].signature):
            result[coordinate] += count * value
    return tuple(result)


def _make_frame(
    *,
    groups: Sequence[SignatureGroup],
    residual: tuple[int, ...],
    remaining: int,
    selected_counts: tuple[tuple[int, int], ...],
    next_allocation_index: int = 0,
    compatibility_index: _SignatureCompatibilityIndex | None = None,
) -> _RuntimeFrame | None:
    index = compatibility_index or _SignatureCompatibilityIndex.build(groups)
    signature_weight = index.signature_weight
    if remaining <= 0 or sum(residual) != remaining * signature_weight:
        return None
    compatible_bits = index.compatible_bits(
        groups=groups,
        residual=residual,
        selected_counts=selected_counts,
    )
    coordinate = _choose_branch_coordinate(
        groups=groups,
        residual=residual,
        selected_counts=selected_counts,
        compatibility_index=index,
        compatible_bits=compatible_bits,
    )
    if coordinate < 0:
        return None
    for coordinate_index, need in enumerate(residual):
        maximum = index.maximum_value(
            coordinate=coordinate_index,
            compatible_bits=compatible_bits,
        )
        if need > remaining * maximum:
            return None
    snapshot = SearchFrameSnapshot(
        residual=residual,
        remaining=remaining,
        selected_counts=selected_counts,
        coordinate=coordinate,
        next_allocation_index=next_allocation_index,
    )
    allocations = _coordinate_allocations(
        groups=groups,
        residual=residual,
        remaining=remaining,
        selected_counts=selected_counts,
        coordinate=coordinate,
        compatibility_index=index,
        compatible_bits=compatible_bits,
    )
    for _ in range(next_allocation_index):
        try:
            next(allocations)
        except StopIteration:
            return None
    return _RuntimeFrame(snapshot=snapshot, allocations=allocations)


class CheckpointJournal:
    def __init__(
        self,
        path: Path,
        *,
        source_contract_digest: str,
        preregistration_digest: str,
        execution_id: str,
    ) -> None:
        self.path = path
        self.source_contract_digest = source_contract_digest
        self.preregistration_digest = preregistration_digest
        self.execution_id = execution_id
        self._last_digest = "0" * 64
        self._count = 0
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def count(self) -> int:
        return self._count

    @property
    def latest_digest(self) -> str:
        return self._last_digest

    def load_latest(self) -> dict[str, Any] | None:
        if not self.path.is_file():
            return None
        previous = "0" * 64
        latest: dict[str, Any] | None = None
        count = 0
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                for raw in handle:
                    payload = json.loads(raw)
                    supplied = str(payload.get("checkpoint_digest") or "")
                    identity = dict(payload)
                    identity.pop("checkpoint_digest", None)
                    if (
                        payload.get("previous_checkpoint_digest") != previous
                        or supplied
                        != canonical_digest(identity, domain=_CHECKPOINT_DOMAIN)
                        or payload.get("source_contract_digest")
                        != self.source_contract_digest
                        or payload.get("preregistration_digest")
                        != self.preregistration_digest
                        or payload.get("execution_id") != self.execution_id
                    ):
                        raise BalancedDesignExecutionError(
                            "checkpoint_identity_changed"
                        )
                    previous = supplied
                    latest = payload
                    count += 1
        except (OSError, json.JSONDecodeError) as exc:
            raise BalancedDesignExecutionError("checkpoint_journal_invalid") from exc
        self._last_digest = previous
        self._count = count
        return latest

    def append(self, state: Mapping[str, Any]) -> dict[str, Any]:
        body = {
            "schema_version": "dehps-prediction-v2-balanced-design-checkpoint.v1",
            "source_contract_digest": self.source_contract_digest,
            "preregistration_digest": self.preregistration_digest,
            "execution_id": self.execution_id,
            "previous_checkpoint_digest": self._last_digest,
            **dict(state),
        }
        payload = {
            **body,
            "checkpoint_digest": canonical_digest(body, domain=_CHECKPOINT_DOMAIN),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._last_digest = payload["checkpoint_digest"]
        self._count += 1
        return payload


def _profile_branches(
    short_representatives: Sequence[OrbitRepresentative],
    profiles: Sequence[tuple[int, int]],
) -> tuple[tuple[tuple[int, int], tuple[int, ...]], ...]:
    return tuple(
        (profile, subset)
        for profile in profiles
        for subset in combinations(range(len(short_representatives)), profile[1])
    )


def search_exact_signature_multicover(
    *,
    inventory: OrbitInventory,
    source_contract_digest: str,
    preregistration_digest: str,
    execution_id: str,
    checkpoint_path: Path,
    target_signature: tuple[int, ...] = TARGET_SIGNATURE,
    profiles: Sequence[tuple[int, int]] = PROFILE_ORDER,
    node_budget: int = MAXIMUM_MULTICOVER_NODE_EXPANSIONS,
    checkpoint_interval: int = CHECKPOINT_INTERVAL_NODE_EXPANSIONS,
) -> MulticoverSearchResult:
    if (
        node_budget <= 0
        or checkpoint_interval <= 0
        or len(target_signature) != len(inventory.signature_groups[0].signature)
    ):
        raise BalancedDesignExecutionError("search_contract_invalid")
    compatibility_index = _SignatureCompatibilityIndex.build(inventory.signature_groups)
    branches = _profile_branches(inventory.short_representatives, profiles)
    journal = CheckpointJournal(
        checkpoint_path,
        source_contract_digest=source_contract_digest,
        preregistration_digest=preregistration_digest,
        execution_id=execution_id,
    )
    latest = journal.load_latest()
    node_count = 0
    branch_index = 0
    transcript_digest = "0" * 64
    stack: list[_RuntimeFrame] = []
    if latest is not None:
        node_count = int(latest["node_expansions"])
        branch_index = int(latest["branch_index"])
        transcript_digest = str(latest["transcript_digest"])
        raw_stack = latest.get("branch_stack")
        if not isinstance(raw_stack, list):
            raise BalancedDesignExecutionError("checkpoint_stack_invalid")
        for raw in raw_stack:
            snapshot = SearchFrameSnapshot(
                residual=tuple(int(value) for value in raw["residual"]),
                remaining=int(raw["remaining"]),
                selected_counts=tuple(
                    (int(index), int(count)) for index, count in raw["selected_counts"]
                ),
                coordinate=int(raw["coordinate"]),
                next_allocation_index=int(raw["next_allocation_index"]),
            )
            frame = _make_frame(
                groups=inventory.signature_groups,
                residual=snapshot.residual,
                remaining=snapshot.remaining,
                selected_counts=snapshot.selected_counts,
                next_allocation_index=snapshot.next_allocation_index,
                compatibility_index=compatibility_index,
            )
            if frame is None or frame.snapshot.coordinate != snapshot.coordinate:
                raise BalancedDesignExecutionError("checkpoint_stack_changed")
            stack.append(frame)
    next_checkpoint = ((node_count // checkpoint_interval) + 1) * checkpoint_interval

    def checkpoint() -> None:
        journal.append(
            {
                "branch_index": branch_index,
                "completed_branch_count": branch_index,
                "node_expansions": node_count,
                "transcript_digest": transcript_digest,
                "branch_stack": [frame.snapshot.to_dict() for frame in stack],
                "repetition_scan": REPETITION_SCAN,
            }
        )

    while branch_index < len(branches):
        profile, short_subset = branches[branch_index]
        if not stack:
            residual = list(target_signature)
            for short_index in short_subset:
                for coordinate, value in enumerate(
                    inventory.short_representatives[short_index].signature
                ):
                    residual[coordinate] -= value
            if any(value < 0 for value in residual):
                branch_index += 1
                checkpoint()
                continue
            root = _make_frame(
                groups=inventory.signature_groups,
                residual=tuple(residual),
                remaining=profile[0],
                selected_counts=(),
                compatibility_index=compatibility_index,
            )
            if root is None:
                branch_index += 1
                checkpoint()
                continue
            stack.append(root)
        while stack:
            if node_count >= node_budget:
                checkpoint()
                return MulticoverSearchResult(
                    outcome=BOUNDED_NEGATIVE_OUTCOME,
                    profile=None,
                    short_subset_indices=(),
                    selected_full_representative_ids=(),
                    selected_short_representative_ids=(),
                    node_expansions=node_count,
                    completed_branch_count=branch_index,
                    total_branch_count=len(branches),
                    search_exhausted=False,
                    transcript_digest=transcript_digest,
                    checkpoint_count=journal.count,
                    terminal_checkpoint_digest=journal.latest_digest,
                )
            frame = stack[-1]
            try:
                allocation = next(frame.allocations)
            except StopIteration:
                stack.pop()
                continue
            frame.snapshot = SearchFrameSnapshot(
                residual=frame.snapshot.residual,
                remaining=frame.snapshot.remaining,
                selected_counts=frame.snapshot.selected_counts,
                coordinate=frame.snapshot.coordinate,
                next_allocation_index=frame.snapshot.next_allocation_index + 1,
            )
            node_count += 1
            contribution = _allocation_contribution(
                inventory.signature_groups,
                allocation,
            )
            residual = tuple(
                available - used
                for available, used in zip(frame.snapshot.residual, contribution)
            )
            selected = _merge_selected_counts(
                frame.snapshot.selected_counts,
                allocation,
            )
            remaining = frame.snapshot.remaining - sum(count for _, count in allocation)
            transcript_digest = canonical_digest(
                {
                    "previous": transcript_digest,
                    "node_expansion": node_count,
                    "branch_index": branch_index,
                    "profile": list(profile),
                    "short_subset": list(short_subset),
                    "allocation": [list(item) for item in allocation],
                    "residual": list(residual),
                    "remaining": remaining,
                },
                domain=_TRANSCRIPT_DOMAIN,
            )
            if remaining == 0 and not any(residual):
                full_ids = sorted(
                    representative_id
                    for group_index, count in selected
                    for representative_id in inventory.signature_groups[
                        group_index
                    ].representative_ids[:count]
                )
                short_ids = sorted(
                    inventory.short_representatives[index].representative_id
                    for index in short_subset
                )
                checkpoint()
                return MulticoverSearchResult(
                    outcome=POSITIVE_OUTCOME,
                    profile=profile,
                    short_subset_indices=short_subset,
                    selected_full_representative_ids=tuple(full_ids),
                    selected_short_representative_ids=tuple(short_ids),
                    node_expansions=node_count,
                    completed_branch_count=branch_index,
                    total_branch_count=len(branches),
                    search_exhausted=False,
                    transcript_digest=transcript_digest,
                    checkpoint_count=journal.count,
                    terminal_checkpoint_digest=journal.latest_digest,
                )
            child = _make_frame(
                groups=inventory.signature_groups,
                residual=residual,
                remaining=remaining,
                selected_counts=selected,
                compatibility_index=compatibility_index,
            )
            if child is not None:
                stack.append(child)
            if node_count >= next_checkpoint:
                checkpoint()
                next_checkpoint += checkpoint_interval
        branch_index += 1
        checkpoint()
    return MulticoverSearchResult(
        outcome=BOUNDED_NEGATIVE_OUTCOME,
        profile=None,
        short_subset_indices=(),
        selected_full_representative_ids=(),
        selected_short_representative_ids=(),
        node_expansions=node_count,
        completed_branch_count=len(branches),
        total_branch_count=len(branches),
        search_exhausted=True,
        transcript_digest=transcript_digest,
        checkpoint_count=journal.count,
        terminal_checkpoint_digest=journal.latest_digest,
    )


def _expand_orbit(
    representative: OrbitRepresentative,
    *,
    point_count: int,
) -> Iterator[tuple[int, ...]]:
    for shift in range(representative.orbit_size):
        yield translate_block(
            representative.block,
            shift,
            point_count=point_count,
        )


def build_positive_certificate(
    *,
    inventory: OrbitInventory,
    result: MulticoverSearchResult,
) -> dict[str, Any]:
    if not result.found or result.profile is None:
        raise BalancedDesignExecutionError("positive_result_required")
    by_id = {
        item.representative_id: item
        for item in (
            *inventory.full_representatives,
            *inventory.short_representatives,
        )
    }
    selected_ids = (
        *result.selected_full_representative_ids,
        *result.selected_short_representative_ids,
    )
    block_ids = sorted(
        lexicographic_combination_rank(
            block,
            point_count=inventory.point_count,
            block_size=inventory.block_size,
        )
        for representative_id in selected_ids
        for block in _expand_orbit(
            by_id[representative_id],
            point_count=inventory.point_count,
        )
    )
    expected_block_count = sum(by_id[value].orbit_size for value in selected_ids)
    if expected_block_count != len(block_ids):
        raise BalancedDesignExecutionError("certificate_orbit_expansion_invalid")
    gaps = [current - previous - 1 for previous, current in pairwise(block_ids)]
    if any(value < 0 for value in gaps):
        raise BalancedDesignExecutionError("certificate_gap_encoding_invalid")
    body = {
        "schema_version": "dehps-prediction-v2-balanced-design-certificate.v1",
        "artifact_type": "PredictionV2BalancedDesignCertificateArtifact",
        "status": "COMPLETE",
        "outcome": POSITIVE_OUTCOME,
        "profile": list(result.profile),
        "selected_full_orbit_representative_ids": list(
            result.selected_full_representative_ids
        ),
        "selected_short_orbit_representative_ids": list(
            result.selected_short_representative_ids
        ),
        "block_count": len(block_ids),
        "first_combination_id": block_ids[0],
        "gap_minus_one": gaps,
        "encoding": "FIRST_COMBINADIC_ID_PLUS_175_GAP_MINUS_ONE_UNSIGNED_INTEGERS",
        "repetition_scan": REPETITION_SCAN,
        "separate_duplicate_membership_or_uniqueness_scan": False,
    }
    return _artifact(body, domain=_CERTIFICATE_DOMAIN)


def verify_positive_certificate(
    *,
    inventory: OrbitInventory,
    certificate: Mapping[str, Any],
    expected_block_count: int = BLOCK_COUNT,
    point_replication_target: int = POINT_REPLICATION_TARGET,
    pair_replication_target: int = PAIR_REPLICATION_TARGET,
) -> CertificateVerification:
    _verify_artifact(certificate, domain=_CERTIFICATE_DOMAIN)
    gaps = certificate.get("gap_minus_one")
    if (
        certificate.get("outcome") != POSITIVE_OUTCOME
        or certificate.get("encoding")
        != "FIRST_COMBINADIC_ID_PLUS_175_GAP_MINUS_ONE_UNSIGNED_INTEGERS"
        or certificate.get("repetition_scan") != REPETITION_SCAN
        or certificate.get("separate_duplicate_membership_or_uniqueness_scan")
        is not False
        or not isinstance(gaps, list)
        or len(gaps) != expected_block_count - 1
        or any(not isinstance(value, int) or value < 0 for value in gaps)
    ):
        raise BalancedDesignExecutionError("certificate_contract_invalid")
    block_ids = [int(certificate["first_combination_id"])]
    for gap in gaps:
        block_ids.append(block_ids[-1] + gap + 1)
    if block_ids[-1] >= comb(inventory.point_count, inventory.block_size):
        raise BalancedDesignExecutionError("certificate_block_id_out_of_range")
    full_ids = tuple(
        int(value) for value in certificate["selected_full_orbit_representative_ids"]
    )
    short_ids = tuple(
        int(value) for value in certificate["selected_short_orbit_representative_ids"]
    )
    by_id = {
        item.representative_id: item
        for item in (
            *inventory.full_representatives,
            *inventory.short_representatives,
        )
    }
    try:
        reconstructed_ids = sorted(
            lexicographic_combination_rank(
                block,
                point_count=inventory.point_count,
                block_size=inventory.block_size,
            )
            for representative_id in (*full_ids, *short_ids)
            for block in _expand_orbit(
                by_id[representative_id],
                point_count=inventory.point_count,
            )
        )
    except KeyError as exc:
        raise BalancedDesignExecutionError(
            "certificate_representative_invalid"
        ) from exc
    if reconstructed_ids != block_ids:
        raise BalancedDesignExecutionError("certificate_orbit_reconstruction_changed")
    point_counts = [0] * inventory.point_count
    pair_counts = [0] * comb(inventory.point_count, 2)
    for block_id in block_ids:
        block = lexicographic_combination_unrank(
            block_id,
            point_count=inventory.point_count,
            block_size=inventory.block_size,
        )
        for point in block:
            point_counts[point] += 1
        for left_position, left in enumerate(block):
            for right in block[left_position + 1 :]:
                pair_counts[_pair_rank(left, right, inventory.point_count)] += 1
    if any(value != point_replication_target for value in point_counts) or any(
        value != pair_replication_target for value in pair_counts
    ):
        raise BalancedDesignExecutionError("certificate_exact_counts_failed")
    return CertificateVerification(
        certificate_digest=str(certificate["artifact_digest"]),
        decoded_block_ids=tuple(block_ids),
        point_counts=tuple(point_counts),
        pair_counts=tuple(pair_counts),
    )


def _pair_rank(left: int, right: int, point_count: int) -> int:
    if not 0 <= left < right < point_count:
        raise BalancedDesignExecutionError("pair_rank_input_invalid")
    return left * (2 * point_count - left - 1) // 2 + (right - left - 1)


def build_search_result_artifact(
    *,
    inventory_artifact_digest: str,
    result: MulticoverSearchResult,
    certificate: Mapping[str, Any] | None,
    peak_resident_bytes: int,
) -> dict[str, Any]:
    if result.found != (certificate is not None):
        raise BalancedDesignExecutionError("search_result_certificate_mismatch")
    body = {
        "schema_version": "dehps-prediction-v2-balanced-design-search-result.v1",
        "artifact_type": "PredictionV2BalancedDesignSearchResultArtifact",
        "status": "COMPLETE",
        "outcome": result.outcome,
        "profile": None if result.profile is None else list(result.profile),
        "selected_full_orbit_representative_ids": list(
            result.selected_full_representative_ids
        ),
        "selected_short_orbit_representative_ids": list(
            result.selected_short_representative_ids
        ),
        "node_expansions": result.node_expansions,
        "completed_branch_count": result.completed_branch_count,
        "total_branch_count": result.total_branch_count,
        "search_exhausted": result.search_exhausted,
        "transcript_digest": result.transcript_digest,
        "checkpoint_count": result.checkpoint_count,
        "terminal_checkpoint_digest": result.terminal_checkpoint_digest,
        "inventory_artifact_digest": inventory_artifact_digest,
        "certificate_artifact_digest": (
            None if certificate is None else certificate["artifact_digest"]
        ),
        "certificate": None if certificate is None else dict(certificate),
        "peak_resident_bytes": peak_resident_bytes,
        "maximum_resident_bytes": MAXIMUM_RESIDENT_BYTES,
        "bounded_negative_is_global_nonexistence": False,
        "cyclic_subspace_exhaustion_is_global_nonexistence": False,
        "repetition_scan": REPETITION_SCAN,
        "separate_duplicate_membership_or_uniqueness_scan": False,
        "evidence_created": False,
        "new_model_created": False,
        "production_action": "none",
    }
    return _artifact(body, domain=_RESULT_DOMAIN)


def build_balanced_design_execution_artifacts(
    *,
    source_contract: Mapping[str, Any],
    preregistration: Mapping[str, Any],
    execution_handoff: Mapping[str, Any],
    preregistration_completion: Mapping[str, Any],
    preregistration_mainline_execution: Mapping[str, Any],
    execution_id: str,
    checkpoint_path: Path,
    inventory: OrbitInventory | None = None,
    target_signature: tuple[int, ...] = TARGET_SIGNATURE,
    profiles: Sequence[tuple[int, int]] = PROFILE_ORDER,
    node_budget: int = MAXIMUM_MULTICOVER_NODE_EXPANSIONS,
    checkpoint_interval: int = CHECKPOINT_INTERVAL_NODE_EXPANSIONS,
    require_formal_identity: bool = True,
    require_registered_identities: bool = True,
) -> BalancedDesignExecutionRun:
    _validate_parent_artifacts(
        preregistration=preregistration,
        execution_handoff=execution_handoff,
        preregistration_completion=preregistration_completion,
        preregistration_mainline_execution=preregistration_mainline_execution,
        require_registered_identities=require_registered_identities,
    )
    compiled = inventory or compile_translation_orbit_inventory(
        require_formal_identity=require_formal_identity,
    )
    if peak_resident_bytes() > MAXIMUM_RESIDENT_BYTES:
        raise BalancedDesignExecutionError("resident_memory_budget_exceeded")
    inventory_artifact = compiled.to_artifact()
    result = search_exact_signature_multicover(
        inventory=compiled,
        source_contract_digest=str(source_contract["artifact_digest"]),
        preregistration_digest=str(preregistration["artifact_digest"]),
        execution_id=execution_id,
        checkpoint_path=checkpoint_path,
        target_signature=target_signature,
        profiles=profiles,
        node_budget=node_budget,
        checkpoint_interval=checkpoint_interval,
    )
    certificate = (
        build_positive_certificate(inventory=compiled, result=result)
        if result.found
        else None
    )
    if certificate is not None:
        verify_positive_certificate(
            inventory=compiled,
            certificate=certificate,
            expected_block_count=(
                BLOCK_COUNT if require_formal_identity else compiled.point_count
            ),
            point_replication_target=(
                POINT_REPLICATION_TARGET
                if require_formal_identity
                else compiled.block_size
            ),
            pair_replication_target=(
                PAIR_REPLICATION_TARGET if require_formal_identity else 1
            ),
        )
    resident_bytes = peak_resident_bytes()
    if resident_bytes > MAXIMUM_RESIDENT_BYTES:
        raise BalancedDesignExecutionError("resident_memory_budget_exceeded")
    result_artifact = build_search_result_artifact(
        inventory_artifact_digest=str(inventory_artifact["artifact_digest"]),
        result=result,
        certificate=certificate,
        peak_resident_bytes=resident_bytes,
    )
    completion = _artifact(
        {
            "schema_version": (
                "dehps-prediction-v2-balanced-design-execution-completion.v1"
            ),
            "artifact_type": (
                "prediction_v2_balanced_design_feasibility_execution_completion"
            ),
            "status": "COMPLETE",
            "completion_fact": (
                PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_COMPLETION_FACT
            ),
            "source_contract_digest": source_contract["artifact_digest"],
            "preregistration_digest": preregistration["artifact_digest"],
            "execution_handoff_digest": execution_handoff["artifact_digest"],
            "preregistration_completion_digest": preregistration_completion[
                "artifact_digest"
            ],
            "preregistration_mainline_execution_digest": (
                preregistration_mainline_execution["artifact_digest"]
            ),
            "inventory_artifact_digest": inventory_artifact["artifact_digest"],
            "result_artifact_digest": result_artifact["artifact_digest"],
            "outcome": result.outcome,
            "existence_established_in_cyclic_scope": result.found,
            "global_nonexistence_established": False,
            "node_expansions": result.node_expansions,
            "completed_branch_count": result.completed_branch_count,
            "total_branch_count": result.total_branch_count,
            "search_exhausted": result.search_exhausted,
            "checkpoint_count": result.checkpoint_count,
            "terminal_checkpoint_digest": result.terminal_checkpoint_digest,
            "legal_block_ids_accounted": compiled.legal_block_ids_accounted,
            "canonical_candidates_visited": compiled.canonical_candidates_visited,
            "full_orbit_count": len(compiled.full_representatives),
            "short_orbit_count": len(compiled.short_representatives),
            "repetition_scan": REPETITION_SCAN,
            "separate_duplicate_membership_or_uniqueness_scan": False,
            "registered_child_count": 3,
            "evidence_created": False,
            "new_model_created": False,
            "candidate_expert_authorized": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "legacy_route_fallback": False,
            "next_consumer": (
                PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_TASK_KEY
            ),
            "production_action": "none",
            "parent_digests": [
                source_contract["artifact_digest"],
                preregistration["artifact_digest"],
                execution_handoff["artifact_digest"],
                preregistration_completion["artifact_digest"],
                preregistration_mainline_execution["artifact_digest"],
                inventory_artifact["artifact_digest"],
                result_artifact["artifact_digest"],
            ],
        },
        domain=_COMPLETION_DOMAIN,
    )
    return BalancedDesignExecutionRun(
        inventory=inventory_artifact,
        result=result_artifact,
        completion=completion,
    )


def replay_balanced_design_execution(
    *,
    source_contract: Mapping[str, Any],
    preregistration: Mapping[str, Any],
    execution_handoff: Mapping[str, Any],
    preregistration_completion: Mapping[str, Any],
    preregistration_mainline_execution: Mapping[str, Any],
    inventory_artifact: Mapping[str, Any],
    result_artifact: Mapping[str, Any],
    completion_artifact: Mapping[str, Any],
    execution_id: str,
    checkpoint_path: Path,
    require_formal_identity: bool = True,
    require_registered_identities: bool = True,
) -> dict[str, Any]:
    _validate_parent_artifacts(
        preregistration=preregistration,
        execution_handoff=execution_handoff,
        preregistration_completion=preregistration_completion,
        preregistration_mainline_execution=preregistration_mainline_execution,
        require_registered_identities=require_registered_identities,
    )
    inventory = orbit_inventory_from_artifact(
        inventory_artifact,
        require_formal_identity=require_formal_identity,
    )
    _verify_artifact(result_artifact, domain=_RESULT_DOMAIN)
    _verify_artifact(completion_artifact, domain=_COMPLETION_DOMAIN)
    journal = CheckpointJournal(
        checkpoint_path,
        source_contract_digest=str(source_contract["artifact_digest"]),
        preregistration_digest=str(preregistration["artifact_digest"]),
        execution_id=execution_id,
    )
    terminal_checkpoint = journal.load_latest()
    if (
        terminal_checkpoint is None
        or terminal_checkpoint.get("checkpoint_digest")
        != result_artifact.get("terminal_checkpoint_digest")
        or terminal_checkpoint.get("node_expansions")
        != result_artifact.get("node_expansions")
        or terminal_checkpoint.get("completed_branch_count")
        != result_artifact.get("completed_branch_count")
        or terminal_checkpoint.get("transcript_digest")
        != result_artifact.get("transcript_digest")
        or journal.count != result_artifact.get("checkpoint_count")
    ):
        raise BalancedDesignExecutionError("terminal_checkpoint_proof_changed")
    certificate = result_artifact.get("certificate")
    found = result_artifact.get("outcome") == POSITIVE_OUTCOME
    if found != isinstance(certificate, dict):
        raise BalancedDesignExecutionError("registered_result_certificate_changed")
    if certificate is not None:
        verification = verify_positive_certificate(
            inventory=inventory,
            certificate=certificate,
            expected_block_count=(
                BLOCK_COUNT if require_formal_identity else inventory.point_count
            ),
            point_replication_target=(
                POINT_REPLICATION_TARGET
                if require_formal_identity
                else inventory.block_size
            ),
            pair_replication_target=(
                PAIR_REPLICATION_TARGET if require_formal_identity else 1
            ),
        )
        if result_artifact.get("certificate_artifact_digest") != (
            verification.certificate_digest
        ):
            raise BalancedDesignExecutionError("registered_certificate_digest_changed")
    if (
        result_artifact.get("inventory_artifact_digest")
        != inventory_artifact.get("artifact_digest")
        or completion_artifact.get("source_contract_digest")
        != source_contract.get("artifact_digest")
        or completion_artifact.get("preregistration_digest")
        != preregistration.get("artifact_digest")
        or completion_artifact.get("execution_handoff_digest")
        != execution_handoff.get("artifact_digest")
        or completion_artifact.get("preregistration_completion_digest")
        != preregistration_completion.get("artifact_digest")
        or completion_artifact.get("preregistration_mainline_execution_digest")
        != preregistration_mainline_execution.get("artifact_digest")
        or completion_artifact.get("inventory_artifact_digest")
        != inventory_artifact.get("artifact_digest")
        or completion_artifact.get("result_artifact_digest")
        != result_artifact.get("artifact_digest")
        or completion_artifact.get("outcome") != result_artifact.get("outcome")
        or completion_artifact.get("repetition_scan") != REPETITION_SCAN
        or completion_artifact.get("separate_duplicate_membership_or_uniqueness_scan")
        is not False
        or completion_artifact.get("next_consumer")
        != PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_TASK_KEY
        or result_artifact.get("repetition_scan") != REPETITION_SCAN
        or result_artifact.get("production_action") != "none"
    ):
        raise BalancedDesignExecutionError("registered_execution_identity_changed")
    return {
        "schema_version": ("dehps-prediction-v2-balanced-design-execution-replay.v1"),
        "status": "REPLAY_VERIFIED",
        "same_registered_content": True,
        "workload_rerun": False,
        "orbit_candidates_replayed": 0,
        "solver_nodes_replayed": 0,
        "terminal_checkpoint_verified": True,
        "certificate_verified": certificate is not None,
        "outcome": result_artifact["outcome"],
        "repetition_scan": REPETITION_SCAN,
        "next_consumer": (
            PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_TASK_KEY
        ),
    }


def orbit_inventory_from_artifact(
    artifact: Mapping[str, Any],
    *,
    require_formal_identity: bool,
) -> OrbitInventory:
    _verify_artifact(artifact, domain=_INVENTORY_DOMAIN)

    def representative(raw: Mapping[str, Any]) -> OrbitRepresentative:
        return OrbitRepresentative(
            representative_id=int(raw["representative_id"]),
            block=tuple(int(value) for value in raw["block"]),
            orbit_size=int(raw["orbit_size"]),
            stabilizer_size=int(raw["stabilizer_size"]),
            signature=tuple(int(value) for value in raw["signature"]),
        )

    try:
        inventory = OrbitInventory(
            point_count=int(artifact["point_count"]),
            block_size=int(artifact["block_size"]),
            legal_block_count=int(artifact["legal_block_count"]),
            canonical_candidates_visited=int(artifact["canonical_candidates_visited"]),
            full_representatives=tuple(
                representative(raw) for raw in artifact["full_representatives"]
            ),
            short_representatives=tuple(
                representative(raw) for raw in artifact["short_representatives"]
            ),
            signature_groups=tuple(
                SignatureGroup(
                    signature=tuple(int(value) for value in raw["signature"]),
                    representative_ids=tuple(
                        int(value) for value in raw["representative_ids"]
                    ),
                )
                for raw in artifact["signature_groups"]
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise BalancedDesignExecutionError("orbit_inventory_artifact_invalid") from exc
    if (
        artifact.get("status") != "COMPLETE"
        or artifact.get("constructor_family") != CONSTRUCTOR_FAMILY
        or artifact.get("repetition_scan") != REPETITION_SCAN
        or artifact.get("separate_duplicate_membership_or_uniqueness_scan") is not False
        or artifact.get("legal_block_ids_accounted")
        != inventory.legal_block_ids_accounted
        or artifact.get("full_orbit_count") != len(inventory.full_representatives)
        or artifact.get("short_orbit_count") != len(inventory.short_representatives)
        or artifact.get("signature_group_count") != len(inventory.signature_groups)
    ):
        raise BalancedDesignExecutionError("orbit_inventory_artifact_changed")
    if require_formal_identity:
        _require_formal_inventory(inventory)
    return inventory


def _validate_parent_artifacts(
    *,
    preregistration: Mapping[str, Any],
    execution_handoff: Mapping[str, Any],
    preregistration_completion: Mapping[str, Any],
    preregistration_mainline_execution: Mapping[str, Any],
    require_registered_identities: bool,
) -> None:
    _verify_artifact(
        preregistration,
        domain="dehps.prediction-v2.balanced-design-feasibility-preregistration.v1",
    )
    _verify_artifact(
        execution_handoff,
        domain=("dehps.prediction-v2.balanced-design-feasibility-execution-handoff.v1"),
    )
    _verify_artifact(
        preregistration_completion,
        domain=(
            "dehps.prediction-v2.balanced-design-feasibility-"
            "preregistration-completion.v1"
        ),
    )
    _verify_artifact(
        preregistration_mainline_execution,
        domain="dehps.research-os.mainline-execution.v1",
    )
    observed = (
        str(preregistration.get("artifact_digest")),
        str(execution_handoff.get("artifact_digest")),
        str(preregistration_completion.get("artifact_digest")),
        str(preregistration_mainline_execution.get("artifact_digest")),
    )
    if require_registered_identities and observed != (
        PREREGISTRATION_DIGEST,
        EXECUTION_HANDOFF_DIGEST,
        PREREGISTRATION_COMPLETION_DIGEST,
        PREREGISTRATION_MAINLINE_EXECUTION_DIGEST,
    ):
        raise BalancedDesignExecutionError("registered_parent_identity_changed")
    if (
        preregistration.get("status") != "COMPLETE"
        or preregistration.get("preregistration_status") != "FROZEN_NOT_EXECUTED"
        or preregistration.get("constructor_family") != CONSTRUCTOR_FAMILY
        or preregistration.get("result_blind") is not True
        or preregistration.get("repetition_scan") != REPETITION_SCAN
        or execution_handoff.get("status") != "COMPLETE"
        or execution_handoff.get("preregistration_digest")
        != preregistration.get("artifact_digest")
        or execution_handoff.get("constructor_family") != CONSTRUCTOR_FAMILY
        or execution_handoff.get("result_blind") is not True
        or execution_handoff.get("repetition_scan") != REPETITION_SCAN
        or preregistration_completion.get("status") != "COMPLETE"
        or preregistration_completion.get("completion_fact")
        != ("prediction-v2-balanced-design-feasibility-preregistration:COMPLETE")
        or preregistration_completion.get("preregistration_digest")
        != preregistration.get("artifact_digest")
        or preregistration_completion.get("execution_handoff_digest")
        != execution_handoff.get("artifact_digest")
        or preregistration_completion.get("repetition_scan") != REPETITION_SCAN
        or preregistration_mainline_execution.get("status") != "COMPLETE"
        or preregistration_mainline_execution.get("task_key")
        != "prediction-v2-balanced-design-feasibility-preregistration"
        or preregistration_mainline_execution.get("preregistration_completion_digest")
        != preregistration_completion.get("artifact_digest")
        or preregistration_mainline_execution.get("repetition_scan") != REPETITION_SCAN
        or preregistration_mainline_execution.get("production_action") != "none"
    ):
        raise BalancedDesignExecutionError("registered_parent_consistency_invalid")


def peak_resident_bytes() -> int:
    # Linux reports ru_maxrss in KiB.
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024


def load_execution_source_contract(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BalancedDesignExecutionError("execution_source_contract_invalid") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != _SOURCE_SCHEMA
        or payload.get("artifact_type") != _SOURCE_ARTIFACT_TYPE
        or payload.get("status") != "FROZEN_SOURCE_INTEGRATION_PENDING"
        or payload.get("contract_key")
        != "PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_SOURCE"
        or payload.get("research_request_key") != _EXPECTED_RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != 417
        or payload.get("research_execution_id") != 338
        or payload.get("engineering_request_key") != _EXPECTED_ENGINEERING_REQUEST_KEY
        or payload.get("engineering_request_id") != 422
        or payload.get("engineering_execution_id") != 343
        or payload.get("constructor_family") != CONSTRUCTOR_FAMILY
        or payload.get("formal_execution_allowed_during_engineering") is not False
        or payload.get("preregistration_digest") != PREREGISTRATION_DIGEST
        or payload.get("execution_handoff_digest") != EXECUTION_HANDOFF_DIGEST
        or payload.get("preregistration_completion_digest")
        != PREREGISTRATION_COMPLETION_DIGEST
        or payload.get("preregistration_mainline_execution_digest")
        != PREREGISTRATION_MAINLINE_EXECUTION_DIGEST
        or payload.get("repetition_scan") != REPETITION_SCAN
        or payload.get("registered_children") != 3
        or payload.get("next_consumer")
        != PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_TASK_KEY
        or payload.get("new_evidence_created") is not False
        or payload.get("new_model_created") is not False
        or payload.get("production_action") != "none"
        or payload.get("artifact_digest") != config_digest(payload)
    ):
        raise BalancedDesignExecutionError("execution_source_contract_changed")
    entries = payload.get("source_entries")
    if (
        not isinstance(entries, list)
        or len(entries) != 1
        or not isinstance(entries[0], dict)
        or entries[0].get("path") != _SOURCE_MODULE_PATH
        or not _is_digest(entries[0].get("content_sha256"))
    ):
        raise BalancedDesignExecutionError("execution_source_entries_invalid")
    return payload


def verify_execution_source_bytes(
    *,
    root_dir: Path,
    contract: Mapping[str, Any],
) -> None:
    entries = contract.get("source_entries")
    if not isinstance(entries, list) or not entries:
        raise BalancedDesignExecutionError("execution_source_entries_invalid")
    actual_entries: list[dict[str, str]] = []
    from hashlib import sha256

    for raw in entries:
        if not isinstance(raw, dict) or tuple(sorted(raw)) != (
            "content_sha256",
            "path",
        ):
            raise BalancedDesignExecutionError("execution_source_entries_invalid")
        path = str(raw["path"])
        try:
            digest = sha256((root_dir / path).read_bytes()).hexdigest()
        except OSError as exc:
            raise BalancedDesignExecutionError(
                "execution_source_bytes_missing"
            ) from exc
        if digest != raw["content_sha256"]:
            raise BalancedDesignExecutionError("execution_source_bytes_changed")
        actual_entries.append({"path": path, "content_sha256": digest})
    if canonical_digest(
        actual_entries,
        domain="dehps.prediction-v2.balanced-design.execution-source-set.v1",
    ) != contract.get("source_set_digest"):
        raise BalancedDesignExecutionError("execution_source_set_changed")


def _artifact(body: Mapping[str, Any], *, domain: str) -> dict[str, Any]:
    payload = dict(body)
    payload["artifact_digest"] = canonical_digest(payload, domain=domain)
    return payload


def _verify_artifact(artifact: Mapping[str, Any], *, domain: str) -> None:
    supplied = str(artifact.get("artifact_digest") or "")
    identity = dict(artifact)
    identity.pop("artifact_digest", None)
    if supplied != canonical_digest(identity, domain=domain):
        raise BalancedDesignExecutionError("artifact_digest_changed")


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
