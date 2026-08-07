from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from dehps.golden_source_identity import validate_golden_source_integrity_identity
from dehps.research_os.information_theory.digest import config_digest

REVIEWED_SHARED_COMPATIBILITY_FIXTURE_PATH = Path(
    "configs/research-os/"
    "m4-p2-6-1-sparse-tree-source-compatibility-fixture-v1.json"
)
REVIEWED_SHARED_COMPATIBILITY_SCHEMA = (
    "dehps-m4-p2-6-1-reviewed-sparse-tree-source-compatibility-fixture.v1"
)
REVIEWED_SHARED_COMPATIBILITY_TYPE = "ReviewedSharedSourceCompatibilityFixture"
REVIEWED_SHARED_COMPATIBILITY_PATHS = (
    (
        "apps/worker-python/dehps/research_os/information_theory/probes/"
        "shallow_calibrated_tree.py"
    ),
)
P263_REVIEWED_SOURCE_COMPATIBILITY_FIXTURE_PATH = Path(
    "configs/research-os/"
    "m4-p2-6-3-periodic-refit-source-compatibility-fixture-v1.json"
)
P263_REVIEWED_SOURCE_COMPATIBILITY_SCHEMA = (
    "dehps-m4-p2-6-3-reviewed-source-compatibility-fixture.v1"
)
P263_REVIEWED_SOURCE_COMPATIBILITY_TYPE = (
    "ReviewedSupersedingSourceCompatibilityFixture"
)
P263_REVIEWED_SOURCE_COMPATIBILITY_PATHS = (
    (
        "apps/worker-python/dehps/research_os/information_theory/"
        "measurement_validation/schedule.py"
    ),
    (
        "apps/worker-python/dehps/research_os/information_theory/"
        "measurement_validation/statistics.py"
    ),
    (
        "apps/worker-python/dehps/research_os/information_theory/"
        "probes/shallow_calibrated_tree.py"
    ),
)

_SHA1_PATTERN = re.compile(r"[0-9a-f]{40}")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_FIXTURE_FIELDS = {
    "schema_version",
    "artifact_type",
    "artifact_digest",
    "fixture_key",
    "status",
    "baseline_git_commit",
    "baseline_runtime_commit",
    "candidate_round",
    "changed_paths",
    "baseline_source_entries",
    "candidate_source_entries",
    "registered_golden_source_integrity_identity",
    "candidate_golden_source_integrity_identity",
    "exact_replay",
    "prefix_spot_replay",
    "performance",
    "independent_reference",
    "governance",
}
_EXACT_REPLAY_FIELDS = {
    "scale_id",
    "fold_count",
    "result_float64_tree_digest",
    "trace_set_digest",
    "checkpoint_journal_sha256",
    "checkpoint_journal_byte_count",
    "result_object_exact",
    "probability_bits_exact",
    "probe_state_trees_exact",
    "fold_traces_exact",
    "checkpoint_and_settlement_exact",
    "journal_bytes_exact",
}
_PREFIX_SPOT_FIELDS = {
    "case_count",
    "historical_fold_indices",
    "long_fold_indices",
    "scenario_ids",
    "state_exact",
    "probability_bits_exact",
}
_PERFORMANCE_FIELDS = {
    "scale_id",
    "fold_index",
    "training_issue_count",
    "sample_count_per_path",
    "before_median_seconds",
    "after_median_seconds",
    "speedup",
    "minimum_speedup",
    "state_and_probability_exact",
}
_INDEPENDENT_REFERENCE_FIELDS = {
    "literal_runtime_cache_used",
    "literal_acceleration_backend_imported",
    "observed_acceleration_backend_imported",
    "source_identity_checked_before_replay",
    "old_and_new_paths_executed_in_separate_processes",
}
_GOVERNANCE_FIELDS = {
    "reviewed",
    "scientific_contract_changed",
    "statistical_results_read",
    "evidence_progress_increment",
    "production_action",
}
_P263_FIXTURE_FIELDS = {
    "schema_version",
    "artifact_type",
    "artifact_digest",
    "fixture_key",
    "status",
    "baseline_git_commit",
    "candidate_git_commit",
    "changed_paths",
    "baseline_source_entries",
    "candidate_source_entries",
    "registered_golden_source_integrity_identity",
    "candidate_golden_source_integrity_identity",
    "source_roles",
    "result_blind",
    "periodic_refit_temporal_contract",
    "governance",
}
_P263_SOURCE_ROLES = {
    P263_REVIEWED_SOURCE_COMPATIBILITY_PATHS[0]: "FOLD_SCHEDULE",
    P263_REVIEWED_SOURCE_COMPATIBILITY_PATHS[1]: "INFERENCE_STATISTICS",
    P263_REVIEWED_SOURCE_COMPATIBILITY_PATHS[2]: "LEARNED_PROBE",
}
_P263_RESULT_BLIND = {
    "historical_outcomes_read": False,
    "previous_score_read": False,
    "previous_prediction_read": False,
    "previous_ranking_read": False,
    "power_result_read": False,
    "false_positive_result_read": False,
    "bias_rmse_coverage_result_read": False,
    "mde_result_read": False,
    "threshold_selected_from_results": False,
}
_P263_TEMPORAL_CONTRACT = {
    "policy_digest": (
        "ad58b9abcd90c5e7ee7b9892ac8c209b8033f7a50e603b58c043685b0c7d6f99"
    ),
    "refit_interval_folds": 64,
    "training_state": "STRICT_PRIOR_THROUGH_T_MINUS_1",
    "prediction_target": "T",
    "current_target_available_before_prediction": False,
    "prediction_checkpoint_written_before_target_read": True,
    "boundary_refit_uses_current_target": False,
    "resume_reuses_only_settled_folds": True,
    "future_fold_state_read": False,
}
_P263_GOVERNANCE = {
    "reviewed": True,
    "scientific_contract_changed": True,
    "change_classification": "MEASUREMENT_CONTRACT_EVOLUTION",
    "statistical_results_read": False,
    "evidence_progress_increment": 0,
    "prediction_v2_promotion_allowed": False,
    "production_action": "none",
}


class SourceCompatibilityError(RuntimeError):
    pass


def _validated_source_entries(
    raw: object,
    *,
    expected_paths: Sequence[str],
    label: str,
) -> tuple[dict[str, str], ...]:
    if not isinstance(raw, list):
        raise SourceCompatibilityError(f"{label}_source_entries_invalid")
    entries: list[dict[str, str]] = []
    for value in raw:
        if not isinstance(value, Mapping) or set(value) != {
            "path",
            "content_sha256",
            "git_blob_oid",
        }:
            raise SourceCompatibilityError(f"{label}_source_entries_invalid")
        entry = {key: str(value.get(key) or "") for key in value}
        if (
            _SHA256_PATTERN.fullmatch(entry["content_sha256"]) is None
            or _SHA1_PATTERN.fullmatch(entry["git_blob_oid"]) is None
        ):
            raise SourceCompatibilityError(f"{label}_source_entries_invalid")
        entries.append(entry)
    if tuple(entry["path"] for entry in entries) != tuple(expected_paths):
        raise SourceCompatibilityError(f"{label}_source_paths_changed")
    return tuple(entries)


def validate_reviewed_shared_compatibility_fixture(
    value: object,
    *,
    expected_artifact_digest: str | None = None,
    expected_candidate_golden_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _FIXTURE_FIELDS:
        raise SourceCompatibilityError("shared_compatibility_fixture_shape_changed")
    payload = dict(value)
    digest = str(payload.get("artifact_digest") or "")
    if (
        payload.get("schema_version") != REVIEWED_SHARED_COMPATIBILITY_SCHEMA
        or payload.get("artifact_type") != REVIEWED_SHARED_COMPATIBILITY_TYPE
        or payload.get("fixture_key") != "M4-P2.6.1_EXACT_SPARSE_TREE_ROUND_6"
        or payload.get("status") != "REVIEWED_EXACT_COMPATIBILITY"
        or payload.get("baseline_git_commit")
        != "70f83a5400c6207cbe3806e69329a233e461e311"
        or payload.get("baseline_runtime_commit")
        != "5c3778a9004041aee2ca707e7b4cc24f338ab3ed"
        or payload.get("candidate_round") != 6
        or payload.get("changed_paths")
        != list(REVIEWED_SHARED_COMPATIBILITY_PATHS)
        or _SHA256_PATTERN.fullmatch(digest) is None
        or config_digest(payload) != digest
        or (expected_artifact_digest is not None and digest != expected_artifact_digest)
    ):
        raise SourceCompatibilityError("shared_compatibility_fixture_identity_changed")

    _validated_source_entries(
        payload.get("baseline_source_entries"),
        expected_paths=REVIEWED_SHARED_COMPATIBILITY_PATHS,
        label="baseline",
    )
    _validated_source_entries(
        payload.get("candidate_source_entries"),
        expected_paths=REVIEWED_SHARED_COMPATIBILITY_PATHS,
        label="candidate",
    )
    validate_golden_source_integrity_identity(
        payload.get("registered_golden_source_integrity_identity")
    )
    candidate_identity = validate_golden_source_integrity_identity(
        payload.get("candidate_golden_source_integrity_identity")
    )
    if (
        expected_candidate_golden_identity is not None
        and candidate_identity
        != validate_golden_source_integrity_identity(
            expected_candidate_golden_identity
        )
    ):
        raise SourceCompatibilityError(
            "shared_compatibility_candidate_source_identity_changed"
        )

    replay = payload.get("exact_replay")
    if (
        not isinstance(replay, Mapping)
        or set(replay) != _EXACT_REPLAY_FIELDS
        or replay.get("scale_id") != "FORWARD_61"
        or replay.get("fold_count") != 61
        or any(
            _SHA256_PATTERN.fullmatch(str(replay.get(field) or "")) is None
            for field in (
                "result_float64_tree_digest",
                "trace_set_digest",
                "checkpoint_journal_sha256",
            )
        )
        or not isinstance(replay.get("checkpoint_journal_byte_count"), int)
        or replay.get("checkpoint_journal_byte_count") <= 0
        or any(
            replay.get(field) is not True
            for field in (
                "result_object_exact",
                "probability_bits_exact",
                "probe_state_trees_exact",
                "fold_traces_exact",
                "checkpoint_and_settlement_exact",
                "journal_bytes_exact",
            )
        )
    ):
        raise SourceCompatibilityError("shared_compatibility_replay_changed")

    spots = payload.get("prefix_spot_replay")
    if (
        not isinstance(spots, Mapping)
        or set(spots) != _PREFIX_SPOT_FIELDS
        or spots.get("case_count") != 7
        or spots.get("historical_fold_indices") != [0, 1290, 2580]
        or spots.get("long_fold_indices") != [0, 3030, 6061]
        or spots.get("scenario_ids")
        != ["NULL_UNIFORM", "MEDIUM_PRACTICAL_PAIR"]
        or spots.get("state_exact") is not True
        or spots.get("probability_bits_exact") is not True
    ):
        raise SourceCompatibilityError("shared_compatibility_prefix_spots_changed")

    performance = payload.get("performance")
    if (
        not isinstance(performance, Mapping)
        or set(performance) != _PERFORMANCE_FIELDS
        or performance.get("scale_id") != "LONG"
        or performance.get("fold_index") != 6061
        or performance.get("training_issue_count") != 6961
        or performance.get("sample_count_per_path") != 4
        or not isinstance(performance.get("before_median_seconds"), float)
        or not isinstance(performance.get("after_median_seconds"), float)
        or not isinstance(performance.get("speedup"), float)
        or performance.get("minimum_speedup") != 1.10
        or performance.get("speedup") < performance.get("minimum_speedup")
        or performance.get("state_and_probability_exact") is not True
    ):
        raise SourceCompatibilityError("shared_compatibility_performance_changed")

    independent = payload.get("independent_reference")
    if (
        not isinstance(independent, Mapping)
        or set(independent) != _INDEPENDENT_REFERENCE_FIELDS
        or independent.get("literal_runtime_cache_used") is not False
        or independent.get("literal_acceleration_backend_imported") is not False
        or independent.get("observed_acceleration_backend_imported") is not True
        or independent.get("source_identity_checked_before_replay") is not True
        or independent.get("old_and_new_paths_executed_in_separate_processes")
        is not True
    ):
        raise SourceCompatibilityError(
            "shared_compatibility_reference_independence_changed"
        )

    governance = payload.get("governance")
    if (
        not isinstance(governance, Mapping)
        or set(governance) != _GOVERNANCE_FIELDS
        or governance.get("reviewed") is not True
        or governance.get("scientific_contract_changed") is not False
        or governance.get("statistical_results_read") is not False
        or governance.get("evidence_progress_increment") != 0
        or governance.get("production_action") != "none"
    ):
        raise SourceCompatibilityError("shared_compatibility_governance_changed")
    return payload


def load_reviewed_shared_compatibility_fixture(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceCompatibilityError(
            f"shared_compatibility_fixture_invalid:{exc}"
        ) from exc
    return validate_reviewed_shared_compatibility_fixture(payload)


def validate_p263_reviewed_source_compatibility_fixture(
    value: object,
    *,
    expected_artifact_digest: str | None = None,
    expected_candidate_golden_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _P263_FIXTURE_FIELDS:
        raise SourceCompatibilityError(
            "p263_source_compatibility_fixture_shape_changed"
        )
    payload = dict(value)
    digest = str(payload.get("artifact_digest") or "")
    if (
        payload.get("schema_version")
        != P263_REVIEWED_SOURCE_COMPATIBILITY_SCHEMA
        or payload.get("artifact_type")
        != P263_REVIEWED_SOURCE_COMPATIBILITY_TYPE
        or payload.get("fixture_key")
        != "M4-P2.6.3_PERIODIC_REFIT_SUPERSEDING_SOURCE"
        or payload.get("status") != "REVIEWED_RESULT_BLIND_COMPATIBILITY"
        or payload.get("baseline_git_commit")
        != "70f83a5400c6207cbe3806e69329a233e461e311"
        or payload.get("candidate_git_commit")
        != "0842201871aef856b97838c38bb53d536e1e5893"
        or payload.get("changed_paths")
        != list(P263_REVIEWED_SOURCE_COMPATIBILITY_PATHS)
        or _SHA256_PATTERN.fullmatch(digest) is None
        or config_digest(payload) != digest
        or (
            expected_artifact_digest is not None
            and digest != expected_artifact_digest
        )
    ):
        raise SourceCompatibilityError(
            "p263_source_compatibility_fixture_identity_changed"
        )
    _validated_source_entries(
        payload.get("baseline_source_entries"),
        expected_paths=P263_REVIEWED_SOURCE_COMPATIBILITY_PATHS,
        label="p263_baseline",
    )
    _validated_source_entries(
        payload.get("candidate_source_entries"),
        expected_paths=P263_REVIEWED_SOURCE_COMPATIBILITY_PATHS,
        label="p263_candidate",
    )
    validate_golden_source_integrity_identity(
        payload.get("registered_golden_source_integrity_identity")
    )
    candidate_identity = validate_golden_source_integrity_identity(
        payload.get("candidate_golden_source_integrity_identity")
    )
    if (
        expected_candidate_golden_identity is not None
        and candidate_identity
        != validate_golden_source_integrity_identity(
            expected_candidate_golden_identity
        )
    ):
        raise SourceCompatibilityError(
            "p263_source_compatibility_candidate_identity_changed"
        )
    if (
        payload.get("source_roles") != _P263_SOURCE_ROLES
        or payload.get("result_blind") != _P263_RESULT_BLIND
        or payload.get("periodic_refit_temporal_contract")
        != _P263_TEMPORAL_CONTRACT
        or payload.get("governance") != _P263_GOVERNANCE
    ):
        raise SourceCompatibilityError(
            "p263_source_compatibility_boundary_changed"
        )
    return payload


def load_p263_reviewed_source_compatibility_fixture(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceCompatibilityError(
            f"p263_source_compatibility_fixture_invalid:{exc}"
        ) from exc
    return validate_p263_reviewed_source_compatibility_fixture(payload)
