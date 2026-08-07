from __future__ import annotations

import hashlib
import json
import math
from array import array
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from math import comb
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

from .contracts import json_compatible_copy
from .marginal_static_contract import (
    DRAW_CARDINALITY,
    ESTIMATOR_ID,
    MARGINAL_BRANCH_ID,
    MARGINAL_STATIC_CONTRACT_FREEZE_COMPLETION_FACT,
    NUMBER_COUNT,
)
from .preflight_execution import PREFLIGHT_EXECUTION_PASS_FACT

MARGINAL_STATIC_FIXTURE_FREEZE_TASK_KEY = (
    "m4-v2-marginal-static-measurement-fixture-freeze"
)
MARGINAL_STATIC_FIXTURE_FREEZE_CAPABILITY = (
    "m4_v2_marginal_static_measurement_fixture_freeze"
)
MARGINAL_STATIC_FIXTURE_FREEZE_COMPLETION_FACT = (
    "m4-v2-marginal-static-measurement-fixture-freeze:FROZEN"
)
MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY = (
    "m4-v2-marginal-static-measurement-health-design"
)
MARGINAL_STATIC_FIXTURE_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/m4-v2-marginal-static-fixture-freeze-source-v1.json"
)

M1_FIXTURE_ID = "V2_M1_GROUP_ODDS_2_STATIONARY"
NULL_FIXTURE_ID = "NULL_UNIFORM_LEGAL_SIX_OF_33"
T1_FIXTURE_ID = "V2_T1_OVERLAP_ODDS_2_MARKOV"
J1_FIXTURE_ID = "V2_J1_HISTORY_IS4_LAMBDA_HALF"
FIXTURE_ORDER = (M1_FIXTURE_ID, NULL_FIXTURE_ID, T1_FIXTURE_ID, J1_FIXTURE_ID)


class MarginalStaticFixtureError(RuntimeError):
    pass


@dataclass
class MarginalSufficientStatistics:
    issue_count: int = 0
    number_event_counts: array = field(
        default_factory=lambda: array("q", (0 for _ in range(NUMBER_COUNT)))
    )

    def __post_init__(self) -> None:
        if (
            isinstance(self.issue_count, bool)
            or not isinstance(self.issue_count, int)
            or self.issue_count < 0
            or self.number_event_counts.typecode != "q"
            or self.number_event_counts.itemsize != 8
            or len(self.number_event_counts) != NUMBER_COUNT
            or any(value < 0 or value > self.issue_count for value in self.number_event_counts)
            or sum(self.number_event_counts) != DRAW_CARDINALITY * self.issue_count
        ):
            raise MarginalStaticFixtureError(
                "marginal_sufficient_statistics_invalid"
            )

    def update(self, draw: Sequence[int]) -> None:
        values = tuple(draw)
        if (
            len(values) != DRAW_CARDINALITY
            or any(
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 1
                or value > NUMBER_COUNT
                for value in values
            )
            or len(set(values)) != DRAW_CARDINALITY
        ):
            raise MarginalStaticFixtureError("marginal_fixture_draw_invalid")
        for value in values:
            self.number_event_counts[value - 1] += 1
        self.issue_count += 1

    def snapshot(self) -> dict[str, Any]:
        payload = {
            "schema_version": "dehps-marginal-sufficient-statistics.v1",
            "artifact_type": "marginal_sufficient_statistics",
            "artifact_digest": "",
            "issue_count": self.issue_count,
            "number_event_counts_1_to_33": list(self.number_event_counts),
            "count_type": "signed_int64",
            "database_reads": 0,
            "database_writes": 0,
            "csv_materialized": False,
        }
        identity = dict(payload)
        identity.pop("artifact_digest")
        payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.marginal-sufficient-statistics.v1",
        )
        return payload


@dataclass(frozen=True)
class MarginalStaticFixtureFreezeRun:
    fixtures: tuple[Mapping[str, Any], ...]
    bundle: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return (*self.fixtures, self.bundle, self.completion)


def load_marginal_static_fixture_source_contract(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MarginalStaticFixtureError(
            f"marginal_static_fixture_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-m4-v2-marginal-static-fixture-freeze-source.v1"
        or payload.get("artifact_type")
        != "m4_v2_marginal_static_fixture_freeze_source"
        or payload.get("contract_key")
        != "M4_V2_MARGINAL_STATIC_FIXTURE_FREEZE_SOURCE"
        or payload.get("research_request_key")
        != "research-m4-v2-marginal-static-fixture-freeze-round-40-20260808"
        or payload.get("research_request_id") != 315
        or payload.get("research_execution_id") != 236
        or payload.get("result_blind") is not True
        or payload.get("generated_issues") != 0
        or payload.get("synthetic_replicates") != 0
        or payload.get("historical_outcomes_read") is not False
        or payload.get("statistical_results_read") is not False
        or payload.get("evidence_created") is not False
        or payload.get("production_action") != "none"
        or not isinstance(entries, list)
        or not entries
        or not isinstance(frozen, dict)
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain="dehps.m4.v2.marginal-static-fixture-freeze-source-set.v1",
        )
    ):
        raise MarginalStaticFixtureError(
            "marginal_static_fixture_source_invalid"
        )
    paths: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise MarginalStaticFixtureError(
                "marginal_static_fixture_source_entry_invalid"
            )
        relative = str(entry.get("path") or "")
        digest = str(entry.get("content_sha256") or "")
        parsed = Path(relative)
        if (
            not relative
            or parsed.is_absolute()
            or ".." in parsed.parts
            or parsed.as_posix() != relative
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or relative in paths
        ):
            raise MarginalStaticFixtureError(
                "marginal_static_fixture_source_entry_invalid"
            )
        paths.add(relative)
    _validate_frozen_contract(frozen)
    return payload


def verify_marginal_static_fixture_source_bytes(
    *,
    root_dir: Path,
    contract: Mapping[str, Any],
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise MarginalStaticFixtureError(
                f"marginal_static_fixture_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise MarginalStaticFixtureError(
                f"marginal_static_fixture_source_modified:{relative}"
            )


def build_marginal_static_fixture_artifacts(
    *,
    source_contract: Mapping[str, Any],
    marginal_contract_execution_artifact_digest: str,
    marginal_measurement_contract: Mapping[str, Any],
    marginal_contract_completion: Mapping[str, Any],
    orthogonal_fixture_contract: Mapping[str, Any],
    branch_fixture_completion: Mapping[str, Any],
    marginal_branch_health: Mapping[str, Any],
    preflight_completion: Mapping[str, Any],
    execution_id: str,
    git_commit: str,
) -> MarginalStaticFixtureFreezeRun:
    _validate_inputs(
        marginal_contract_execution_artifact_digest=(
            marginal_contract_execution_artifact_digest
        ),
        marginal_measurement_contract=marginal_measurement_contract,
        marginal_contract_completion=marginal_contract_completion,
        orthogonal_fixture_contract=orthogonal_fixture_contract,
        branch_fixture_completion=branch_fixture_completion,
        marginal_branch_health=marginal_branch_health,
        preflight_completion=preflight_completion,
    )
    frozen = source_contract["frozen_contract"]
    _validate_frozen_contract(frozen)
    source_digest = str(source_contract["artifact_digest"])
    orthogonal_by_id = {
        str(item["fixture_id"]): item
        for item in orthogonal_fixture_contract["fixtures"]
    }
    fixtures: list[Mapping[str, Any]] = []
    for fixture_spec in frozen["fixtures"]:
        fixture_id = str(fixture_spec["fixture_id"])
        orthogonal = orthogonal_by_id[fixture_id]
        expected_gain = _expected_marginal_gain(fixture_id)
        if not math.isclose(
            float(orthogonal["truth_anchor_bits"]["marginal_static"]),
            expected_gain,
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            raise MarginalStaticFixtureError(
                "marginal_static_fixture_truth_anchor_changed"
            )
        fixtures.append(
            _artifact(
                schema_version=(
                    "dehps-m4-v2-marginal-static-measurement-fixture.v1"
                ),
                artifact_type="m4_v2_marginal_static_measurement_fixture",
                body={
                    "status": "FROZEN_FIXTURE",
                    "branch_id": MARGINAL_BRANCH_ID,
                    "estimator_id": ESTIMATOR_ID,
                    "fixture_id": fixture_id,
                    "role": fixture_spec["role"],
                    "generator": json_compatible_copy(fixture_spec["generator"]),
                    "stationary_marginal_truth": json_compatible_copy(
                        fixture_spec["stationary_marginal_truth"]
                    ),
                    "expected_marginal_gain_bits_per_issue": expected_gain,
                    "source_orthogonal_fixture_digest": (
                        orthogonal_fixture_contract["artifact_digest"]
                    ),
                    "source_orthogonal_fixture_definition": orthogonal.get(
                        "definition", "uniform_legal_six_of_33"
                    ),
                    "source_orthogonal_fixture_role": orthogonal["expected_roles"][
                        MARGINAL_BRANCH_ID
                    ],
                    "generated_issues": 0,
                    "synthetic_replicates": 0,
                    "historical_outcomes_read": False,
                    "statistical_results_read": False,
                    "evidence_created": False,
                    "formal_execution_allowed": False,
                    "production_action": "none",
                },
                parent_digests=(
                    source_digest,
                    marginal_contract_execution_artifact_digest,
                    str(marginal_measurement_contract["artifact_digest"]),
                    str(orthogonal_fixture_contract["artifact_digest"]),
                    str(marginal_branch_health["artifact_digest"]),
                ),
                domain="dehps.m4.v2.marginal-static-measurement-fixture.v1",
            )
        )
    bundle = _artifact(
        schema_version="dehps-m4-v2-marginal-static-fixture-bundle.v1",
        artifact_type="m4_v2_marginal_static_fixture_bundle",
        body={
            "status": "FROZEN_FIXTURES",
            "branch_id": MARGINAL_BRANCH_ID,
            "estimator_id": ESTIMATOR_ID,
            "fixture_order": list(FIXTURE_ORDER),
            "fixture_digests": [item["artifact_digest"] for item in fixtures],
            "positive_fixture_id": M1_FIXTURE_ID,
            "negative_fixture_ids": [
                NULL_FIXTURE_ID,
                T1_FIXTURE_ID,
                J1_FIXTURE_ID,
            ],
            "required_checks": json_compatible_copy(frozen["required_checks"]),
            "runtime_boundary": json_compatible_copy(frozen["runtime_boundary"]),
            "sampled_workload_status": "NOT_FROZEN",
            "sample_size_selected": False,
            "inference_thresholds_selected": False,
            "accepted_model_artifact_digest": None,
            "generated_issues": 0,
            "synthetic_replicates": 0,
            "formal_branch_runs_executed": 0,
            "actual_fold_count": 0,
            "historical_outcomes_read": False,
            "statistical_results_read": False,
            "evidence_created": False,
            "evidence_progress_increment": 0,
            "next_consumer": MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY,
            "production_action": "none",
        },
        parent_digests=(
            source_digest,
            marginal_contract_execution_artifact_digest,
            str(marginal_measurement_contract["artifact_digest"]),
            str(marginal_contract_completion["artifact_digest"]),
            str(branch_fixture_completion["artifact_digest"]),
            str(preflight_completion["artifact_digest"]),
            *(str(item["artifact_digest"]) for item in fixtures),
        ),
        domain="dehps.m4.v2.marginal-static-fixture-bundle.v1",
    )
    completion = _artifact(
        schema_version="dehps-m4-v2-marginal-static-fixture-freeze-completion.v1",
        artifact_type="m4_v2_marginal_static_fixture_freeze_completion",
        body={
            "status": "COMPLETE",
            "execution_id": execution_id,
            "git_commit": git_commit,
            "source_contract_digest": source_digest,
            "fixture_bundle_digest": bundle["artifact_digest"],
            "fixture_digests": [item["artifact_digest"] for item in fixtures],
            "fixture_count": len(fixtures),
            "completion_fact": MARGINAL_STATIC_FIXTURE_FREEZE_COMPLETION_FACT,
            "sampled_workload_status": "NOT_FROZEN",
            "generated_issues": 0,
            "synthetic_replicates": 0,
            "formal_branch_runs_executed": 0,
            "actual_fold_count": 0,
            "historical_outcomes_read": False,
            "statistical_results_read": False,
            "evidence_created": False,
            "evidence_progress_increment": 0,
            "next_consumer": MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY,
            "production_action": "none",
        },
        parent_digests=(
            source_digest,
            str(bundle["artifact_digest"]),
            str(marginal_contract_completion["artifact_digest"]),
            str(preflight_completion["artifact_digest"]),
        ),
        domain="dehps.m4.v2.marginal-static-fixture-freeze-completion.v1",
    )
    return MarginalStaticFixtureFreezeRun(
        fixtures=tuple(fixtures),
        bundle=bundle,
        completion=completion,
    )


def _validate_inputs(
    *,
    marginal_contract_execution_artifact_digest: str,
    marginal_measurement_contract: Mapping[str, Any],
    marginal_contract_completion: Mapping[str, Any],
    orthogonal_fixture_contract: Mapping[str, Any],
    branch_fixture_completion: Mapping[str, Any],
    marginal_branch_health: Mapping[str, Any],
    preflight_completion: Mapping[str, Any],
) -> None:
    fixtures = orthogonal_fixture_contract.get("fixtures")
    if (
        len(marginal_contract_execution_artifact_digest) != 64
        or marginal_measurement_contract.get("artifact_type")
        != "m4_v2_marginal_static_measurement_contract"
        or marginal_measurement_contract.get("status")
        != "FROZEN_SYNTHETIC_HEALTH_PENDING"
        or marginal_measurement_contract.get("legacy_measurement_health") != "REPAIR"
        or marginal_measurement_contract.get("legacy_repair_overridden") is not False
        or marginal_measurement_contract.get("historical_execution_status")
        != "NOT_AUTHORIZED"
        or marginal_measurement_contract.get("accepted_model_artifact_digest")
        is not None
        or marginal_measurement_contract.get("next_fixture_obligations", {}).get(
            "positive_control"
        )
        != M1_FIXTURE_ID
        or marginal_measurement_contract.get("next_fixture_obligations", {}).get(
            "negative_controls"
        )
        != [
            f"{NULL_FIXTURE_ID}",
            f"{T1_FIXTURE_ID} projected to stationary marginals",
            f"{J1_FIXTURE_ID} projected to stationary marginals",
        ]
        or marginal_contract_completion.get("artifact_type")
        != "m4_v2_marginal_static_contract_freeze_completion"
        or marginal_contract_completion.get("status") != "COMPLETE"
        or marginal_contract_completion.get("completion_fact")
        != MARGINAL_STATIC_CONTRACT_FREEZE_COMPLETION_FACT
        or marginal_contract_completion.get(
            "marginal_static_measurement_contract_digest"
        )
        != marginal_measurement_contract.get("artifact_digest")
        or orthogonal_fixture_contract.get("artifact_type")
        != "m4_v2_orthogonal_control_fixture_contract"
        or orthogonal_fixture_contract.get("status") != "FROZEN_FIXTURES"
        or not isinstance(fixtures, list)
        or tuple(item.get("fixture_id") for item in fixtures) != (
            M1_FIXTURE_ID,
            T1_FIXTURE_ID,
            J1_FIXTURE_ID,
            NULL_FIXTURE_ID,
        )
        or branch_fixture_completion.get("artifact_type")
        != "m4_v2_branch_fixture_freeze_completion"
        or branch_fixture_completion.get("status") != "COMPLETE"
        or branch_fixture_completion.get(
            "orthogonal_control_fixture_contract_digest"
        )
        != orthogonal_fixture_contract.get("artifact_digest")
        or marginal_branch_health.get("artifact_type")
        != "m4_v2_branch_health_preflight_result"
        or marginal_branch_health.get("branch_id") != MARGINAL_BRANCH_ID
        or marginal_branch_health.get("status") != "PASS"
        or marginal_branch_health.get("measurement_health") != "PASS"
        or marginal_branch_health.get("decision_credit") is not False
        or marginal_branch_health.get("historical_evidence_eligible") is not False
        or marginal_branch_health.get("primary_positive_fixture_id")
        != M1_FIXTURE_ID
        or marginal_branch_health.get("negative_endpoint_keys")
        != [
            f"{T1_FIXTURE_ID}:MARGINAL_STATIC",
            f"{J1_FIXTURE_ID}:MARGINAL_STATIC",
            f"{NULL_FIXTURE_ID}:MARGINAL_STATIC",
        ]
        or preflight_completion.get("artifact_type")
        != "m4_v2_branch_preflight_execution_completion"
        or preflight_completion.get("status") != "COMPLETE"
        or preflight_completion.get("all_branches_pass") is not True
        or preflight_completion.get("all_branches_pass_fact")
        != PREFLIGHT_EXECUTION_PASS_FACT
        or marginal_branch_health.get("artifact_digest")
        not in preflight_completion.get("branch_result_digests", [])
    ):
        raise MarginalStaticFixtureError(
            "marginal_static_fixture_input_identity_changed"
        )


def _validate_frozen_contract(frozen: Any) -> None:
    if not isinstance(frozen, Mapping):
        raise MarginalStaticFixtureError("marginal_static_fixture_contract_missing")
    fixtures = frozen.get("fixtures")
    runtime = frozen.get("runtime_boundary")
    if (
        not isinstance(fixtures, list)
        or tuple(item.get("fixture_id") for item in fixtures) != FIXTURE_ORDER
        or tuple(item.get("role") for item in fixtures)
        != (
            "POSITIVE_CONTROL",
            "NEGATIVE_CONTROL",
            "NEGATIVE_CONTROL",
            "NEGATIVE_CONTROL",
        )
        or fixtures[0].get("stationary_marginal_truth")
        != {
            "group_a_numbers": "1..16",
            "group_a_q": "47343/200861",
            "group_b_numbers": "17..33",
            "group_b_q": "26334/200861",
            "exact_sum": "16*q_a+17*q_b=6",
        }
        or any(
            item.get("stationary_marginal_truth")
            != {"all_numbers_q": "2/11", "exact_sum": "33*(2/11)=6"}
            for item in fixtures[1:]
        )
        or not isinstance(runtime, Mapping)
        or runtime.get("training_state")
        != "issue_count plus ordered signed_int64[33] number-event counts"
        or runtime.get("database_reads_during_replicate") != 0
        or runtime.get("database_writes_during_replicate") != 0
        or runtime.get("csv_materialization") != "forbidden"
        or runtime.get("checkpoint_unit")
        != "completed replicate summary plus deterministic seed-domain identity"
        or runtime.get("resume")
        != "load compact completion index and skip completed replicate digests"
        or runtime.get("duplicate_raw_replay") != "forbidden"
        or runtime.get("routine_physical_checkpoint_scan") != "forbidden"
        or frozen.get("sampled_workload_status") != "NOT_FROZEN"
        or frozen.get("generated_issues") != 0
        or frozen.get("synthetic_replicates") != 0
        or frozen.get("historical_data_allowed") is not False
        or frozen.get("completion_fact")
        != MARGINAL_STATIC_FIXTURE_FREEZE_COMPLETION_FACT
        or frozen.get("next_consumer") != MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY
    ):
        raise MarginalStaticFixtureError("marginal_static_fixture_contract_invalid")
    partition, q_a, q_b = _m1_truth()
    generator = fixtures[0].get("generator")
    if (
        partition != 11_248_216
        or q_a != Fraction(47_343, 200_861)
        or q_b != Fraction(26_334, 200_861)
        or not isinstance(generator, Mapping)
        or generator.get("legal_sample_space") != "six-element subsets of 1..33"
        or generator.get("probability") != "proportional to product w_i"
        or generator.get("weights") != "w_1..w_16=2;w_17..w_33=1"
        or generator.get("partition") != partition
    ):
        raise MarginalStaticFixtureError("marginal_static_fixture_contract_invalid")


def _m1_truth() -> tuple[int, Fraction, Fraction]:
    partition = sum(
        comb(16, selected_a) * comb(17, 6 - selected_a) * (2**selected_a)
        for selected_a in range(7)
    )
    expected_a = sum(
        Fraction(selected_a)
        * comb(16, selected_a)
        * comb(17, 6 - selected_a)
        * (2**selected_a)
        for selected_a in range(7)
    ) / partition
    q_a = expected_a / 16
    q_b = (Fraction(6) - expected_a) / 17
    if 16 * q_a + 17 * q_b != 6:
        raise MarginalStaticFixtureError("marginal_static_fixture_sum_changed")
    return partition, q_a, q_b


def _expected_marginal_gain(fixture_id: str) -> float:
    if fixture_id != M1_FIXTURE_ID:
        return 0.0
    _, q_a, q_b = _m1_truth()
    baseline = Fraction(2, 11)

    def divergence(probability: Fraction) -> float:
        p = float(probability)
        q = float(baseline)
        return p * math.log2(p / q) + (1.0 - p) * math.log2(
            (1.0 - p) / (1.0 - q)
        )

    return 16 * divergence(q_a) + 17 * divergence(q_b)


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
        **json_compatible_copy(body),
        "parent_digests": list(parent_digests),
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(identity, domain=domain)
    return payload
