from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.db import get_connection
from dehps.input_contracts import HistorySnapshotArtifact
from dehps.research_os.information_theory.digest import config_digest

MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_KEY = (
    "m4-v2-marginal-static-historical-measurement-preregistration"
)
MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_CAPABILITY = (
    "m4_v2_marginal_static_historical_measurement_preregistration"
)
MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_COMPLETION_FACT = (
    "m4-v2-marginal-static-historical-measurement-preregistration:FROZEN"
)
MARGINAL_STATIC_HISTORICAL_EXECUTION_TASK_KEY = (
    "m4-v2-marginal-static-historical-measurement-execution"
)
MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/"
    "m4-v2-marginal-static-historical-preregistration-source-v1.json"
)

MARGINAL_STATIC_HISTORICAL_DESIGN_TASK_KEY = (
    "m4-v2-marginal-static-historical-measurement-design"
)
MARGINAL_STATIC_HISTORICAL_DESIGN_TASK_DIGEST = (
    "554e75ca2370e0df73df81a89827580a13c99315a8fce47694936cdd6ec3716e"
)
MARGINAL_STATIC_HISTORICAL_DESIGN_EXECUTION_ID = (
    "4eb05fd1dab8cfe6a8bb144f9efa156a000881c0dfb19438d8973e029081f7ff"
)
MARGINAL_STATIC_HISTORICAL_DESIGN_EXECUTION_DIGEST = (
    "5341f21e5d0a69597362c2244aac12009dfbae847285442780d541088312e649"
)
HISTORICAL_DATASET_BOUNDARY_DIGEST = (
    "c2d03127d2eb966b699b4829402dd72947cf0c959dd013f33169649316a1d420"
)
HISTORICAL_WALK_FORWARD_DESIGN_DIGEST = (
    "da61f66489c4a511f1b9fafe84dfe3bacc10e9e0f15ed270e954db56d662e752"
)
HISTORICAL_INFERENCE_DESIGN_DIGEST = (
    "e52220af0b6cd4c40dd3ff05b9eb692446fe4660b1118ff6cf2b4cd5423f5bb4"
)
HISTORICAL_DESIGN_COMPLETION_DIGEST = (
    "e2624941ae88faa3aff67eff841e773a01a7b343a6c422a9ae433eb2bf710ba0"
)
LEGACY_METADATA_ONLY_HISTORY_IDENTITY = (
    "30224d09a8b2d9080d3bc848f50b534c6d6de50b2eac867882915e85acbf206b"
)

HISTORICAL_ISSUE_COUNT = 3_481
INITIAL_TRAINING_ISSUES = 900
EVALUATION_FOLD_COUNT = 2_581
ROOT_REPLICATES = 2_000
FOLD_SHARD_SIZE = 256
FOLD_SHARD_COUNT = 11
LAST_FOLD_SHARD_SIZE = 21
ROOT_SEED_DOMAIN = "M4_V2_MARGINAL_STATIC_HISTORICAL_INFERENCE_V1"
RESAMPLING_SCHEMES = (
    "MOVING_BLOCK_NONCIRCULAR_LENGTH_5_PRIMARY",
    "MOVING_BLOCK_NONCIRCULAR_LENGTH_3_SENSITIVITY",
    "MOVING_BLOCK_NONCIRCULAR_LENGTH_8_SENSITIVITY",
    "MOVING_BLOCK_NONCIRCULAR_LENGTH_13_SENSITIVITY",
    "STATIONARY_EXPECTED_LENGTH_3_SENSITIVITY",
    "STATIONARY_EXPECTED_LENGTH_5_SENSITIVITY",
    "STATIONARY_EXPECTED_LENGTH_8_SENSITIVITY",
    "STATIONARY_EXPECTED_LENGTH_13_SENSITIVITY",
)
RESAMPLING_CHILD_COUNT = ROOT_REPLICATES * len(RESAMPLING_SCHEMES)
CHECKPOINT_PHASE_ORDER = (
    "COUNTS_FIT_THROUGH_T_MINUS_1",
    "VIRTUAL_CHECKPOINT_PERSISTED",
    "TARGET_T_EXPOSED",
    "TARGET_T_SCORED",
    "COUNTS_UPDATED_WITH_T",
    "FOLD_SETTLED",
)
EXPECTED_ORDINAL_ISSUES = {
    1: "2003001",
    900: "2009075",
    901: "2009076",
    1761: "2015016",
    1762: "2015017",
    2191: "2017139",
    2192: "2017140",
    2621: "2020111",
    2622: "2020112",
    3481: "2026084",
}

_EXPECTED_RESEARCH_REQUEST_KEY = (
    "research-m4-v2-marginal-static-historical-measurement-"
    "preregistration-round-53-20260808"
)
_EXPECTED_ENGINEERING_REQUEST_KEY = (
    "engineering-m4-v2-marginal-static-historical-measurement-"
    "preregistration-round-53-20260808"
)
_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/information_theory/"
    "measurement_system_v2/marginal_static_historical_preregistration.py"
)
# This authenticates the exact Research-367 frozen_contract independently of the
# source-contract self digest.  It is filled after the contract is rendered.
FROZEN_CONTRACT_DIGEST = (
    "8af4853e1215c517c6713229c7d6cc56bb6a57760f4a54edfb5f9bf5e96b6011"
)


class MarginalStaticHistoricalPreregistrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class MarginalStaticHistoricalPreregistrationRun:
    dataset_snapshot: Mapping[str, Any]
    fold_manifest: Mapping[str, Any]
    checkpoint_order_manifest: Mapping[str, Any]
    resampling_manifest: Mapping[str, Any]
    execution_plan: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return (
            self.dataset_snapshot,
            self.fold_manifest,
            self.checkpoint_order_manifest,
            self.resampling_manifest,
            self.execution_plan,
            self.completion,
        )


def load_marginal_static_historical_preregistration_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MarginalStaticHistoricalPreregistrationError(
            f"marginal_static_historical_preregistration_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-m4-v2-marginal-static-historical-preregistration-source.v1"
        or payload.get("artifact_type")
        != "m4_v2_marginal_static_historical_preregistration_source"
        or payload.get("contract_key")
        != "M4_V2_MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_SOURCE"
        or payload.get("research_request_key") != _EXPECTED_RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != 367
        or payload.get("research_execution_id") != 288
        or payload.get("engineering_request_key") != _EXPECTED_ENGINEERING_REQUEST_KEY
        or payload.get("engineering_request_id") != 368
        or payload.get("engineering_execution_id") != 289
        or payload.get("result_blind") is not True
        or payload.get("database_queries_during_capability") != 1
        or payload.get("historical_rows_content_hashed") != HISTORICAL_ISSUE_COUNT
        or payload.get("historical_scores_computed") != 0
        or payload.get("formal_historical_folds_executed") != 0
        or payload.get("bootstrap_children_executed") != 0
        or payload.get("statistical_results_read") is not False
        or payload.get("evidence_created") is not False
        or payload.get("duplicate_validation") is not False
        or payload.get("production_action") != "none"
        or not isinstance(entries, list)
        or len(entries) != 1
        or not isinstance(frozen, dict)
        or payload.get("frozen_contract_digest") != FROZEN_CONTRACT_DIGEST
        or canonical_digest(
            frozen,
            domain=(
                "dehps.m4.v2.marginal-static-historical-preregistration-"
                "frozen-contract.v1"
            ),
        )
        != FROZEN_CONTRACT_DIGEST
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain=(
                "dehps.m4.v2.marginal-static-historical-preregistration-source-set.v1"
            ),
        )
    ):
        raise MarginalStaticHistoricalPreregistrationError(
            "marginal_static_historical_preregistration_source_invalid"
        )
    entry = entries[0]
    if (
        not isinstance(entry, dict)
        or entry.get("path") != _SOURCE_MODULE_PATH
        or not _is_digest(entry.get("content_sha256"))
    ):
        raise MarginalStaticHistoricalPreregistrationError(
            "marginal_static_historical_preregistration_source_entry_invalid"
        )
    _validate_frozen_contract(frozen)
    return payload


def verify_marginal_static_historical_preregistration_source_bytes(
    *, root_dir: Path, contract: Mapping[str, Any]
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise MarginalStaticHistoricalPreregistrationError(
                f"marginal_static_historical_preregistration_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise MarginalStaticHistoricalPreregistrationError(
                f"marginal_static_historical_preregistration_source_modified:{relative}"
            )


def load_canonical_historical_rows() -> tuple[tuple[str, date, tuple[int, ...]], ...]:
    """Read exactly one bounded historical result set under a read-only snapshot."""

    with get_connection() as connection, connection.transaction():
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        rows = connection.execute(
            """
                SELECT issue, draw_date, red_numbers
                FROM ssq_history
                WHERE issue >= %s AND issue <= %s
                ORDER BY issue
                """,
            ("2003001", "2026084"),
        ).fetchall()
    return tuple(
        (str(row[0]), row[1], tuple(int(value) for value in row[2])) for row in rows
    )


def root_seed(
    *, source_contract_digest: str, inference_design_digest: str, replicate_index: int
) -> int:
    if (
        not _is_digest(source_contract_digest)
        or not _is_digest(inference_design_digest)
        or isinstance(replicate_index, bool)
        or not isinstance(replicate_index, int)
        or not 0 <= replicate_index < ROOT_REPLICATES
    ):
        raise MarginalStaticHistoricalPreregistrationError(
            "marginal_static_historical_preregistration_root_seed_invalid"
        )
    digest = canonical_digest(
        {
            "source_contract_digest": source_contract_digest,
            "inference_design_digest": inference_design_digest,
            "root_seed_domain": ROOT_SEED_DOMAIN,
            "replicate_index": replicate_index,
        },
        domain="dehps.m4.v2.marginal-static-historical-root-seed.v1",
    )
    return int(digest[:16], 16)


def fold_identity(
    *,
    dataset_content_digest: str,
    test_ordinal: int,
    test_issue: str,
    test_draw_date: str,
) -> str:
    if (
        not _is_digest(dataset_content_digest)
        or isinstance(test_ordinal, bool)
        or not isinstance(test_ordinal, int)
        or not INITIAL_TRAINING_ISSUES + 1 <= test_ordinal <= HISTORICAL_ISSUE_COUNT
        or len(test_issue) != 7
        or not test_issue.isdigit()
        or len(test_draw_date) != 10
    ):
        raise MarginalStaticHistoricalPreregistrationError(
            "marginal_static_historical_preregistration_fold_identity_invalid"
        )
    return canonical_digest(
        {
            "dataset_content_digest": dataset_content_digest,
            "candidate_estimator_id": "EXPANDING_LEGAL_MARGINAL_ALPHA_1",
            "baseline_id": "LEGAL_UNIFORM_NUMBER_EVENT_BASELINE",
            "training_start_ordinal": 1,
            "training_end_ordinal": test_ordinal - 1,
            "test_ordinal": test_ordinal,
            "test_issue": test_issue,
            "test_draw_date": test_draw_date,
        },
        domain="dehps.m4.v2.marginal-static-historical-fold-identity.v1",
    )


def resampling_child_identity(
    *,
    dataset_content_digest: str,
    inference_design_digest: str,
    scheme_id: str,
    replicate_index: int,
    seed: int,
) -> str:
    if (
        not _is_digest(dataset_content_digest)
        or not _is_digest(inference_design_digest)
        or scheme_id not in RESAMPLING_SCHEMES
        or isinstance(replicate_index, bool)
        or not isinstance(replicate_index, int)
        or not 0 <= replicate_index < ROOT_REPLICATES
        or isinstance(seed, bool)
        or not isinstance(seed, int)
        or not 0 <= seed < 2**64
    ):
        raise MarginalStaticHistoricalPreregistrationError(
            "marginal_static_historical_preregistration_child_identity_invalid"
        )
    return canonical_digest(
        {
            "dataset_content_digest": dataset_content_digest,
            "inference_design_digest": inference_design_digest,
            "scheme_id": scheme_id,
            "replicate_index": replicate_index,
            "root_seed": seed,
        },
        domain="dehps.m4.v2.marginal-static-historical-resampling-child.v1",
    )


def build_marginal_static_historical_preregistration_artifacts(
    *,
    source_contract: Mapping[str, Any],
    historical_design_execution: Mapping[str, Any],
    dataset_boundary: Mapping[str, Any],
    walk_forward_design: Mapping[str, Any],
    inference_design: Mapping[str, Any],
    design_completion: Mapping[str, Any],
    history_rows: Sequence[object],
    execution_id: str,
    git_commit: str,
) -> MarginalStaticHistoricalPreregistrationRun:
    frozen = source_contract.get("frozen_contract")
    if not isinstance(frozen, Mapping):
        raise MarginalStaticHistoricalPreregistrationError(
            "marginal_static_historical_preregistration_contract_missing"
        )
    _validate_frozen_contract(frozen)
    _validate_design_lineage(
        execution=historical_design_execution,
        dataset_boundary=dataset_boundary,
        walk_forward_design=walk_forward_design,
        inference_design=inference_design,
        completion=design_completion,
    )
    if not _is_digest(execution_id) or len(git_commit) != 40:
        raise MarginalStaticHistoricalPreregistrationError(
            "marginal_static_historical_preregistration_execution_identity_invalid"
        )
    try:
        snapshot = HistorySnapshotArtifact.from_history(
            tuple(history_rows),
            source="ssq_history:2003001..2026084",
        )
    except (TypeError, ValueError) as exc:
        raise MarginalStaticHistoricalPreregistrationError(
            "marginal_static_historical_preregistration_dataset_invalid"
        ) from exc
    _validate_snapshot(snapshot)

    source_digest = str(source_contract["artifact_digest"])
    base_parents = (
        source_digest,
        str(historical_design_execution["artifact_digest"]),
        str(dataset_boundary["artifact_digest"]),
        str(walk_forward_design["artifact_digest"]),
        str(inference_design["artifact_digest"]),
        str(design_completion["artifact_digest"]),
    )
    common = {
        "formal_historical_folds_executed": 0,
        "bootstrap_children_executed": 0,
        "historical_scores_computed": 0,
        "statistical_results_read": False,
        "evidence_created": False,
        "accepted_model_artifact_digest": None,
        "promotion_gate_opened": False,
        "duplicate_validation": False,
        "production_action": "none",
    }
    dataset_snapshot = _artifact(
        schema_version=("dehps-m4-v2-marginal-static-historical-dataset-snapshot.v1"),
        artifact_type="m4_v2_marginal_static_historical_dataset_snapshot",
        body={
            "status": "FROZEN_CONTENT_ADDRESSED",
            "source_contract_digest": source_digest,
            "legacy_metadata_only_history_identity": (
                LEGACY_METADATA_ONLY_HISTORY_IDENTITY
            ),
            "legacy_identity_role": "lineage_only_not_content_digest",
            "history_snapshot": snapshot.as_dict(include_records=True),
            "dataset_content_digest": snapshot.history_digest,
            "historical_issue_count": snapshot.draw_count,
            "database_queries_during_capability": 1,
            "historical_rows_content_hashed": snapshot.draw_count,
            "historical_outcomes_hashed": True,
            "historical_outcomes_exposed_to_research_or_decision_logic": False,
            **common,
        },
        parent_digests=base_parents,
        domain="dehps.m4.v2.marginal-static-historical-dataset-snapshot.v1",
    )

    records = snapshot.records
    folds: list[dict[str, Any]] = []
    for test_ordinal in range(INITIAL_TRAINING_ISSUES + 1, len(records) + 1):
        record = records[test_ordinal - 1]
        draw_date = record.draw_date.isoformat() if record.draw_date else ""
        digest = fold_identity(
            dataset_content_digest=snapshot.history_digest,
            test_ordinal=test_ordinal,
            test_issue=record.issue,
            test_draw_date=draw_date,
        )
        folds.append(
            {
                "fold_index": test_ordinal - INITIAL_TRAINING_ISSUES - 1,
                "fold_digest": digest,
                "training_start_ordinal": 1,
                "training_end_ordinal": test_ordinal - 1,
                "test_ordinal": test_ordinal,
                "test_issue": record.issue,
                "test_draw_date": draw_date,
            }
        )
    if (
        len(folds) != EVALUATION_FOLD_COUNT
        or len({item["fold_digest"] for item in folds}) != EVALUATION_FOLD_COUNT
    ):
        raise MarginalStaticHistoricalPreregistrationError(
            "marginal_static_historical_preregistration_fold_set_invalid"
        )
    fold_manifest = _artifact(
        schema_version=("dehps-m4-v2-marginal-static-historical-fold-manifest.v1"),
        artifact_type="m4_v2_marginal_static_historical_fold_manifest",
        body={
            "status": "FROZEN",
            "source_contract_digest": source_digest,
            "dataset_snapshot_digest": dataset_snapshot["artifact_digest"],
            "dataset_content_digest": snapshot.history_digest,
            "candidate_estimator_id": "EXPANDING_LEGAL_MARGINAL_ALPHA_1",
            "baseline_id": "LEGAL_UNIFORM_NUMBER_EVENT_BASELINE",
            "initial_training_issue_count": INITIAL_TRAINING_ISSUES,
            "fold_count": len(folds),
            "folds": folds,
            **common,
        },
        parent_digests=(*base_parents, str(dataset_snapshot["artifact_digest"])),
        domain="dehps.m4.v2.marginal-static-historical-fold-manifest.v1",
    )

    order_entries = [
        {
            "fold_index": item["fold_index"],
            "fold_digest": item["fold_digest"],
            "test_ordinal": item["test_ordinal"],
            "phase_order": list(CHECKPOINT_PHASE_ORDER),
            "order_digest": canonical_digest(
                {
                    "fold_digest": item["fold_digest"],
                    "test_ordinal": item["test_ordinal"],
                    "phase_order": list(CHECKPOINT_PHASE_ORDER),
                },
                domain=("dehps.m4.v2.marginal-static-historical-checkpoint-order.v1"),
            ),
        }
        for item in folds
    ]
    checkpoint_order_manifest = _artifact(
        schema_version=(
            "dehps-m4-v2-marginal-static-historical-checkpoint-order-manifest.v1"
        ),
        artifact_type=("m4_v2_marginal_static_historical_checkpoint_order_manifest"),
        body={
            "status": "FROZEN",
            "source_contract_digest": source_digest,
            "dataset_content_digest": snapshot.history_digest,
            "fold_manifest_digest": fold_manifest["artifact_digest"],
            "entry_count": len(order_entries),
            "phase_order": list(CHECKPOINT_PHASE_ORDER),
            "checkpoint_is_forward_evidence": False,
            "partial_run_evidence": "forbidden",
            "entries": order_entries,
            **common,
        },
        parent_digests=(
            *base_parents,
            str(dataset_snapshot["artifact_digest"]),
            str(fold_manifest["artifact_digest"]),
        ),
        domain=("dehps.m4.v2.marginal-static-historical-checkpoint-order-manifest.v1"),
    )

    roots: list[dict[str, Any]] = []
    children: list[dict[str, Any]] = []
    for replicate_index in range(ROOT_REPLICATES):
        seed = root_seed(
            source_contract_digest=source_digest,
            inference_design_digest=HISTORICAL_INFERENCE_DESIGN_DIGEST,
            replicate_index=replicate_index,
        )
        root_digest = canonical_digest(
            {
                "root_seed_domain": ROOT_SEED_DOMAIN,
                "replicate_index": replicate_index,
                "root_seed": seed,
            },
            domain="dehps.m4.v2.marginal-static-historical-resampling-root.v1",
        )
        roots.append(
            {
                "replicate_index": replicate_index,
                "root_seed": seed,
                "root_digest": root_digest,
            }
        )
        for scheme_id in RESAMPLING_SCHEMES:
            children.append(
                {
                    "replicate_index": replicate_index,
                    "scheme_id": scheme_id,
                    "root_seed": seed,
                    "child_digest": resampling_child_identity(
                        dataset_content_digest=snapshot.history_digest,
                        inference_design_digest=HISTORICAL_INFERENCE_DESIGN_DIGEST,
                        scheme_id=scheme_id,
                        replicate_index=replicate_index,
                        seed=seed,
                    ),
                }
            )
    if (
        len(roots) != ROOT_REPLICATES
        or len({item["root_seed"] for item in roots}) != ROOT_REPLICATES
        or len(children) != RESAMPLING_CHILD_COUNT
        or len({item["child_digest"] for item in children}) != RESAMPLING_CHILD_COUNT
    ):
        raise MarginalStaticHistoricalPreregistrationError(
            "marginal_static_historical_preregistration_resampling_set_invalid"
        )
    resampling_manifest = _artifact(
        schema_version=(
            "dehps-m4-v2-marginal-static-historical-resampling-manifest.v1"
        ),
        artifact_type="m4_v2_marginal_static_historical_resampling_manifest",
        body={
            "status": "FROZEN",
            "source_contract_digest": source_digest,
            "dataset_content_digest": snapshot.history_digest,
            "historical_inference_design_digest": (HISTORICAL_INFERENCE_DESIGN_DIGEST),
            "root_seed_domain": ROOT_SEED_DOMAIN,
            "root_replicate_count": len(roots),
            "scheme_count": len(RESAMPLING_SCHEMES),
            "child_count": len(children),
            "selection_policy": "no_best_seed",
            "schemes": list(RESAMPLING_SCHEMES),
            "roots": roots,
            "children": children,
            **common,
        },
        parent_digests=(
            *base_parents,
            str(dataset_snapshot["artifact_digest"]),
            str(fold_manifest["artifact_digest"]),
            str(checkpoint_order_manifest["artifact_digest"]),
        ),
        domain="dehps.m4.v2.marginal-static-historical-resampling-manifest.v1",
    )

    execution_plan = _artifact(
        schema_version=("dehps-m4-v2-marginal-static-historical-execution-plan.v1"),
        artifact_type="m4_v2_marginal_static_historical_execution_plan",
        body={
            "status": "FROZEN_PREREGISTRATION",
            "source_contract_digest": source_digest,
            "dataset_snapshot_digest": dataset_snapshot["artifact_digest"],
            "dataset_content_digest": snapshot.history_digest,
            "fold_manifest_digest": fold_manifest["artifact_digest"],
            "checkpoint_order_manifest_digest": checkpoint_order_manifest[
                "artifact_digest"
            ],
            "resampling_manifest_digest": resampling_manifest["artifact_digest"],
            "inference_algorithms": frozen["inference_algorithms"],
            "time_stability": frozen["time_stability"],
            "execution": frozen["execution"],
            "formal_historical_execution_authorized": False,
            "automatic_evidence_from_preregistration": False,
            "next_consumer": MARGINAL_STATIC_HISTORICAL_EXECUTION_TASK_KEY,
            **common,
        },
        parent_digests=(
            *base_parents,
            str(dataset_snapshot["artifact_digest"]),
            str(fold_manifest["artifact_digest"]),
            str(checkpoint_order_manifest["artifact_digest"]),
            str(resampling_manifest["artifact_digest"]),
        ),
        domain="dehps.m4.v2.marginal-static-historical-execution-plan.v1",
    )
    completion = _artifact(
        schema_version=(
            "dehps-m4-v2-marginal-static-historical-preregistration-completion.v1"
        ),
        artifact_type=("m4_v2_marginal_static_historical_preregistration_completion"),
        body={
            "status": "COMPLETE",
            "execution_id": execution_id,
            "git_commit": git_commit,
            "source_contract_digest": source_digest,
            "dataset_snapshot_digest": dataset_snapshot["artifact_digest"],
            "dataset_content_digest": snapshot.history_digest,
            "fold_manifest_digest": fold_manifest["artifact_digest"],
            "checkpoint_order_manifest_digest": checkpoint_order_manifest[
                "artifact_digest"
            ],
            "resampling_manifest_digest": resampling_manifest["artifact_digest"],
            "historical_execution_plan_digest": execution_plan["artifact_digest"],
            "historical_issue_count": HISTORICAL_ISSUE_COUNT,
            "fold_count": EVALUATION_FOLD_COUNT,
            "checkpoint_order_entry_count": EVALUATION_FOLD_COUNT,
            "root_seed_count": ROOT_REPLICATES,
            "resampling_scheme_count": len(RESAMPLING_SCHEMES),
            "resampling_child_count": RESAMPLING_CHILD_COUNT,
            "fold_shard_count": FOLD_SHARD_COUNT,
            "completion_fact": (
                MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_COMPLETION_FACT
            ),
            "next_consumer": MARGINAL_STATIC_HISTORICAL_EXECUTION_TASK_KEY,
            **common,
        },
        parent_digests=(
            *base_parents,
            str(dataset_snapshot["artifact_digest"]),
            str(fold_manifest["artifact_digest"]),
            str(checkpoint_order_manifest["artifact_digest"]),
            str(resampling_manifest["artifact_digest"]),
            str(execution_plan["artifact_digest"]),
        ),
        domain=("dehps.m4.v2.marginal-static-historical-preregistration-completion.v1"),
    )
    return MarginalStaticHistoricalPreregistrationRun(
        dataset_snapshot=dataset_snapshot,
        fold_manifest=fold_manifest,
        checkpoint_order_manifest=checkpoint_order_manifest,
        resampling_manifest=resampling_manifest,
        execution_plan=execution_plan,
        completion=completion,
    )


def _validate_snapshot(snapshot: HistorySnapshotArtifact) -> None:
    if (
        snapshot.draw_count != HISTORICAL_ISSUE_COUNT
        or snapshot.first_issue != "2003001"
        or snapshot.latest_issue != "2026084"
        or snapshot.records[0].draw_date != date(2003, 2, 23)
        or snapshot.records[-1].draw_date != date(2026, 7, 23)
    ):
        raise MarginalStaticHistoricalPreregistrationError(
            "marginal_static_historical_preregistration_dataset_boundary_invalid"
        )
    for ordinal, expected_issue in EXPECTED_ORDINAL_ISSUES.items():
        if snapshot.records[ordinal - 1].issue != expected_issue:
            raise MarginalStaticHistoricalPreregistrationError(
                "marginal_static_historical_preregistration_dataset_ordinal_invalid"
            )


def _validate_design_lineage(
    *,
    execution: Mapping[str, Any],
    dataset_boundary: Mapping[str, Any],
    walk_forward_design: Mapping[str, Any],
    inference_design: Mapping[str, Any],
    completion: Mapping[str, Any],
) -> None:
    if (
        execution.get("execution_id") != MARGINAL_STATIC_HISTORICAL_DESIGN_EXECUTION_ID
        or execution.get("artifact_digest")
        != MARGINAL_STATIC_HISTORICAL_DESIGN_EXECUTION_DIGEST
        or execution.get("task_key") != MARGINAL_STATIC_HISTORICAL_DESIGN_TASK_KEY
        or execution.get("task_digest") != MARGINAL_STATIC_HISTORICAL_DESIGN_TASK_DIGEST
        or execution.get("completion_classification") != "VALIDATED_IN_MAINLINE"
        or execution.get("registered_artifact_count") != 5
        or execution.get("formal_historical_folds_executed") != 0
        or execution.get("historical_scores_computed", 0) != 0
        or execution.get("evidence_created") is not False
        or dataset_boundary.get("artifact_digest") != HISTORICAL_DATASET_BOUNDARY_DIGEST
        or walk_forward_design.get("artifact_digest")
        != HISTORICAL_WALK_FORWARD_DESIGN_DIGEST
        or inference_design.get("artifact_digest") != HISTORICAL_INFERENCE_DESIGN_DIGEST
        or completion.get("artifact_digest") != HISTORICAL_DESIGN_COMPLETION_DIGEST
    ):
        raise MarginalStaticHistoricalPreregistrationError(
            "marginal_static_historical_preregistration_design_lineage_invalid"
        )


def _validate_frozen_contract(frozen: Mapping[str, Any]) -> None:
    dataset = frozen.get("dataset")
    folds = frozen.get("folds")
    resampling = frozen.get("resampling")
    inference = frozen.get("inference_algorithms")
    execution = frozen.get("execution")
    time_stability = frozen.get("time_stability")
    if (
        frozen.get("task_key") != MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_KEY
        or frozen.get("capability")
        != MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_CAPABILITY
        or frozen.get("completion_fact")
        != MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_COMPLETION_FACT
        or frozen.get("next_consumer") != MARGINAL_STATIC_HISTORICAL_EXECUTION_TASK_KEY
        or frozen.get("historical_design_execution_digest")
        != MARGINAL_STATIC_HISTORICAL_DESIGN_EXECUTION_DIGEST
        or not isinstance(dataset, Mapping)
        or dataset.get("contract") != "history_snapshot.v1.0.0"
        or dataset.get("issue_count") != HISTORICAL_ISSUE_COUNT
        or dataset.get("database_query_count") != 1
        or dataset.get("legacy_metadata_only_history_identity")
        != LEGACY_METADATA_ONLY_HISTORY_IDENTITY
        or not isinstance(folds, Mapping)
        or folds.get("fold_count") != EVALUATION_FOLD_COUNT
        or folds.get("phase_order") != list(CHECKPOINT_PHASE_ORDER)
        or not isinstance(resampling, Mapping)
        or resampling.get("root_replicates") != ROOT_REPLICATES
        or resampling.get("schemes") != list(RESAMPLING_SCHEMES)
        or resampling.get("child_count") != RESAMPLING_CHILD_COUNT
        or not isinstance(inference, Mapping)
        or inference.get("primary_threshold_bits_per_issue") != 0.01
        or inference.get("family_method") != "Holm"
        or inference.get("missing_branch_p_value") != 1.0
        or not isinstance(execution, Mapping)
        or execution.get("algorithm") != "single_pass_incremental_33_count_vector"
        or execution.get("fold_shard_size") != FOLD_SHARD_SIZE
        or execution.get("fold_shard_count") != FOLD_SHARD_COUNT
        or execution.get("last_fold_shard_size") != LAST_FOLD_SHARD_SIZE
        or execution.get("completion_index_loads") != 1
        or execution.get("duplicate_validation") is not False
        or not isinstance(time_stability, Mapping)
        or time_stability.get("primary_half_counts") != [1291, 1290]
        or time_stability.get("third_counts") != [861, 860, 860]
        or frozen.get("formal_historical_execution_authorized") is not False
    ):
        raise MarginalStaticHistoricalPreregistrationError(
            "marginal_static_historical_preregistration_contract_invalid"
        )


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
        **dict(body),
        "parent_digests": list(parent_digests),
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(identity, domain=domain)
    return payload


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
