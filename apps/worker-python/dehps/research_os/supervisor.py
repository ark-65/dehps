from __future__ import annotations

import json
import math
import os
import subprocess
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.contracts import canonical_digest
from dehps.golden_source_identity import (
    golden_source_identity_from_contract,
    require_golden_source_compatibility,
    validate_golden_source_integrity_contract,
    validate_golden_source_integrity_identity,
)
from dehps.prediction.v2.activation_binding import (
    CUTOVER_TASK_KEY as PREDICTION_V2_CUTOVER_TASK_KEY,
)
from dehps.prediction.v2.activation_binding import (
    PredictionV2ActivationBindingError,
    build_live_activation_attestation,
)
from dehps.prediction.v2.issue_mainline import (
    PredictionV2IssuePostDrawCapability,
    PredictionV2IssuePostDrawReplayCapability,
    PredictionV2IssuePreDrawCapability,
    PredictionV2IssuePreDrawReplayCapability,
)
from dehps.prediction.v2.issues import (
    POST_CAPABILITY as PREDICTION_V2_POST_CAPABILITY,
)
from dehps.prediction.v2.issues import (
    POST_REPLAY_CAPABILITY as PREDICTION_V2_POST_REPLAY_CAPABILITY,
)
from dehps.prediction.v2.issues import (
    PRE_CAPABILITY as PREDICTION_V2_PRE_CAPABILITY,
)
from dehps.prediction.v2.issues import (
    PRE_REPLAY_CAPABILITY as PREDICTION_V2_PRE_REPLAY_CAPABILITY,
)
from dehps.prediction.v2.mainline import (
    CONTROL_PLANE_KEY as PREDICTION_V2_CONTROL_PLANE_KEY,
)
from dehps.prediction.v2.mainline import (
    CUTOVER_CAPABILITY as PREDICTION_V2_CUTOVER_CAPABILITY,
)
from dehps.prediction.v2.mainline import (
    REFERENCE_CAPABILITY as PREDICTION_V2_REFERENCE_CAPABILITY,
)
from dehps.prediction.v2.mainline import (
    REFERENCE_TASK_KEY as PREDICTION_V2_REFERENCE_TASK_KEY,
)
from dehps.prediction.v2.mainline import (
    REPLAY_CAPABILITY as PREDICTION_V2_REPLAY_CAPABILITY,
)
from dehps.prediction.v2.mainline import (
    REPLAY_TASK_KEY as PREDICTION_V2_REPLAY_TASK_KEY,
)
from dehps.prediction.v2.mainline import (
    PredictionV2LiveActivationCapability,
    PredictionV2ReferenceCapability,
    PredictionV2ReplayCapability,
    build_prediction_v2_status,
    build_reference_children,
    build_reference_history,
)
from dehps.prediction.v2.replay import (
    replay_post_draw as replay_prediction_v2_post_draw,
)
from dehps.prediction.v2.replay import replay_pre_draw as replay_prediction_v2_pre_draw
from dehps.research_os.information_theory.calibration import (
    CALIBRATION_RUN_MANIFEST_DIGEST,
    load_calibration_manifest,
    run_p24_calibration,
)
from dehps.research_os.information_theory.calibration.contracts import (
    DECISION_POLICY_DIGEST as P24_DECISION_POLICY_DIGEST,
)
from dehps.research_os.information_theory.calibration.contracts import (
    METRIC_KERNEL_DIGEST as P24_METRIC_KERNEL_DIGEST,
)
from dehps.research_os.information_theory.calibration.contracts import (
    PREREGISTRATION_DIGEST as P24_PREREGISTRATION_DIGEST,
)
from dehps.research_os.information_theory.calibration.contracts import (
    SYNTHETIC_MANIFEST_DIGEST as P24_SYNTHETIC_MANIFEST_DIGEST,
)
from dehps.research_os.information_theory.calibration.contracts import (
    WALK_FORWARD_HARNESS_DIGEST as P24_WALK_FORWARD_HARNESS_DIGEST,
)
from dehps.research_os.information_theory.identifiability import (
    IDENTIFIABILITY_PREFLIGHT_MANIFEST_DIGEST,
    SUPERSEDED_RUN_ARCHIVE_DIGEST,
    load_identifiability_preflight_manifest,
    load_superseded_run_archive,
    run_identifiability_preflight,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    COMPATIBILITY_COMPLETION_FACT,
    COMPATIBILITY_REQUEST_DIGEST,
    COMPATIBILITY_REQUEST_PATH,
    DESIGN_REPLAY_COMPLETION_FACT,
    GATE_REPLAY_FIXTURE_PATH,
    MEASUREMENT_CONTRACT_V2_DIGEST,
    MEASUREMENT_CONTRACT_V2_PATH,
    P261_FROZEN_FIXTURE_DIGEST,
    P261_FROZEN_FIXTURE_PATH,
    P261_MARGINAL_BINDING_CONTRACT_PATH,
    P263_POLICY_DIGEST,
    P263_SLOT_ELIGIBILITY_CAPABILITY,
    P263_SLOT_ELIGIBILITY_FACT,
    P263_SLOT_ELIGIBILITY_TASK_KEY,
    P263_SLOT_SOURCE_CONTRACT_PATH,
    P263_SUPERSEDING_FIXTURE_DIGEST,
    P263_SUPERSEDING_FIXTURE_PATH,
    bind_p261_marginal_acceptance,
    build_branch_decision_replay_artifact,
    build_design_artifacts,
    build_design_replay_artifacts,
    build_measurement_compatibility_acceptance,
    build_p263_slot_eligibility_artifact,
    load_gate_replay_fixture,
    load_measurement_compatibility_fixture,
    load_measurement_compatibility_request,
    load_measurement_contract_v2,
    load_p261_marginal_binding_contract,
    load_p263_slot_source_contract,
    replay_measurement_source_fixture,
    replay_p263_slot_eligibility_artifact,
    validate_p263_slot_eligibility_artifact,
    verify_p263_slot_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.execution import (
    DESIGN_COMPLETION_FACT,
)
from dehps.research_os.information_theory.measurement_system_v2.fixture_freeze import (
    FIXTURE_FREEZE_CAPABILITY,
    FIXTURE_FREEZE_COMPLETION_FACT,
    FIXTURE_FREEZE_SOURCE_CONTRACT_PATH,
    FIXTURE_FREEZE_TASK_KEY,
    build_fixture_freeze_artifacts,
    load_fixture_freeze_source_contract,
    verify_fixture_freeze_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_contract import (
    MARGINAL_STATIC_CONTRACT_FREEZE_CAPABILITY,
    MARGINAL_STATIC_CONTRACT_FREEZE_COMPLETION_FACT,
    MARGINAL_STATIC_CONTRACT_FREEZE_TASK_KEY,
    MARGINAL_STATIC_SOURCE_CONTRACT_PATH,
    build_marginal_static_contract_artifacts,
    load_marginal_static_source_contract,
    verify_marginal_static_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_fixtures import (
    FIXTURE_ORDER as MARGINAL_STATIC_FIXTURE_ORDER,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_fixtures import (
    MARGINAL_STATIC_FIXTURE_FREEZE_CAPABILITY,
    MARGINAL_STATIC_FIXTURE_FREEZE_COMPLETION_FACT,
    MARGINAL_STATIC_FIXTURE_FREEZE_TASK_KEY,
    MARGINAL_STATIC_FIXTURE_SOURCE_CONTRACT_PATH,
    build_marginal_static_fixture_artifacts,
    load_marginal_static_fixture_source_contract,
    verify_marginal_static_fixture_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_health_decision import (
    MARGINAL_STATIC_HEALTH_DECISION_CAPABILITY,
    MARGINAL_STATIC_HEALTH_DECISION_REPAIR_FACT,
    MARGINAL_STATIC_HEALTH_DECISION_SOURCE_CONTRACT_PATH,
    MARGINAL_STATIC_HEALTH_DECISION_TASK_KEY,
    MARGINAL_STATIC_REPAIR_DESIGN_TASK_KEY,
    build_marginal_static_health_decision,
    load_marginal_static_health_decision_source_contract,
    verify_marginal_static_health_decision_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_health_decision import (
    MEASUREMENT_CONTRACT_V2_DIGEST as MARGINAL_STATIC_DECISION_CONTRACT_DIGEST,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_health_design import (
    MARGINAL_STATIC_HEALTH_DESIGN_CAPABILITY,
    MARGINAL_STATIC_HEALTH_DESIGN_COMPLETION_FACT,
    MARGINAL_STATIC_HEALTH_DESIGN_SOURCE_CONTRACT_PATH,
    MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY,
    MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY,
    build_marginal_static_health_design_artifacts,
    load_marginal_static_health_design_source_contract,
    verify_marginal_static_health_design_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_health_execution import (
    MARGINAL_STATIC_HEALTH_EXECUTION_CAPABILITY,
    MARGINAL_STATIC_HEALTH_EXECUTION_COMPLETION_FACT,
    MARGINAL_STATIC_HEALTH_EXECUTION_SOURCE_CONTRACT_PATH,
    MARGINAL_STATIC_HEALTH_PROGRESS_PATH,
    build_replicate_specs,
    execute_health_program,
    load_marginal_static_health_execution_source_contract,
    rebuild_health_artifacts_from_index,
    run_replicate,
    verify_marginal_static_health_execution_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_historical_design import (
    FROZEN_PREREGISTRATION_PATH as MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_PATH,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_historical_design import (
    MARGINAL_STATIC_CONTRACT_TASK_KEY as HISTORICAL_MARGINAL_STATIC_CONTRACT_TASK_KEY,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_historical_design import (
    MARGINAL_STATIC_HISTORICAL_DESIGN_CAPABILITY,
    MARGINAL_STATIC_HISTORICAL_DESIGN_COMPLETION_FACT,
    MARGINAL_STATIC_HISTORICAL_DESIGN_SOURCE_CONTRACT_PATH,
    MARGINAL_STATIC_HISTORICAL_DESIGN_TASK_KEY,
    MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_KEY,
    build_marginal_static_historical_design_artifacts,
    load_marginal_static_historical_design_source_contract,
    verify_marginal_static_historical_design_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_historical_design import (
    MEASUREMENT_CONTRACT_DESIGN_TASK_KEY as HISTORICAL_MEASUREMENT_CONTRACT_DESIGN_TASK_KEY,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_repair_design import (
    MARGINAL_STATIC_REPAIR_DESIGN_CAPABILITY,
    MARGINAL_STATIC_REPAIR_DESIGN_COMPLETION_FACT,
    MARGINAL_STATIC_REPAIR_DESIGN_SOURCE_CONTRACT_PATH,
    MARGINAL_STATIC_REPAIR_PREREGISTRATION_TASK_KEY,
    build_marginal_static_repair_design_artifacts,
    load_marginal_static_repair_design_source_contract,
    verify_marginal_static_repair_design_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_repair_health_decision import (
    MARGINAL_STATIC_REPAIR_HEALTH_DECISION_CAPABILITY,
    MARGINAL_STATIC_REPAIR_HEALTH_DECISION_SOURCE_CONTRACT_PATH,
    MARGINAL_STATIC_REPAIR_HEALTH_DECISION_TASK_KEY,
    build_marginal_static_repair_health_decision,
    load_marginal_static_repair_health_decision_source_contract,
    verify_marginal_static_repair_health_decision_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_repair_health_execution import (
    MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_CAPABILITY,
    MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_COMPLETION_FACT,
    MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_SOURCE_CONTRACT_PATH,
    MARGINAL_STATIC_REPAIR_HEALTH_PROGRESS_PATH,
    execute_repair_health_program,
    load_marginal_static_repair_health_execution_source_contract,
    rebuild_repair_health_artifacts_from_index,
    verify_marginal_static_repair_health_execution_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_repair_preregistration import (
    CALIBRATION_REPLICATES,
    EVALUATION_REPLICATES,
    EXECUTION_SHARD_SIZE,
    EXECUTION_SHARDS,
    MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_TASK_KEY,
    MARGINAL_STATIC_REPAIR_PREREGISTRATION_CAPABILITY,
    MARGINAL_STATIC_REPAIR_PREREGISTRATION_COMPLETION_FACT,
    MARGINAL_STATIC_REPAIR_PREREGISTRATION_SOURCE_CONTRACT_PATH,
    TOTAL_GENERATED_ISSUES,
    TOTAL_OUTER_EVALUATION_ISSUES,
    TOTAL_REPLICATES,
    build_marginal_static_repair_preregistration_artifacts,
    load_marginal_static_repair_preregistration_source_contract,
    verify_marginal_static_repair_preregistration_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_repair_v2_design import (
    MARGINAL_STATIC_REPAIR_V2_DESIGN_CAPABILITY,
    MARGINAL_STATIC_REPAIR_V2_DESIGN_COMPLETION_FACT,
    MARGINAL_STATIC_REPAIR_V2_DESIGN_SOURCE_CONTRACT_PATH,
    MARGINAL_STATIC_REPAIR_V2_DESIGN_TASK_KEY,
    MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_TASK_KEY,
    REPAIR_HEALTH_DECISION_TASK_KEY,
    build_marginal_static_repair_v2_design_artifacts,
    load_marginal_static_repair_v2_design_source_contract,
    verify_marginal_static_repair_v2_design_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_repair_v2_health_decision import (
    MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_CAPABILITY,
    MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_SOURCE_CONTRACT_PATH,
    build_marginal_static_repair_v2_health_decision,
    load_marginal_static_repair_v2_health_decision_source_contract,
    verify_marginal_static_repair_v2_health_decision_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_repair_v2_health_execution import (
    EVALUATION_CHILDREN as REPAIR_V2_EVALUATION_CHILDREN,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_repair_v2_health_execution import (
    MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_TASK_KEY,
    MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_CAPABILITY,
    MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_COMPLETION_FACT,
    MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_SOURCE_CONTRACT_PATH,
    MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_TASK_KEY,
    MARGINAL_STATIC_REPAIR_V2_HEALTH_PROGRESS_PATH,
    execute_repair_v2_health_program,
    load_marginal_static_repair_v2_health_execution_source_contract,
    rebuild_repair_v2_health_artifacts_from_index,
    verify_marginal_static_repair_v2_health_execution_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_repair_v2_health_execution import (
    PLANNED_GENERATED_ISSUES as REPAIR_V2_GENERATED_ISSUES,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_repair_v2_health_execution import (
    PLANNED_OUTER_EVALUATION_ISSUES as REPAIR_V2_OUTER_EVALUATION_ISSUES,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_repair_v2_health_execution import (
    REFERENCE_CHILDREN as REPAIR_V2_REFERENCE_CHILDREN,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_repair_v2_health_execution import (
    SHARD_COUNT as REPAIR_V2_SHARD_COUNT,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_repair_v2_health_execution import (
    SHARD_SIZE as REPAIR_V2_SHARD_SIZE,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_repair_v2_health_execution import (
    TOTAL_CHILDREN as REPAIR_V2_TOTAL_CHILDREN,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_repair_v2_preregistration import (
    MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_CAPABILITY,
    MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_COMPLETION_FACT,
    MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_SOURCE_CONTRACT_PATH,
    build_marginal_static_repair_v2_preregistration_artifacts,
    load_marginal_static_repair_v2_preregistration_source_contract,
    verify_marginal_static_repair_v2_preregistration_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.preflight_design import (
    PREFLIGHT_DESIGN_CAPABILITY,
    PREFLIGHT_DESIGN_COMPLETION_FACT,
    PREFLIGHT_DESIGN_TASK_KEY,
    PREFLIGHT_FIXTURE_FREEZE_TASK_KEY,
    PREFLIGHT_SOURCE_CONTRACT_PATH,
    build_branch_preflight_design_artifacts,
    load_preflight_source_contract,
    verify_preflight_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.preflight_execution import (
    MARGINAL_CONTRACT_FREEZE_TASK_KEY,
    PREFLIGHT_EXECUTION_CAPABILITY,
    PREFLIGHT_EXECUTION_COMPLETION_FACT,
    PREFLIGHT_EXECUTION_PASS_FACT,
    PREFLIGHT_EXECUTION_SOURCE_CONTRACT_PATH,
    PREFLIGHT_EXECUTION_TASK_KEY,
    build_preflight_execution_artifacts,
    load_preflight_execution_source_contract,
    verify_preflight_execution_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.replay import (
    P27_GATE_REPLAY_FACT,
    P261_RAW_REPLAY_FACT,
    build_p27_gate_replay_artifact,
    build_p261_raw_replay_artifact,
)
from dehps.research_os.information_theory.measurement_system_v2.runtime_audit import (
    RUNTIME_AUDIT_PLAN_PATH,
    RuntimeAuditObserver,
    build_benchmark_plan_artifact,
    build_equivalence_attestation,
    build_runtime_benchmark_attempt_artifact,
    load_runtime_audit_plan,
    validate_runtime_benchmark_attempt_artifact,
)
from dehps.research_os.information_theory.measurement_validation import (
    FIXTURE_GIT_COMMIT,
    FIXTURE_PARENT_EXECUTION_ID,
    MEASUREMENT_VALIDATION_MANIFEST_DIGEST,
    PERIODIC_REFIT_CONTRACT_DIGEST,
    REPAIRED_MEASUREMENT_VALIDATION_MANIFEST_DIGEST,
    PythonReferenceEvaluation,
    PythonReferenceReplicateEvaluator,
    StrictPriorFeatureCache,
    assemble_completion,
    build_canonical_executor_fingerprint,
    build_cells,
    build_exact_golden_attestation,
    build_golden_fixture_artifact,
    build_golden_reference_plan_artifact,
    build_reference_boundary_snapshots,
    build_replicate,
    evaluate_automatic_gate,
    full_blind_feature_view_payload_digest,
    full_train_feature_view_payload_digest,
    generate_evaluation_dataset,
    golden_boundary_identity_contract,
    golden_full_replicate,
    load_periodic_refit_contract,
    load_repaired_measurement_validation_manifest,
    locate_repaired_truth_artifacts,
    run_parallel_execution,
    verify_completion_replay,
)
from dehps.research_os.information_theory.measurement_validation.reference import (
    ReferenceReplicateEvaluator,
)
from dehps.research_os.information_theory.measurement_validation.source_integrity import (
    build_source_integrity_attestation,
    construction_source_integrity_identity,
    float64_tree_digest,
    golden_source_integrity_contract,
    golden_source_integrity_identity,
    preflight_source_integrity,
    validate_construction_source_integrity_identity,
    validate_registered_source_integrity_attestation,
    validate_source_integrity_attestation,
)
from dehps.research_os.information_theory.metrics import load_metric_kernel_manifest
from dehps.research_os.information_theory.progress import build_m4_status
from dehps.research_os.information_theory.repair.contracts import (
    MEASUREMENT_REPAIR_MANIFEST_DIGEST,
)
from dehps.research_os.information_theory.repair.execution import (
    REPAIRED_FACT,
    run_measurement_contract_repair,
)
from dehps.research_os.information_theory.resampling import (
    KERNEL_MANIFEST_DIGEST,
    load_resampling_manifest,
    run_p25_resampling,
)
from dehps.research_os.information_theory.resampling.contracts import (
    DECISION_POLICY_DIGEST as P25_DECISION_POLICY_DIGEST,
)
from dehps.research_os.information_theory.resampling.contracts import (
    METRIC_KERNEL_DIGEST as P25_METRIC_KERNEL_DIGEST,
)
from dehps.research_os.information_theory.resampling.contracts import (
    P24_COMPLETION_DIGEST as P25_P24_COMPLETION_DIGEST,
)
from dehps.research_os.information_theory.resampling.contracts import (
    PREREGISTRATION_DIGEST as P25_PREREGISTRATION_DIGEST,
)
from dehps.research_os.information_theory.resampling.contracts import (
    SYNTHETIC_MANIFEST_DIGEST as P25_SYNTHETIC_MANIFEST_DIGEST,
)
from dehps.research_os.information_theory.resampling.contracts import (
    WALK_FORWARD_HARNESS_DIGEST as P25_WALK_FORWARD_HARNESS_DIGEST,
)
from dehps.research_os.information_theory.synthetic import (
    load_synthetic_run_manifest,
)
from dehps.research_os.information_theory.walk_forward import (
    OuterFold,
    load_harness_manifest,
    load_synthetic_dataset,
    restrict_to_training_history,
    run_walk_forward,
)
from dehps.research_os.mainline import (
    completion_execution_ids,
    integration_contract,
    mainline_completion_fact,
)
from dehps.research_os.models import (
    CompletionClassification,
    ControlPlaneManifest,
    MainlineArtifactRegistration,
    MainlineExecutionEvent,
    ResearchOSValidationError,
    Task,
    TaskStatus,
    stable_hash,
)
from dehps.research_os.repository import PostgresResearchOSRepository
from dehps.source_version import resolve_git_commit

P23_TASK_KEY = "m4-p2-walk-forward-probe-harness"
P23_CAPABILITY = "m4_p2_3_walk_forward_harness"
P23_PROBES = (
    "THEORETICAL_BASELINE",
    "REGULARIZED_LOGISTIC_REGRESSION",
)
P24_TASK_KEY = "m4-p2-injected-signal-calibration"
P24_CAPABILITY = "m4_p2_4_injected_signal_calibration"
P25_TASK_KEY = "m4-p2-resampling"
P25_CAPABILITY = "m4_p2_5_resampling_and_negative_controls"
P26_PREFLIGHT_TASK_KEY = "m4-p2-measurement-identifiability-preflight"
P26_PREFLIGHT_CAPABILITY = "m4_p2_6_identifiability_preflight"
P26_REPAIR_TASK_KEY = "m4-p2-repair-measurement-system"
P26_REPAIR_CAPABILITY = "m4_p2_measurement_system_repair"
P26_TASK_KEY = "m4-p2-false-positive-and-power-runs"
P26_LEGACY_CAPABILITY = "m4_p2_6_1_false_positive_and_power"
P26_CAPABILITY = "m4_p2_6_3_periodic_refit_false_positive_and_power"
P27_TASK_KEY = "m4-p2-automatic-gate-and-report"
P27_CAPABILITY = "m4_p2_7_automatic_measurement_gate"
M4_P263_COMPATIBILITY_TASK_KEY = "m4-p2-6-3-superseding-compatibility-acceptance"
M4_P263_COMPATIBILITY_CAPABILITY = "m4_p2_6_3_superseding_compatibility_acceptance"
M4_V2_DESIGN_TASK_KEY = "m4-v2-measurement-contract-design"
M4_V2_DESIGN_CAPABILITY = "m4_v2_measurement_contract_design"
M4_V2_DESIGN_REPLAY_TASK_KEY = "m4-v2-measurement-contract-design-replay"
M4_V2_DESIGN_REPLAY_CAPABILITY = "m4_v2_measurement_contract_design_replay"
M4_V2_P261_RAW_REPLAY_TASK_KEY = "m4-v2-p2-6-1-raw-execution-replay"
M4_V2_P261_RAW_REPLAY_CAPABILITY = "m4_v2_p2_6_1_raw_execution_replay"
M4_V2_P27_GATE_REPLAY_TASK_KEY = "m4-v2-p2-7-measurement-gate-replay"
M4_V2_P27_GATE_REPLAY_CAPABILITY = "m4_v2_p2_7_measurement_gate_replay"
M4_V2_MARGINAL_BINDING_TASK_KEY = "m4-v2-p2-6-1-marginal-binding"
M4_V2_MARGINAL_BINDING_CAPABILITY = "m4_v2_p2_6_1_marginal_binding"
M4_V2_MARGINAL_DECISION_REPLAY_TASK_KEY = "m4-v2-p2-6-1-marginal-decision-replay"
M4_V2_MARGINAL_DECISION_REPLAY_CAPABILITY = "m4_v2_p2_6_1_marginal_decision_replay"
MARGINAL_BINDING_COMPLETION_FACT = (
    "m4-v2-marginal-measurement-acceptance-decision:BOUND"
)
MARGINAL_DECISION_REPLAY_FACT = "m4-v2-branch-decision-replay:MARGINAL_STATIC:VERIFIED"
M4_P29_P261_GOLDEN_REFERENCE_TASK_KEY = "m4-p2-9-golden-reference-freeze"
M4_P29_P261_RUNTIME_AUDIT_TASK_KEY = "m4-p2-9-measurement-runtime-audit"
M4_P29_P263_FAILED_RUNTIME_AUDIT_TASK_KEY = "m4-p2-9-p263-measurement-runtime-audit"
M4_P29_GOLDEN_REFERENCE_TASK_KEY = "m4-p2-9-p263-golden-reference-freeze"
M4_P29_GOLDEN_REFERENCE_CAPABILITY = "m4_p2_9_p263_golden_reference_freeze"
M4_P29_GOLDEN_REFERENCE_COMPLETION_FACT = "m4-p2-9-p263-golden-reference:VERIFIED"
M4_P261_FROZEN_TASK_DIGEST = (
    "80068e22f5e1c343fd86213faa0d9a411d71f92ad2750fed10449a10151de8fa"
)
M4_P263_TASK_DIGEST = "85a08402a4a0c37f75ee1675f4970ef00a7a0b0992b4204251c0c2cc79324de4"
M4_P29_RUNTIME_AUDIT_TASK_KEY = "m4-p2-9-p263-runtime-observation-arithmetic-fix"
M4_P29_RUNTIME_AUDIT_CAPABILITY = "m4_p2_9_p263_runtime_observation_arithmetic_fix"
M4_P29_RUNTIME_AUDIT_COMPLETION_FACT = (
    "m4-p2-9-p263-runtime-audit-arithmetic-fix:VERIFIED"
)
M4_P29_ACCELERATION_BOUNDARY_SCOPE = "literal_behavior_path_and_fresh_import_closure"
P2_UMBRELLA_TASK_KEY = "m4-p2-synthetic-measurement-validation"
M4_CONTROL_PLANE_KEY = "m4-information-theory-mainline"

_TASK_ARTIFACT_NAMESPACE_BY_CONTROL_PLANE = {
    M4_CONTROL_PLANE_KEY: "mainline",
    PREDICTION_V2_CONTROL_PLANE_KEY: "prediction-v2-shadow",
}
MAINLINE_EXECUTION_SCHEMA = "dehps-research-os-mainline-execution.v1"
P26_EQUIVALENT_RESUME_ENV = "DEHPS_P26_EQUIVALENT_RESUME_FROM_COMMIT"
P26_EQUIVALENT_RESUME_REPORT_ENV = "DEHPS_P26_EQUIVALENT_RESUME_REPORT"
P26_EQUIVALENT_RESUME_REPORT = (
    "docs/experiments/2026-07-31-m4-p2-6-exact-runtime-acceleration.md"
)
P26_FAILED_RECOVERY_EVENT_ENV = "DEHPS_P26_RECOVER_FAILED_EVENT_DIGEST"
P26_FAILED_RECOVERY_REPORT_ENV = "DEHPS_P26_FAILED_RECOVERY_REPORT"
P26_FAILED_RECOVERY_EVENT_DIGEST = (
    "c003525e63c6570f74dbde06c2cb8ed67e79886829c7a4be52f13f2bede9544e"
)
P26_FAILED_RECOVERY_EXECUTION_ID = (
    "cd64aacc48c5e1dac4f84d7f644e92384b50f37299b1643631b7ee872ab452b3"
)
P26_FAILED_RECOVERY_RUNNING_MANIFEST_DIGEST = (
    "dd9a2a0106fe17787cb57a6293bd1e9eea9cb8c30771f6a7e27b0ecc30c18ce3"
)
P26_FAILED_RECOVERY_ERROR = (
    "repaired_measurement_validation_truth_missing: repaired truth is unavailable: "
    "42e9ab014ca479f7b46f360cebc556dae6eb4bbc9df81a9e07e9217689ba9f20"
)


class MainlineSupervisorError(RuntimeError):
    pass


@dataclass(frozen=True)
class CapabilityResult:
    execution_artifact: Mapping[str, Any]
    execution_artifact_path: Path
    registrations: tuple[MainlineArtifactRegistration, ...]
    completion_facts: tuple[str, ...] = ()
    additional_completed_task_keys: tuple[str, ...] = ()


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise MainlineSupervisorError(f"artifact is not an object: {path}")
    return value


def _persist_immutable(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists():
        if _load_object(path) != dict(payload):
            raise MainlineSupervisorError(f"immutable artifact collision: {path}")
        return
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )


def _verify_v2_registered_artifacts(
    *,
    root_dir: Path,
    registrations: list[Mapping[str, Any]],
    expected_payloads: tuple[Mapping[str, Any], ...],
) -> None:
    expected_by_digest = {
        str(payload["artifact_digest"]): dict(payload) for payload in expected_payloads
    }
    registered_digests = {
        str(item.get("artifact_digest") or "") for item in registrations
    }
    if len(expected_by_digest) != len(expected_payloads) or registered_digests != set(
        expected_by_digest
    ):
        raise MainlineSupervisorError(
            "M4 Measurement Contract v2 registered artifact set changed"
        )
    for registration in registrations:
        digest = str(registration.get("artifact_digest") or "")
        path = root_dir / str(registration.get("artifact_path") or "")
        actual = _load_object(path)
        expected = expected_by_digest[digest]
        if (
            actual != expected
            or actual.get("artifact_digest") != digest
            or actual.get("artifact_type") != registration.get("artifact_type")
        ):
            raise MainlineSupervisorError(
                "M4 Measurement Contract v2 registered artifact content changed"
            )


def _artifact_digest(payload: Mapping[str, Any]) -> str:
    for field in (
        "artifact_digest",
        "fold_digest",
        "feature_view_digest",
        "state_digest",
    ):
        value = payload.get(field)
        if isinstance(value, str) and len(value) == 64:
            return value
    raise MainlineSupervisorError("registered artifact has no digest identity")


def _typed_artifact(
    payload: Mapping[str, Any],
    *,
    artifact_type: str,
    parent_digests: tuple[str, ...],
    domain: str,
) -> dict[str, Any]:
    artifact: dict[str, Any] = {
        "artifact_type": artifact_type,
        "artifact_digest": "",
        **dict(payload),
        "parent_digests": list(parent_digests),
    }
    identity = dict(artifact)
    identity.pop("artifact_digest")
    artifact["artifact_digest"] = canonical_digest(identity, domain=domain)
    return artifact


def _event_record(event: Mapping[str, Any]) -> MainlineExecutionEvent:
    raw_payload = event.get("payload")
    if not isinstance(raw_payload, (list, tuple)) or any(
        not isinstance(item, (list, tuple)) or len(item) != 2 for item in raw_payload
    ):
        raise MainlineSupervisorError("mainline execution event payload changed")
    expected_fields = {
        "event_digest",
        "execution_id",
        "control_plane_key",
        "manifest_digest",
        "task_key",
        "task_digest",
        "capability",
        "event_type",
        "sequence",
        "recorded_at",
        "payload",
    }
    if set(event) != expected_fields:
        raise MainlineSupervisorError("mainline execution event shape changed")
    record = MainlineExecutionEvent(
        execution_id=str(event.get("execution_id") or ""),
        control_plane_key=str(event.get("control_plane_key") or ""),
        manifest_digest=str(event.get("manifest_digest") or ""),
        task_key=str(event.get("task_key") or ""),
        task_digest=str(event.get("task_digest") or ""),
        capability=str(event.get("capability") or ""),
        event_type=str(event.get("event_type") or ""),
        sequence=int(event.get("sequence", -1)),
        recorded_at=str(event.get("recorded_at") or ""),
        payload=tuple((str(item[0]), item[1]) for item in raw_payload),
    )
    if event.get("event_digest") != record.artifact_digest:
        raise MainlineSupervisorError("mainline execution event digest changed")
    return record


def _registration_record(
    registration: Mapping[str, Any],
) -> MainlineArtifactRegistration:
    expected_fields = {
        "registration_digest",
        "execution_id",
        "control_plane_key",
        "task_key",
        "task_digest",
        "artifact_digest",
        "artifact_type",
        "schema_version",
        "artifact_path",
        "parent_digests",
        "git_commit",
    }
    raw_parents = registration.get("parent_digests")
    if set(registration) != expected_fields or not isinstance(
        raw_parents, (list, tuple)
    ):
        raise MainlineSupervisorError("mainline artifact registration shape changed")
    record = MainlineArtifactRegistration(
        execution_id=str(registration.get("execution_id") or ""),
        control_plane_key=str(registration.get("control_plane_key") or ""),
        task_key=str(registration.get("task_key") or ""),
        task_digest=str(registration.get("task_digest") or ""),
        artifact_digest=str(registration.get("artifact_digest") or ""),
        artifact_type=str(registration.get("artifact_type") or ""),
        schema_version=str(registration.get("schema_version") or ""),
        artifact_path=str(registration.get("artifact_path") or ""),
        parent_digests=tuple(str(value) for value in raw_parents),
        git_commit=str(registration.get("git_commit") or ""),
    )
    if registration.get("registration_digest") != record.registration_digest:
        raise MainlineSupervisorError("mainline artifact registration digest changed")
    return record


def _canonical_task_artifact_path(
    *,
    root_dir: Path,
    control_plane_key: str,
    task_key: str,
    execution_id: str,
    relative_path: str,
) -> Path:
    raw = Path(relative_path)
    if (
        not relative_path
        or raw.is_absolute()
        or ".." in raw.parts
        or raw.as_posix() != relative_path
    ):
        raise MainlineSupervisorError("mainline artifact path is not canonical")
    try:
        artifact_namespace = _TASK_ARTIFACT_NAMESPACE_BY_CONTROL_PLANE[
            control_plane_key
        ]
    except KeyError as exc:
        raise MainlineSupervisorError(
            "mainline artifact control plane is not registered"
        ) from exc
    repository_root = root_dir.resolve()
    # A clean code worktree may intentionally bind its top-level runtime entry
    # to the canonical same-host runtime root.  Resolve that one boundary first,
    # then keep every namespace, task, execution, and artifact check anchored to
    # the resulting real path.  Symlinks below the bound runtime root remain
    # forbidden by the existing equality and containment checks.
    runtime_root = (repository_root / "runtime").resolve()
    namespace_root = runtime_root / "research-os" / artifact_namespace / "tasks"
    if namespace_root.resolve() != namespace_root:
        raise MainlineSupervisorError("mainline artifact path escaped task namespace")
    task_root = namespace_root / task_key / execution_id
    if task_root.resolve() != task_root:
        raise MainlineSupervisorError("mainline artifact path escaped task execution")
    path = (repository_root / raw).resolve()
    if not path.is_relative_to(task_root):
        raise MainlineSupervisorError("mainline artifact path escaped task execution")
    return path


def _load_single_completed_execution(
    *,
    repository: PostgresResearchOSRepository,
    root_dir: Path,
    control_plane_key: str,
    task_key: str,
    require_manifest_complete: bool = True,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    manifest = repository.load_manifest(control_plane_key=control_plane_key)
    matching_tasks = [task for task in manifest.tasks if task.task_key == task_key]
    if len(matching_tasks) != 1:
        raise MainlineSupervisorError(
            f"mainline parent is not in the current manifest: {task_key}"
        )
    task = matching_tasks[0]
    state = manifest.task_state_by_digest[task.artifact_digest]
    state_is_valid = (
        state.declared_status is TaskStatus.COMPLETED
        and state.completion_classification is CompletionClassification.COMPLETE
        if require_manifest_complete
        else state.declared_status is TaskStatus.RUNNING
        and state.completion_classification
        in {
            CompletionClassification.INTEGRATED,
            CompletionClassification.VALIDATED_IN_MAINLINE,
        }
    )
    if task.requested_capability is None or not state_is_valid:
        raise MainlineSupervisorError(
            f"mainline parent is not canonically complete: {task_key}"
        )
    events = repository.list_mainline_execution_events(
        control_plane_key=control_plane_key,
        task_key=task_key,
    )
    completed = [
        dict(event) for event in events if event.get("event_type") == "completed"
    ]
    if len(completed) != 1:
        raise MainlineSupervisorError(
            f"mainline parent requires one completed execution: {task_key}"
        )
    event = completed[0]
    completed_record = _event_record(event)
    matching_started = [
        dict(candidate)
        for candidate in events
        if candidate.get("event_type") == "started"
        and candidate.get("execution_id") == completed_record.execution_id
    ]
    matching_failed = [
        dict(candidate)
        for candidate in events
        if candidate.get("event_type") == "failed"
        and candidate.get("execution_id") == completed_record.execution_id
    ]
    recovered_p26_failure = (
        task_key == P26_TASK_KEY
        and len(matching_failed) == 1
        and str(matching_failed[0].get("event_digest") or "")
        == P26_FAILED_RECOVERY_EVENT_DIGEST
        and _event_record(matching_failed[0]).sequence == 1
        and _event_payload(matching_failed[0])
        == {
            "error": P26_FAILED_RECOVERY_ERROR,
            "git_commit": "e6dedaf9c835672a5e17007653ee6e8fe55b67d9",
        }
    )
    expected_completed_sequence = 2 if recovered_p26_failure else 1
    if len(matching_started) != 1:
        raise MainlineSupervisorError(
            f"mainline parent requires one matching started event: {task_key}"
        )
    started = matching_started[0]
    started_record = _event_record(started)
    if (
        completed_record.control_plane_key != control_plane_key
        or completed_record.task_key != task_key
        or completed_record.task_digest != task.artifact_digest
        or completed_record.capability != task.requested_capability
        or completed_record.event_type != "completed"
        or completed_record.sequence != expected_completed_sequence
        or (matching_failed and not recovered_p26_failure)
        or (
            not require_manifest_complete
            and completed_record.manifest_digest
            != (
                P26_FAILED_RECOVERY_RUNNING_MANIFEST_DIGEST
                if recovered_p26_failure
                else manifest.artifact_digest
            )
        )
        or started_record.execution_id != completed_record.execution_id
        or started_record.control_plane_key != control_plane_key
        or started_record.manifest_digest != completed_record.manifest_digest
        or started_record.task_key != task_key
        or started_record.task_digest != task.artifact_digest
        or started_record.capability != task.requested_capability
        or started_record.event_type != "started"
        or started_record.sequence != 0
    ):
        raise MainlineSupervisorError(
            f"mainline parent event provenance changed: {task_key}"
        )
    summary = _event_payload(event)
    started_summary = _event_payload(started)
    execution_relative_path = str(summary.get("execution_artifact_path") or "")
    path = _canonical_task_artifact_path(
        root_dir=root_dir,
        control_plane_key=control_plane_key,
        task_key=task_key,
        execution_id=completed_record.execution_id,
        relative_path=execution_relative_path,
    )
    execution = _load_object(path)
    expected = canonical_digest(
        {key: value for key, value in execution.items() if key != "artifact_digest"},
        domain="dehps.research-os.mainline-execution.v1",
    )
    expected_execution_id = stable_hash(
        {
            "schema": MAINLINE_EXECUTION_SCHEMA,
            "control_plane_key": control_plane_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "input_artifact_digests": task.input_artifact_digests,
            "git_commit": execution.get("git_commit"),
        }
    )
    if (
        execution.get("artifact_digest") != expected
        or execution.get("task_key") != task_key
        or execution.get("task_digest") != task.artifact_digest
        or execution.get("goal_key") != task.goal_key
        or execution.get("capability") != task.requested_capability
        or execution.get("control_plane_key") != control_plane_key
        or execution.get("execution_id") != completed_record.execution_id
        or execution.get("execution_id") != expected_execution_id
        or execution.get("status") != "COMPLETE"
        or execution.get("completion_classification") != "VALIDATED_IN_MAINLINE"
        or execution.get("input_artifact_digests") != list(task.input_artifact_digests)
        or summary.get("execution_artifact_digest") != execution.get("artifact_digest")
        or summary.get("execution_artifact_path") != execution_relative_path
        or summary.get("git_commit") != execution.get("git_commit")
        or started_summary.get("git_commit") != execution.get("git_commit")
        or started_summary.get("input_artifact_digests")
        != list(task.input_artifact_digests)
        or summary.get("actual_fold_count") != execution.get("actual_fold_count")
        or (
            require_manifest_complete
            and mainline_completion_fact(
                task=task,
                execution_id=completed_record.execution_id,
            )
            not in manifest.facts.artifacts
        )
    ):
        raise MainlineSupervisorError(
            f"completed execution identity changed: {task_key}"
        )
    registrations = [
        dict(item)
        for item in repository.list_mainline_artifacts(
            control_plane_key=control_plane_key,
            execution_id=str(execution["execution_id"]),
        )
    ]
    try:
        summary_count = int(summary.get("registered_artifact_count"))
        execution_count = (
            summary_count
            if control_plane_key == PREDICTION_V2_CONTROL_PLANE_KEY
            and "registered_artifact_count" not in execution
            else int(execution.get("registered_artifact_count"))
        )
    except (TypeError, ValueError) as exc:
        raise MainlineSupervisorError(
            f"completed execution registry count changed: {task_key}"
        ) from exc
    if len(registrations) != summary_count or len(registrations) != execution_count:
        raise MainlineSupervisorError(
            f"completed execution registry changed: {task_key}"
        )
    registration_digests: set[str] = set()
    registration_paths: set[str] = set()
    execution_registrations: list[MainlineArtifactRegistration] = []
    for item in registrations:
        record = _registration_record(item)
        if (
            record.execution_id != completed_record.execution_id
            or record.control_plane_key != control_plane_key
            or record.task_key != task_key
            or record.task_digest != task.artifact_digest
            or record.registration_digest in registration_digests
            or record.artifact_path in registration_paths
        ):
            raise MainlineSupervisorError(
                f"completed execution registration provenance changed: {task_key}"
            )
        artifact_path = _canonical_task_artifact_path(
            root_dir=root_dir,
            control_plane_key=control_plane_key,
            task_key=task_key,
            execution_id=completed_record.execution_id,
            relative_path=record.artifact_path,
        )
        if not artifact_path.is_file():
            raise MainlineSupervisorError(
                f"completed execution artifact missing: {task_key}"
            )
        artifact = _load_object(artifact_path)
        expected_registration_git = str(
            artifact.get("runtime_git_commit") or execution.get("git_commit") or ""
        )
        if (
            _artifact_digest(artifact) != record.artifact_digest
            or str(artifact.get("artifact_type") or "typed_artifact")
            != record.artifact_type
            or str(artifact.get("schema_version") or "unknown") != record.schema_version
            or tuple(str(value) for value in artifact.get("parent_digests", ()))
            != record.parent_digests
            or record.git_commit != expected_registration_git
        ):
            raise MainlineSupervisorError(
                f"completed execution registered artifact changed: {task_key}"
            )
        registration_digests.add(record.registration_digest)
        registration_paths.add(record.artifact_path)
        if record.artifact_type == "research_os_mainline_execution":
            execution_registrations.append(record)
    if (
        len(execution_registrations) != 1
        or execution_registrations[0].artifact_digest
        != execution.get("artifact_digest")
        or execution_registrations[0].artifact_path != execution_relative_path
    ):
        raise MainlineSupervisorError(
            f"completed execution artifact registration changed: {task_key}"
        )
    return event, execution, registrations


def _load_registered_type(
    *,
    root_dir: Path,
    registrations: list[dict[str, Any]],
    artifact_type: str,
) -> dict[str, Any]:
    matches = [
        item for item in registrations if item.get("artifact_type") == artifact_type
    ]
    if len(matches) != 1:
        raise MainlineSupervisorError(
            f"registered artifact type is not unique: {artifact_type}"
        )
    payload = _load_object(root_dir / str(matches[0]["artifact_path"]))
    if payload.get("artifact_type") != artifact_type or payload.get(
        "artifact_digest"
    ) != matches[0].get("artifact_digest"):
        raise MainlineSupervisorError(
            f"registered artifact content identity changed: {artifact_type}"
        )
    return payload


def _load_registered_type_group(
    *,
    root_dir: Path,
    registrations: list[dict[str, Any]],
    artifact_type: str,
) -> tuple[dict[str, Any], ...]:
    matches = [
        item for item in registrations if item.get("artifact_type") == artifact_type
    ]
    if not matches:
        raise MainlineSupervisorError(
            f"registered artifact type is missing: {artifact_type}"
        )
    payloads = tuple(
        _load_object(root_dir / str(item["artifact_path"])) for item in matches
    )
    if any(
        payload.get("artifact_type") != artifact_type
        or payload.get("artifact_digest") != registration.get("artifact_digest")
        for payload, registration in zip(payloads, matches, strict=True)
    ):
        raise MainlineSupervisorError(
            f"registered artifact group content identity changed: {artifact_type}"
        )
    return payloads


def _persist_small_capability(
    *,
    root_dir: Path,
    owner: Any,
    control_plane_key: str,
    task: Task,
    execution_id: str,
    git_commit: str,
    child_name: str,
    child_filename: str,
    child_payload: Mapping[str, Any],
    completion_fact: str,
    downstream_consumer: str,
    extra_execution: Mapping[str, Any],
) -> CapabilityResult:
    task_dir = (
        root_dir / "runtime/research-os/mainline/tasks" / task.task_key / execution_id
    )
    child_path = (
        task_dir
        / "artifacts"
        / child_name
        / str(child_payload["artifact_digest"])
        / child_filename
    )
    _persist_immutable(child_path, child_payload)
    execution_payload: dict[str, Any] = {
        "schema_version": MAINLINE_EXECUTION_SCHEMA,
        "artifact_type": "research_os_mainline_execution",
        "artifact_digest": "",
        "execution_id": execution_id,
        "control_plane_key": control_plane_key,
        "goal_key": task.goal_key,
        "task_key": task.task_key,
        "task_digest": task.artifact_digest,
        "capability": task.requested_capability,
        "status": "COMPLETE",
        "completion_classification": "VALIDATED_IN_MAINLINE",
        "input_artifact_digests": list(task.input_artifact_digests),
        "completion_fact": completion_fact,
        "actual_fold_count": 0,
        "registered_artifact_count": 2,
        "historical_outcomes_read": False,
        "p2_6_1_partial_statistical_results_read": False,
        "evidence_created": False,
        "evidence_progress_before": 0,
        "evidence_progress_after": 0,
        "downstream_consumer": downstream_consumer,
        "production_impact": "none",
        "git_commit": git_commit,
        "working_tree_clean": True,
        **dict(extra_execution),
        "parent_digests": [
            *task.input_artifact_digests,
            str(child_payload["artifact_digest"]),
        ],
    }
    identity = dict(execution_payload)
    identity.pop("artifact_digest")
    execution_payload["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.research-os.mainline-execution.v1",
    )
    execution_path = task_dir / "execution.json"
    _persist_immutable(execution_path, execution_payload)
    registrations = P24InjectedSignalCalibrationCapability._registrations(
        owner,
        control_plane_key=control_plane_key,
        task=task,
        execution_id=execution_id,
        git_commit=git_commit,
        child_payloads=((child_path, child_payload),),
        execution_path=execution_path,
        execution_payload=execution_payload,
    )
    return CapabilityResult(
        execution_artifact=execution_payload,
        execution_artifact_path=execution_path,
        registrations=registrations,
        completion_facts=(completion_fact,),
    )


def _runtime_audit_child_identities(
    replicate_payload: Mapping[str, Any],
) -> list[dict[str, str]]:
    children = [
        {
            "artifact_type": f"probe_run:{probe_id}",
            "artifact_digest": str(digest),
        }
        for probe_id, digest in sorted(
            dict(replicate_payload["probe_run_digests"]).items()
        )
    ]
    for field in (
        "dataset_digest",
        "ordered_outer_checkpoint_digest",
        "ordered_settlement_digest",
        "checkpoint_journal_digest",
        "bootstrap_seed_set_digest",
        "permutation_seed_set_digest",
    ):
        children.append(
            {
                "artifact_type": field,
                "artifact_digest": str(replicate_payload[field]),
            }
        )
    return children


@dataclass(frozen=True)
class _GoldenReferenceBundle:
    plan: Mapping[str, Any]
    fixture: Mapping[str, Any]
    replay: Mapping[str, Any]
    runtime_audit_plan: Mapping[str, Any]
    expected_input_digests: tuple[str, ...]
    reference_fold_count: int
    observed_fold_count: int
    reference_boundary_snapshot_count: int
    observed_boundary_snapshot_count: int
    equivalence_boundary_case_count: int


def _golden_execution_work_counts(
    bundle: _GoldenReferenceBundle,
) -> dict[str, int]:
    counts = (
        bundle.reference_fold_count,
        bundle.observed_fold_count,
        bundle.reference_boundary_snapshot_count,
        bundle.observed_boundary_snapshot_count,
        bundle.equivalence_boundary_case_count,
    )
    if counts != (61, 61, 45, 45, 45):
        raise MainlineSupervisorError("golden reference work counts changed")
    return {
        "actual_fold_count": (bundle.reference_fold_count + bundle.observed_fold_count),
        "reference_full_replicate_fold_count": bundle.reference_fold_count,
        "observed_full_replicate_fold_count": bundle.observed_fold_count,
        "reference_boundary_snapshot_count": (bundle.reference_boundary_snapshot_count),
        "observed_boundary_snapshot_count": (bundle.observed_boundary_snapshot_count),
        "equivalence_boundary_case_count": bundle.equivalence_boundary_case_count,
    }


def _golden_reference_sources(
    *,
    root_dir: Path,
) -> tuple[
    Mapping[str, Any],
    Any,
    Any,
    Mapping[str, Mapping[str, Any]],
    tuple[str, ...],
]:
    runtime_plan = load_runtime_audit_plan(root_dir / RUNTIME_AUDIT_PLAN_PATH)
    manifest = load_repaired_measurement_validation_manifest(
        root_dir / "configs/research-os/"
        "m4-information-theory-p2-6-1-measurement-validation-v1.json"
    )
    synthetic = load_synthetic_run_manifest(
        root_dir / "configs/research-os/"
        "m4-information-theory-p2-synthetic-run-manifest-v1.0.1.json"
    )
    truth_digests = tuple(
        str(item["artifact_digest"]) for item in manifest.payload["truth_artifacts"]
    )
    truths = locate_repaired_truth_artifacts(
        root_dir,
        required_digests=truth_digests,
        repair_manifest_digest=MEASUREMENT_REPAIR_MANIFEST_DIGEST,
    )
    preregistration = _load_object(
        root_dir
        / "configs/research-os/m4-information-theory-preregistration-v1.0.3.json"
    )
    resampling = _load_object(
        root_dir / "configs/research-os/"
        "m4-information-theory-p2-5-resampling-kernel-v1.json"
    )
    metric = _load_object(
        root_dir / "configs/research-os/m4-information-theory-metric-kernel-v1.json"
    )
    harness = _load_object(
        root_dir
        / "configs/research-os/m4-information-theory-walk-forward-harness-v1.json"
    )
    expected_inputs = (
        str(runtime_plan["artifact_digest"]),
        M4_P263_TASK_DIGEST,
        PERIODIC_REFIT_CONTRACT_DIGEST,
        COMPATIBILITY_REQUEST_DIGEST,
        P263_SUPERSEDING_FIXTURE_DIGEST,
        MEASUREMENT_REPAIR_MANIFEST_DIGEST,
        manifest.artifact_digest,
        str(manifest.payload["development_selection_artifact_digest"]),
        str(manifest.payload["state_visible_feature_manifest_digest"]),
        synthetic.artifact_digest,
        str(preregistration["artifact_digest"]),
        str(resampling["artifact_digest"]),
        str(metric["artifact_digest"]),
        str(harness["artifact_digest"]),
        *truth_digests,
    )
    if len(set(expected_inputs)) != len(expected_inputs):
        raise MainlineSupervisorError("golden reference source identities overlap")
    return runtime_plan, manifest, synthetic, truths, expected_inputs


def _observed_reference_evaluation(
    *,
    root_dir: Path,
    output_dir: Path,
    manifest: Any,
    synthetic: Any,
    truths: Mapping[str, Mapping[str, Any]],
    replicate: Any,
    periodic_refit_contract: Any | None = None,
    observer: RuntimeAuditObserver | None = None,
    capture_trace: bool = True,
) -> PythonReferenceEvaluation:
    trace_records: list[dict[str, Any]] | None = [] if capture_trace else None
    evaluator = ReferenceReplicateEvaluator.from_paths(
        manifest=manifest,
        synthetic=synthetic,
        preregistration_path=(
            root_dir
            / "configs/research-os/m4-information-theory-preregistration-v1.0.3.json"
        ),
        walk_forward_harness_path=(
            root_dir
            / "configs/research-os/m4-information-theory-walk-forward-harness-v1.json"
        ),
        resampling_path=(
            root_dir / "configs/research-os/"
            "m4-information-theory-p2-5-resampling-kernel-v1.json"
        ),
        truth_by_scenario=truths,
        git_commit=FIXTURE_GIT_COMMIT,
        output_dir=output_dir,
        periodic_refit_contract=periodic_refit_contract,
        audit_observer=observer,
        trace_records=trace_records,
    )
    result = dict(evaluator.evaluate(replicate))
    if observer is not None:
        observer.stop()
    journal_relative = Path(str(result["checkpoint_journal_path"]))
    if journal_relative.is_absolute() or ".." in journal_relative.parts:
        raise MainlineSupervisorError("golden reference journal path escaped work dir")
    journal_path = output_dir / journal_relative
    if not journal_path.is_file():
        raise MainlineSupervisorError("golden reference observed journal is missing")
    return PythonReferenceEvaluation(
        result_payload=result,
        fold_traces=tuple(trace_records or ()),
        checkpoint_journal_bytes=journal_path.read_bytes(),
    )


def _require_exact_runtime_correctness_replay(
    *,
    measured: PythonReferenceEvaluation,
    correctness: PythonReferenceEvaluation,
) -> None:
    if measured.fold_traces:
        raise MainlineSupervisorError(
            "runtime audit measured run unexpectedly captured trace records"
        )
    if len(correctness.fold_traces) != 61:
        raise MainlineSupervisorError(
            "runtime audit correctness replay trace count changed"
        )
    measured_digest = float64_tree_digest(
        measured.result_payload,
        domain="dehps.m4.p2-9.measured-correctness-result.v1",
    )
    correctness_digest = float64_tree_digest(
        correctness.result_payload,
        domain="dehps.m4.p2-9.measured-correctness-result.v1",
    )
    if measured_digest != correctness_digest:
        raise MainlineSupervisorError(
            "runtime audit production-like result changed during correctness replay"
        )
    if measured.checkpoint_journal_bytes != correctness.checkpoint_journal_bytes:
        raise MainlineSupervisorError(
            "runtime audit production-like journal changed during correctness replay"
        )


def _prepare_fresh_runtime_audit_attempt(
    *,
    task_dir: Path,
    execution_id: str,
) -> tuple[str, Path, Path]:
    legacy_workdir = task_dir / "audited-work"
    if legacy_workdir.exists():
        raise MainlineSupervisorError(
            "runtime audit legacy measured workdir already exists"
        )
    attempts_root = task_dir / "benchmark-attempts"
    existing = (
        sorted(item for item in attempts_root.iterdir())
        if attempts_root.exists()
        else []
    )
    if any(not item.is_dir() for item in existing):
        raise MainlineSupervisorError(
            "runtime audit attempt root contains a non-directory entry"
        )
    expected_existing = {
        stable_hash(
            {
                "schema": "dehps-m4-p2-9-runtime-audit-attempt.v1",
                "execution_id": execution_id,
                "attempt_sequence": sequence,
            }
        )
        for sequence in range(len(existing))
    }
    if {item.name for item in existing} != expected_existing:
        raise MainlineSupervisorError("runtime audit existing attempt identity changed")
    attempt_id = stable_hash(
        {
            "schema": "dehps-m4-p2-9-runtime-audit-attempt.v1",
            "execution_id": execution_id,
            "attempt_sequence": len(existing),
        }
    )
    attempt_dir = attempts_root / attempt_id
    measured_workdir = attempt_dir / "production-like-measured"
    correctness_workdir = attempt_dir / "correctness-replay"
    if (
        attempt_dir.exists()
        or measured_workdir.exists()
        or correctness_workdir.exists()
    ):
        raise MainlineSupervisorError(
            "runtime audit selected attempt workdir is not fresh"
        )
    return attempt_id, measured_workdir, correctness_workdir


def _validate_runtime_benchmark_attempt_files(
    *,
    root_dir: Path,
    control_plane_key: str,
    task_key: str,
    execution_id: str,
    attempt: Mapping[str, Any],
) -> bytes:
    attempt_id = str(attempt.get("benchmark_attempt_id") or "")
    expected_attempt_path = (
        f"runtime/research-os/mainline/tasks/{task_key}/{execution_id}/"
        f"benchmark-attempts/{attempt_id}"
    )
    expected_measured_path = f"{expected_attempt_path}/production-like-measured"
    expected_correctness_path = f"{expected_attempt_path}/correctness-replay"
    if (
        not attempt_id
        or attempt.get("benchmark_attempt_path") != expected_attempt_path
        or attempt.get("measured_workdir_path") != expected_measured_path
        or attempt.get("correctness_replay_workdir_path") != expected_correctness_path
    ):
        raise MainlineSupervisorError(
            "runtime benchmark attempt workdir identity changed"
        )
    measured_root = _canonical_task_artifact_path(
        root_dir=root_dir,
        control_plane_key=control_plane_key,
        task_key=task_key,
        execution_id=execution_id,
        relative_path=expected_measured_path,
    )
    correctness_root = _canonical_task_artifact_path(
        root_dir=root_dir,
        control_plane_key=control_plane_key,
        task_key=task_key,
        execution_id=execution_id,
        relative_path=expected_correctness_path,
    )
    journal_relative_text = str(
        attempt.get("measured_checkpoint_journal_relative_path") or ""
    )
    journal_relative = Path(journal_relative_text)
    if (
        not journal_relative_text
        or journal_relative.is_absolute()
        or ".." in journal_relative.parts
        or journal_relative.as_posix() != journal_relative_text
    ):
        raise MainlineSupervisorError(
            "runtime benchmark attempt journal path is not canonical"
        )
    measured_journal_path = measured_root / journal_relative
    correctness_journal_path = correctness_root / journal_relative
    try:
        measured_bytes = measured_journal_path.read_bytes()
        correctness_bytes = correctness_journal_path.read_bytes()
    except OSError as exc:
        raise MainlineSupervisorError(
            "runtime benchmark attempt journal file is missing"
        ) from exc
    if (
        measured_bytes != correctness_bytes
        or measured_bytes
        != str(attempt.get("measured_checkpoint_journal_utf8") or "").encode("utf-8")
        or sha256(measured_bytes).hexdigest()
        != attempt.get("measured_checkpoint_journal_sha256")
    ):
        raise MainlineSupervisorError("runtime benchmark attempt journal bytes changed")
    return measured_bytes


def _build_observed_boundary_snapshots(
    *,
    manifest: Any,
    synthetic: Any,
    truths: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    expected_outer_lengths = {
        "FORWARD_61": 61,
        "HISTORICAL": 2581,
        "LONG": 6062,
    }
    cells = {
        (cell.scale_id, cell.scenario_id): cell
        for cell in build_cells(manifest, synthetic)
    }
    observed: list[dict[str, Any]] = []
    active_key: tuple[str, str] | None = None
    active: tuple[Any, Any, Any] | None = None
    for identity in golden_boundary_identity_contract():
        key = (str(identity["scale_id"]), str(identity["scenario_id"]))
        if key not in cells:
            raise MainlineSupervisorError(
                "golden observed boundary cell is not in the frozen schedule"
            )
        if key != active_key:
            cell = cells[key]
            replicate = build_replicate(
                cell=cell,
                replicate_index=0,
                parent_execution_id=FIXTURE_PARENT_EXECUTION_ID,
            )
            dataset = generate_evaluation_dataset(
                replicate,
                synthetic=synthetic,
                truth_artifact=truths.get(cell.scenario_id),
                expose_prior_state=True,
            )
            active = (
                replicate,
                dataset,
                StrictPriorFeatureCache(dataset, include_prior_state=True),
            )
            active_key = key
        if active is None:
            raise MainlineSupervisorError(
                "golden observed boundary state was not initialized"
            )
        replicate, dataset, cache = active
        fold_index = int(identity["fold_index"])
        if fold_index < 0 or fold_index >= dataset.outer_evaluation_length:
            raise MainlineSupervisorError(
                "golden observed boundary fold escaped the frozen scale"
            )
        test_issue = int(identity["test_issue"])
        expected_test_issue = dataset.minimum_training_length + 1 + fold_index
        fold = OuterFold(tuple(range(1, test_issue)), test_issue)
        if (
            cells[key].mechanism != identity["mechanism"]
            or cells[key].signal_strength != identity["signal_strength"]
            or dataset.outer_evaluation_length != expected_outer_lengths.get(key[0])
        ):
            raise MainlineSupervisorError(
                "golden observed boundary scale contract changed"
            )
        if (
            test_issue != expected_test_issue
            or fold.train_issues[0] != identity["train_start_issue"]
            or fold.train_issues[-1] != identity["train_end_issue"]
            or fold.test_issue != identity["test_issue"]
        ):
            raise MainlineSupervisorError(
                "golden observed boundary identity contract changed"
            )
        training = restrict_to_training_history(
            dataset,
            available_through_issue=fold.train_issues[-1],
        )
        cache.reveal_training_history(
            training,
            through_issue=fold.train_issues[-1],
        )
        train = cache.build_train_feature_view(training, fold.train_issues)
        blind = cache.build_blind_test_feature_view(target_issue=fold.test_issue)
        observed.append(
            {
                "scale_id": key[0],
                "scenario_id": key[1],
                "mechanism": cells[key].mechanism,
                "signal_strength": cells[key].signal_strength,
                "replicate_index": replicate.replicate_index,
                "replicate_digest": replicate.artifact_digest,
                "dataset_digest": dataset.artifact_digest,
                "fold_position": identity["fold_position"],
                "fold_index": fold_index,
                "train_start_issue": fold.train_issues[0],
                "train_end_issue": fold.train_issues[-1],
                "test_issue": fold.test_issue,
                "train_feature_view_digest": train.feature_view_digest,
                "blind_feature_view_digest": blind.feature_view_digest,
                "train_feature_view_payload_digest": (
                    full_train_feature_view_payload_digest(train)
                ),
                "blind_feature_view_payload_digest": (
                    full_blind_feature_view_payload_digest(blind)
                ),
            }
        )
    if len(observed) != 45:
        raise MainlineSupervisorError("golden observed boundary snapshot count changed")
    return tuple(observed)


def _build_golden_reference_bundle(
    *,
    root_dir: Path,
    work_dir: Path,
    observer: RuntimeAuditObserver | None = None,
) -> _GoldenReferenceBundle:
    (
        runtime_plan,
        manifest,
        synthetic,
        truths,
        expected_inputs,
    ) = _golden_reference_sources(root_dir=root_dir)
    periodic_refit_contract = load_periodic_refit_contract(
        root_dir
        / "configs/research-os/m4-information-theory-p2-6-3-periodic-refit-v1.json"
    )
    verified_construction_source_identity = preflight_source_integrity(
        root_dir=root_dir,
        runtime_plan=runtime_plan,
    )
    verified_golden_source_contract = golden_source_integrity_contract(runtime_plan)
    verified_golden_source_identity = golden_source_integrity_identity(runtime_plan)
    executor_fingerprint = build_canonical_executor_fingerprint()
    plan = build_golden_reference_plan_artifact(
        runtime_plan,
        executor_fingerprint=executor_fingerprint,
        construction_source_integrity_identity=(verified_construction_source_identity),
    )
    if (
        plan.get("construction_source_integrity_identity")
        != verified_construction_source_identity
        or plan.get("golden_source_integrity_contract")
        != verified_golden_source_contract
        or plan.get("golden_source_integrity_identity")
        != verified_golden_source_identity
    ):
        raise MainlineSupervisorError(
            "golden reference source integrity preflight changed"
        )
    replicate = golden_full_replicate(manifest=manifest, synthetic=synthetic)
    boundaries = build_reference_boundary_snapshots(
        manifest=manifest,
        synthetic=synthetic,
        truth_by_scenario=truths,
    )
    reference_evaluation = PythonReferenceReplicateEvaluator.from_paths(
        manifest=manifest,
        synthetic=synthetic,
        preregistration_path=(
            root_dir
            / "configs/research-os/m4-information-theory-preregistration-v1.0.3.json"
        ),
        walk_forward_harness_path=(
            root_dir
            / "configs/research-os/m4-information-theory-walk-forward-harness-v1.json"
        ),
        resampling_path=(
            root_dir / "configs/research-os/"
            "m4-information-theory-p2-5-resampling-kernel-v1.json"
        ),
        truth_by_scenario=truths,
        fixture_git_commit=FIXTURE_GIT_COMMIT,
        output_dir=work_dir / "literal-oracle",
        periodic_refit_contract=periodic_refit_contract,
    ).evaluate(replicate)
    reference_fixture = build_golden_fixture_artifact(
        plan_digest=str(plan["artifact_digest"]),
        replicate=replicate,
        evaluation=reference_evaluation,
        boundary_snapshots=boundaries,
        parent_digests=expected_inputs,
        executor_fingerprint_digest=str(plan["executor_fingerprint_digest"]),
        golden_source_integrity_identity=verified_golden_source_identity,
    )
    observed_evaluation = _observed_reference_evaluation(
        root_dir=root_dir,
        output_dir=work_dir / "observed-backend",
        manifest=manifest,
        synthetic=synthetic,
        truths=truths,
        replicate=replicate,
        periodic_refit_contract=periodic_refit_contract,
        observer=observer,
    )
    observed_boundaries = _build_observed_boundary_snapshots(
        manifest=manifest,
        synthetic=synthetic,
        truths=truths,
    )
    observed_fixture = build_golden_fixture_artifact(
        plan_digest=str(plan["artifact_digest"]),
        replicate=replicate,
        evaluation=observed_evaluation,
        boundary_snapshots=observed_boundaries,
        parent_digests=expected_inputs,
        executor_fingerprint_digest=str(plan["executor_fingerprint_digest"]),
        golden_source_integrity_identity=verified_golden_source_identity,
    )
    if build_canonical_executor_fingerprint() != plan["executor_fingerprint"]:
        raise MainlineSupervisorError(
            "golden reference executor fingerprint changed during construction"
        )
    replay = build_exact_golden_attestation(
        plan_digest=str(plan["artifact_digest"]),
        reference_payload=reference_fixture,
        observed_payload=observed_fixture,
        reference_journal_bytes=reference_evaluation.checkpoint_journal_bytes,
        observed_journal_bytes=observed_evaluation.checkpoint_journal_bytes,
    )
    return _GoldenReferenceBundle(
        plan=plan,
        fixture=reference_fixture,
        replay=replay,
        runtime_audit_plan=runtime_plan,
        expected_input_digests=expected_inputs,
        reference_fold_count=int(
            reference_evaluation.result_payload["actual_outer_fold_count"]
        ),
        observed_fold_count=int(
            observed_evaluation.result_payload["actual_outer_fold_count"]
        ),
        reference_boundary_snapshot_count=len(boundaries),
        observed_boundary_snapshot_count=len(observed_boundaries),
        equivalence_boundary_case_count=len(boundaries),
    )


def _verify_typed_digest(
    payload: Mapping[str, Any],
    *,
    artifact_type: str,
    domain: str,
) -> None:
    identity = dict(payload)
    digest = identity.pop("artifact_digest", None)
    if payload.get("artifact_type") != artifact_type or digest != canonical_digest(
        identity, domain=domain
    ):
        raise MainlineSupervisorError(
            f"golden reference artifact identity changed: {artifact_type}"
        )


def _validate_golden_boundary_schedule(plan: Mapping[str, Any]) -> None:
    boundary_suite = plan.get("boundary_suite")
    expected_identities = [
        dict(identity) for identity in golden_boundary_identity_contract()
    ]
    expected_schedule_digest = canonical_digest(
        expected_identities,
        domain="dehps.m4-p2-9.golden-boundary-identity-schedule.v1",
    )
    if (
        not isinstance(boundary_suite, Mapping)
        or set(boundary_suite)
        != {
            "replicate_index",
            "scales",
            "mechanisms",
            "fold_positions",
            "identity_count",
            "identity_schedule_digest",
            "identities",
        }
        or boundary_suite.get("replicate_index") != 0
        or boundary_suite.get("scales") != ["FORWARD_61", "HISTORICAL", "LONG"]
        or boundary_suite.get("mechanisms")
        != [
            "uniform_choose_6_without_replacement_from_33",
            "single_number_conditional_shift",
            "local_temporal_state",
            "pair_conditional_signal",
            "marginal_preserving_conditional_signal",
        ]
        or boundary_suite.get("fold_positions") != ["first", "middle", "last"]
        or boundary_suite.get("identities") != expected_identities
        or boundary_suite.get("identity_count") != len(expected_identities)
        or len(expected_identities) != 45
        or boundary_suite.get("identity_schedule_digest") != expected_schedule_digest
    ):
        raise MainlineSupervisorError(
            "golden reference boundary identity schedule changed"
        )


def _validate_golden_artifact_set(
    *,
    plan: Mapping[str, Any],
    fixture: Mapping[str, Any],
    replay: Mapping[str, Any],
    expected_source_inputs: tuple[str, ...] | None = None,
    expected_construction_source_identity: Mapping[str, Any] | None = None,
    expected_golden_source_identity: Mapping[str, Any] | None = None,
) -> None:
    current_executor_fingerprint = build_canonical_executor_fingerprint()
    oracle_contract = plan.get("oracle_contract")
    replicate_result = fixture.get("replicate_result")
    _verify_typed_digest(
        plan,
        artifact_type="GoldenReferencePlanArtifact",
        domain="dehps.m4-p2-9.phase0-golden-plan.v1",
    )
    _verify_typed_digest(
        fixture,
        artifact_type="Phase0GoldenReferenceFixture.v1",
        domain="dehps.m4-p2-9.phase0-golden-fixture.v1",
    )
    _verify_typed_digest(
        replay,
        artifact_type="GoldenReferenceReplayArtifact",
        domain="dehps.m4-p2-9.phase0-golden-replay.v1",
    )
    _validate_golden_boundary_schedule(plan)
    try:
        construction_source_identity = validate_construction_source_integrity_identity(
            plan.get("construction_source_integrity_identity")
        )
        embedded_golden_contract = validate_golden_source_integrity_contract(
            plan.get("golden_source_integrity_contract")
        )
        embedded_golden_identity = validate_golden_source_integrity_identity(
            plan.get("golden_source_integrity_identity")
        )
    except RuntimeError as exc:
        raise MainlineSupervisorError(
            f"golden reference source contract changed: {exc}"
        ) from exc
    if golden_source_identity_from_contract(
        embedded_golden_contract
    ) != embedded_golden_identity or any(
        construction_source_identity[key] != embedded_golden_identity[key]
        for key in (
            "shared_frozen_source_set_digest",
            "independent_oracle_source_set_digest",
        )
    ):
        raise MainlineSupervisorError(
            "golden reference source identity projection changed"
        )
    if (
        fixture.get("benchmark_plan_digest") != plan.get("artifact_digest")
        or replay.get("benchmark_plan_digest") != plan.get("artifact_digest")
        or replay.get("fixture_artifact_digest") != fixture.get("artifact_digest")
        or replay.get("reference_fixture_digest") != fixture.get("artifact_digest")
        or replay.get("observed_fixture_digest") != fixture.get("artifact_digest")
        or plan.get("executor_fingerprint") != current_executor_fingerprint
        or plan.get("executor_fingerprint_digest")
        != current_executor_fingerprint["artifact_digest"]
        or plan.get("exact_replay_scope") != "same_canonical_executor_fingerprint_only"
        or not isinstance(oracle_contract, Mapping)
        or oracle_contract.get("acceleration_boundary_independence_scope")
        != M4_P29_ACCELERATION_BOUNDARY_SCOPE
        or oracle_contract.get("oracle_construction_process_isolated") is not False
        or fixture.get("executor_fingerprint_digest")
        != plan.get("executor_fingerprint_digest")
        or fixture.get("exact_replay_scope")
        != "same_canonical_executor_fingerprint_only"
        or replay.get("executor_fingerprint_digest")
        != plan.get("executor_fingerprint_digest")
        or replay.get("exact_replay_scope")
        != "same_canonical_executor_fingerprint_only"
        or replay.get("status") != "EXACT_GOLDEN_REPLAY_VERIFIED"
        or replay.get("immutable_golden_fixture_is_oracle") is not True
        or replay.get("acceleration_boundary_independent") is not True
        or replay.get("acceleration_boundary_independence_scope")
        != M4_P29_ACCELERATION_BOUNDARY_SCOPE
        or replay.get("oracle_construction_process_isolated") is not False
        or replay.get("oracle_construction_fully_implementation_independent")
        is not False
        or replay.get("payload_exact") is not True
        or replay.get("float_bits_exact") is not True
        or replay.get("journal_bytes_exact") is not True
        or fixture.get("golden_source_integrity_identity") != embedded_golden_identity
        or replay.get("golden_source_integrity_identity") != embedded_golden_identity
        or (
            expected_construction_source_identity is not None
            and construction_source_identity
            != dict(expected_construction_source_identity)
        )
        or (
            expected_golden_source_identity is not None
            and embedded_golden_identity != dict(expected_golden_source_identity)
        )
        or fixture.get("immutable_golden_fixture_is_oracle") is not True
        or fixture.get("acceleration_boundary_independent") is not True
        or fixture.get("acceleration_boundary_independence_scope")
        != M4_P29_ACCELERATION_BOUNDARY_SCOPE
        or fixture.get("oracle_construction_process_isolated") is not False
        or fixture.get("oracle_construction_fully_implementation_independent")
        is not False
        or fixture.get("historical_outcomes_read") is not False
        or not isinstance(replicate_result, Mapping)
        or replicate_result.get("measurement_update_policy_digest")
        != PERIODIC_REFIT_CONTRACT_DIGEST
        or replicate_result.get("learned_probe_refit_interval_folds") != 64
        or replicate_result.get("learned_probe_refit_boundary_count") != 1
        or replicate_result.get("empirical_baseline_update_count") != 61
        or fixture.get("evidence_progress_before") != 0
        or fixture.get("evidence_progress_after") != 0
        or fixture.get("production_action") != "none"
    ):
        raise MainlineSupervisorError("golden reference verification contract changed")
    if expected_source_inputs is not None:
        runtime_plan_digest = expected_source_inputs[0]
        construction_source_digests = tuple(construction_source_identity.values())
        golden_source_digests = tuple(embedded_golden_identity.values())
        expected_fixture_parents = tuple(
            sorted(
                {
                    str(plan["artifact_digest"]),
                    *expected_source_inputs,
                    *golden_source_digests,
                }
            )
        )
        journal_digest = fixture.get("checkpoint_journal_bytes_sha256")
        if (
            plan.get("source_runtime_audit_plan_digest") != runtime_plan_digest
            or plan.get("parent_digests")
            != sorted(
                {
                    runtime_plan_digest,
                    *construction_source_digests,
                    *golden_source_digests,
                }
            )
            or tuple(sorted(str(value) for value in fixture.get("parent_digests", ())))
            != expected_fixture_parents
            or replay.get("checkpoint_journal_bytes_sha256") != journal_digest
            or replay.get("parent_digests")
            != sorted(
                {
                    plan.get("artifact_digest"),
                    fixture.get("artifact_digest"),
                    journal_digest,
                    *golden_source_digests,
                }
            )
        ):
            raise MainlineSupervisorError("golden reference source lineage changed")


def _load_verified_golden_parent(
    *,
    repository: PostgresResearchOSRepository,
    root_dir: Path,
    control_plane_key: str,
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    event, execution, registrations = _load_single_completed_execution(
        repository=repository,
        root_dir=root_dir,
        control_plane_key=control_plane_key,
        task_key=M4_P29_GOLDEN_REFERENCE_TASK_KEY,
    )
    summary = _event_payload(event)
    manifest = repository.load_manifest(control_plane_key=control_plane_key)
    golden_tasks = [
        task
        for task in manifest.tasks
        if task.task_key == M4_P29_GOLDEN_REFERENCE_TASK_KEY
    ]
    if len(golden_tasks) != 1:
        raise MainlineSupervisorError(
            "golden reference task is not unique in the current manifest"
        )
    execution_completion_fact = mainline_completion_fact(
        task=golden_tasks[0],
        execution_id=str(execution["execution_id"]),
    )
    if (
        M4_P29_GOLDEN_REFERENCE_COMPLETION_FACT
        not in tuple(str(value) for value in summary.get("completion_facts", ()))
        or M4_P29_GOLDEN_REFERENCE_COMPLETION_FACT not in manifest.facts.artifacts
        or execution_completion_fact not in manifest.facts.artifacts
        or execution.get("completion_fact") != M4_P29_GOLDEN_REFERENCE_COMPLETION_FACT
        or execution.get("immutable_golden_fixture_is_oracle") is not True
        or execution.get("acceleration_boundary_independent") is not True
        or execution.get("acceleration_boundary_independence_scope")
        != M4_P29_ACCELERATION_BOUNDARY_SCOPE
        or execution.get("oracle_construction_process_isolated") is not False
        or execution.get("oracle_construction_fully_implementation_independent")
        is not False
        or execution.get("exact_replay_verified") is not True
        or execution.get("historical_outcomes_read") is not False
        or execution.get("measurement_update_policy_digest")
        != PERIODIC_REFIT_CONTRACT_DIGEST
        or execution.get("p2_6_3_task_digest") != M4_P263_TASK_DIGEST
        or execution.get("evidence_progress_before") != 0
        or execution.get("evidence_progress_after") != 0
        or execution.get("production_action") != "none"
    ):
        raise MainlineSupervisorError(
            "golden reference completion fact is not bound to its execution"
        )
    registered_types = {str(item.get("artifact_type") or "") for item in registrations}
    if registered_types != {
        "GoldenReferencePlanArtifact",
        "Phase0GoldenReferenceFixture.v1",
        "GoldenReferenceReplayArtifact",
        "SourceIntegrityAttestationArtifact",
        "research_os_mainline_execution",
    }:
        raise MainlineSupervisorError(
            "golden reference registered artifact set changed"
        )
    plan = _load_registered_type(
        root_dir=root_dir,
        registrations=registrations,
        artifact_type="GoldenReferencePlanArtifact",
    )
    fixture = _load_registered_type(
        root_dir=root_dir,
        registrations=registrations,
        artifact_type="Phase0GoldenReferenceFixture.v1",
    )
    replay = _load_registered_type(
        root_dir=root_dir,
        registrations=registrations,
        artifact_type="GoldenReferenceReplayArtifact",
    )
    source_integrity = _load_registered_type(
        root_dir=root_dir,
        registrations=registrations,
        artifact_type="SourceIntegrityAttestationArtifact",
    )
    raw_expected_inputs = execution.get("input_artifact_digests")
    if not isinstance(raw_expected_inputs, list) or not raw_expected_inputs:
        raise MainlineSupervisorError(
            "golden reference execution source inputs changed"
        )
    expected_inputs = tuple(str(value) for value in raw_expected_inputs)
    _validate_golden_artifact_set(
        plan=plan,
        fixture=fixture,
        replay=replay,
        expected_source_inputs=expected_inputs,
    )
    validate_registered_source_integrity_attestation(
        source_integrity,
        source_runtime_audit_plan_digest=str(plan["source_runtime_audit_plan_digest"]),
        construction_source_identity=plan["construction_source_integrity_identity"],
        golden_source_identity=plan["golden_source_integrity_identity"],
        execution_id=str(execution["execution_id"]),
        git_commit=str(execution["git_commit"]),
        baseline_git_commit=str(
            plan["golden_source_integrity_contract"]["baseline_git_commit"]
        ),
        exact_fixture_replay_artifact_digest=str(replay["artifact_digest"]),
    )
    if (
        execution.get("source_integrity_attestation_artifact_digest")
        != source_integrity["artifact_digest"]
        or execution.get("shared_frozen_source_modified") is not False
        or execution.get("backend_source_modified")
        is not source_integrity["backend_source_modified"]
        or execution.get("acceleration_changed_paths")
        != source_integrity["acceleration_changed_paths"]
        or execution.get("backend_optimization_applied") is not False
        or execution.get("statistical_semantics_modified") is not False
        or execution.get("input_artifact_digests") != list(expected_inputs)
        or execution.get("golden_reference_plan_artifact_digest")
        != plan["artifact_digest"]
        or execution.get("golden_reference_fixture_artifact_digest")
        != fixture["artifact_digest"]
        or execution.get("golden_reference_replay_artifact_digest")
        != replay["artifact_digest"]
    ):
        raise MainlineSupervisorError("golden reference execution lineage changed")
    return execution, registrations, plan, fixture, replay, source_integrity


def _build_runtime_golden_equivalence(
    *,
    benchmark_plan: Mapping[str, Any],
    golden_execution: Mapping[str, Any],
    golden_plan: Mapping[str, Any],
    golden_fixture: Mapping[str, Any],
    golden_replay: Mapping[str, Any],
    observed_fixture: Mapping[str, Any],
    audited_payload: Mapping[str, Any],
    benchmark_attempt: Mapping[str, Any],
    source_integrity: Mapping[str, Any],
    golden_source_integrity: Mapping[str, Any],
) -> dict[str, Any]:
    reference_children = _runtime_audit_child_identities(
        dict(golden_fixture["replicate_result"])
    )
    audited_children = _runtime_audit_child_identities(audited_payload)
    equivalence = build_equivalence_attestation(
        plan_digest=str(benchmark_plan["artifact_digest"]),
        reference_payload=golden_fixture,
        audited_payload=observed_fixture,
        reference_child_artifacts=reference_children,
        audited_child_artifacts=audited_children,
    )
    identity = dict(equivalence)
    identity.pop("artifact_digest")
    identity.update(
        {
            "reference_evaluator_is_oracle": False,
            "immutable_golden_fixture_is_oracle": True,
            "acceleration_boundary_independent": True,
            "acceleration_boundary_independence_scope": (
                M4_P29_ACCELERATION_BOUNDARY_SCOPE
            ),
            "oracle_construction_process_isolated": False,
            "oracle_construction_fully_implementation_independent": False,
            "golden_reference_execution_artifact_digest": golden_execution[
                "artifact_digest"
            ],
            "golden_reference_plan_artifact_digest": golden_plan["artifact_digest"],
            "golden_reference_fixture_artifact_digest": golden_fixture[
                "artifact_digest"
            ],
            "golden_reference_replay_artifact_digest": golden_replay["artifact_digest"],
            "golden_source_integrity_attestation_artifact_digest": (
                golden_source_integrity["artifact_digest"]
            ),
            "golden_source_integrity_identity": golden_fixture[
                "golden_source_integrity_identity"
            ],
            "exact_golden_replay_verified": True,
            "runtime_benchmark_attempt_artifact_digest": benchmark_attempt[
                "artifact_digest"
            ],
            "measured_result_float64_tree_digest": benchmark_attempt[
                "measured_result_float64_tree_digest"
            ],
            "measured_checkpoint_journal_sha256": benchmark_attempt[
                "measured_checkpoint_journal_sha256"
            ],
            "source_integrity_attestation_artifact_digest": source_integrity[
                "artifact_digest"
            ],
            "shared_frozen_source_set_digest": source_integrity[
                "shared_frozen_source_set_digest"
            ],
            "approved_acceleration_source_set_digest": source_integrity[
                "approved_acceleration_source_set_digest"
            ],
            "parent_digests": [
                benchmark_plan["artifact_digest"],
                golden_execution["artifact_digest"],
                golden_plan["artifact_digest"],
                golden_fixture["artifact_digest"],
                golden_replay["artifact_digest"],
                golden_source_integrity["artifact_digest"],
                benchmark_attempt["artifact_digest"],
                source_integrity["artifact_digest"],
            ],
        }
    )
    return {
        **identity,
        "artifact_digest": canonical_digest(
            identity,
            domain="dehps.m4.p2-9.equivalence-attestation.v1",
        ),
    }


def _recover_runtime_audit_commit_marker(
    *,
    root_dir: Path,
    owner: Any,
    control_plane_key: str,
    task: Task,
    execution_id: str,
    git_commit: str,
    task_dir: Path,
    runtime_plan: Mapping[str, Any],
    golden_execution: Mapping[str, Any],
    golden_plan: Mapping[str, Any],
    golden_fixture: Mapping[str, Any],
    golden_replay: Mapping[str, Any],
    golden_source_integrity: Mapping[str, Any],
    compatible_golden_source_identity: Mapping[str, Any],
) -> CapabilityResult | None:
    """Recover the durable result after execution.json crossed commit boundary."""

    execution_path = task_dir / "execution.json"
    if not execution_path.exists():
        return None
    execution = _load_object(execution_path)
    _verify_typed_digest(
        execution,
        artifact_type="research_os_mainline_execution",
        domain="dehps.research-os.mainline-execution.v1",
    )

    def load_child(
        *,
        directory: str,
        filename: str,
        digest_field: str,
        artifact_type: str,
    ) -> tuple[Path, dict[str, Any]]:
        digest = str(execution.get(digest_field) or "")
        path = task_dir / "artifacts" / directory / digest / filename
        if not path.is_file():
            raise MainlineSupervisorError(
                f"runtime audit commit marker child missing: {artifact_type}"
            )
        payload = _load_object(path)
        if (
            payload.get("artifact_type") != artifact_type
            or payload.get("artifact_digest") != digest
        ):
            raise MainlineSupervisorError(
                f"runtime audit commit marker child changed: {artifact_type}"
            )
        return path, payload

    benchmark_plan_path, benchmark_plan = load_child(
        directory="benchmark-plan",
        filename="plan.json",
        digest_field="benchmark_plan_artifact_digest",
        artifact_type="BenchmarkPlanArtifact",
    )
    observation_path, observation = load_child(
        directory="runtime-observation",
        filename="observation.json",
        digest_field="runtime_observation_artifact_digest",
        artifact_type="RuntimeObservationArtifact",
    )
    attempt_path, benchmark_attempt = load_child(
        directory="runtime-benchmark-attempt",
        filename="attempt.json",
        digest_field="runtime_benchmark_attempt_artifact_digest",
        artifact_type="RuntimeBenchmarkAttemptArtifact",
    )
    equivalence_path, equivalence = load_child(
        directory="equivalence-attestation",
        filename="attestation.json",
        digest_field="equivalence_attestation_artifact_digest",
        artifact_type="EquivalenceAttestationArtifact",
    )
    source_path, source_integrity = load_child(
        directory="source-integrity-attestation",
        filename="attestation.json",
        digest_field="source_integrity_attestation_artifact_digest",
        artifact_type="SourceIntegrityAttestationArtifact",
    )
    child_payloads: tuple[tuple[Path, Mapping[str, Any]], ...] = (
        (benchmark_plan_path, benchmark_plan),
        (observation_path, observation),
        (attempt_path, benchmark_attempt),
        (equivalence_path, equivalence),
        (source_path, source_integrity),
    )

    expected_benchmark_plan = build_benchmark_plan_artifact(runtime_plan)
    current_fingerprint = build_canonical_executor_fingerprint()
    if (
        benchmark_plan != expected_benchmark_plan
        or current_fingerprint != golden_plan.get("executor_fingerprint")
    ):
        raise MainlineSupervisorError("runtime audit commit marker environment changed")
    _validate_runtime_observation(
        observation,
        benchmark_plan=benchmark_plan,
        execution_id=execution_id,
        git_commit=git_commit,
        executor_fingerprint_digest=str(golden_plan["executor_fingerprint_digest"]),
        benchmark_attempt_id=str(benchmark_attempt["benchmark_attempt_id"]),
        measured_result_float64_tree_digest=str(
            benchmark_attempt["measured_result_float64_tree_digest"]
        ),
        measured_checkpoint_journal_sha256=str(
            benchmark_attempt["measured_checkpoint_journal_sha256"]
        ),
    )
    validate_runtime_benchmark_attempt_artifact(
        benchmark_attempt,
        benchmark_plan_digest=str(benchmark_plan["artifact_digest"]),
        observation=observation,
        execution_id=execution_id,
        git_commit=git_commit,
    )
    measured_journal_bytes = _validate_runtime_benchmark_attempt_files(
        root_dir=root_dir,
        control_plane_key=control_plane_key,
        task_key=task.task_key,
        execution_id=execution_id,
        attempt=benchmark_attempt,
    )
    reconstructed_source = build_source_integrity_attestation(
        root_dir=root_dir,
        runtime_plan=runtime_plan,
        execution_id=execution_id,
        git_commit=git_commit,
        exact_fixture_replay_artifact_digest=str(golden_replay["artifact_digest"]),
        golden_reference_execution_artifact_digest=str(
            golden_execution["artifact_digest"]
        ),
        golden_source_identity=compatible_golden_source_identity,
    )
    validate_source_integrity_attestation(
        source_integrity,
        runtime_plan=runtime_plan,
        execution_id=execution_id,
        git_commit=git_commit,
        exact_fixture_replay_artifact_digest=str(golden_replay["artifact_digest"]),
        golden_reference_execution_artifact_digest=str(
            golden_execution["artifact_digest"]
        ),
        golden_source_identity=compatible_golden_source_identity,
    )
    reconstructed_equivalence = _build_runtime_golden_equivalence(
        benchmark_plan=benchmark_plan,
        golden_execution=golden_execution,
        golden_plan=golden_plan,
        golden_fixture=golden_fixture,
        golden_replay=golden_replay,
        observed_fixture=golden_fixture,
        audited_payload=dict(benchmark_attempt["measured_result_payload"]),
        benchmark_attempt=benchmark_attempt,
        source_integrity=source_integrity,
        golden_source_integrity=golden_source_integrity,
    )
    expected_parent_digests = [
        *task.input_artifact_digests,
        golden_execution["artifact_digest"],
        golden_plan["artifact_digest"],
        golden_fixture["artifact_digest"],
        golden_replay["artifact_digest"],
        golden_source_integrity["artifact_digest"],
        *(str(payload["artifact_digest"]) for _, payload in child_payloads),
    ]
    expected_execution_fields = {
        "schema_version",
        "artifact_type",
        "artifact_digest",
        "execution_id",
        "control_plane_key",
        "goal_key",
        "task_key",
        "task_digest",
        "capability",
        "status",
        "completion_classification",
        "input_artifact_digests",
        "benchmark_plan_artifact_digest",
        "runtime_observation_artifact_digest",
        "runtime_benchmark_attempt_artifact_digest",
        "source_integrity_attestation_artifact_digest",
        "golden_source_integrity_attestation_artifact_digest",
        "runtime_executor_fingerprint_digest_before",
        "runtime_executor_fingerprint_digest_after",
        "equivalence_attestation_artifact_digest",
        "completion_fact",
        "actual_fold_count",
        "audited_fold_count",
        "correctness_replay_fold_count",
        "total_execution_fold_count",
        "correctness_boundary_snapshot_count",
        "frozen_reference_fold_count",
        "registered_artifact_count",
        "benchmark_attempt_id",
        "benchmark_attempt_path",
        "measured_workdir_path",
        "correctness_replay_workdir_path",
        "journal_reused",
        "fresh_workdir",
        "worker_count",
        "formal_benchmark_after_p263_compatibility",
        "reference_evaluator_is_oracle",
        "immutable_golden_fixture_is_oracle",
        "acceleration_boundary_independent",
        "acceleration_boundary_independence_scope",
        "oracle_construction_process_isolated",
        "oracle_construction_fully_implementation_independent",
        "golden_reference_execution_artifact_digest",
        "golden_reference_plan_artifact_digest",
        "golden_reference_fixture_artifact_digest",
        "golden_reference_replay_artifact_digest",
        "exact_golden_replay_verified",
        "shared_frozen_source_modified",
        "backend_source_modified",
        "acceleration_changed_paths",
        "backend_optimization_applied",
        "statistical_semantics_modified",
        "historical_outcomes_read",
        "p2_6_1_partial_statistical_results_read",
        "p2_6_3_statistical_results_read",
        "measurement_update_policy_digest",
        "p2_6_3_task_digest",
        "evidence_created",
        "evidence_progress_before",
        "evidence_progress_after",
        "downstream_consumer",
        "production_action",
        "production_impact",
        "git_commit",
        "working_tree_clean",
        "parent_digests",
    }
    if (
        set(execution) != expected_execution_fields
        or source_integrity != reconstructed_source
        or equivalence != reconstructed_equivalence
        or benchmark_attempt.get("measured_result_float64_tree")
        != golden_fixture.get("replicate_result")
        or measured_journal_bytes
        != str(golden_fixture["checkpoint_journal_utf8"]).encode("utf-8")
        or execution.get("schema_version") != MAINLINE_EXECUTION_SCHEMA
        or execution.get("execution_id") != execution_id
        or execution.get("control_plane_key") != control_plane_key
        or execution.get("goal_key") != task.goal_key
        or execution.get("task_key") != task.task_key
        or execution.get("task_digest") != task.artifact_digest
        or execution.get("capability") != task.requested_capability
        or execution.get("status") != "COMPLETE"
        or execution.get("completion_classification") != "VALIDATED_IN_MAINLINE"
        or execution.get("input_artifact_digests") != list(task.input_artifact_digests)
        or execution.get("completion_fact") != M4_P29_RUNTIME_AUDIT_COMPLETION_FACT
        or execution.get("runtime_executor_fingerprint_digest_before")
        != golden_plan["executor_fingerprint_digest"]
        or execution.get("runtime_executor_fingerprint_digest_after")
        != golden_plan["executor_fingerprint_digest"]
        or execution.get("actual_fold_count") != 61
        or execution.get("audited_fold_count") != 61
        or execution.get("correctness_replay_fold_count") != 61
        or execution.get("total_execution_fold_count") != 122
        or execution.get("correctness_boundary_snapshot_count") != 45
        or execution.get("frozen_reference_fold_count") != 61
        or execution.get("registered_artifact_count") != 6
        or execution.get("worker_count") != 1
        or execution.get("formal_benchmark_after_p263_compatibility") is not True
        or execution.get("reference_evaluator_is_oracle") is not False
        or execution.get("immutable_golden_fixture_is_oracle") is not True
        or execution.get("acceleration_boundary_independent") is not True
        or execution.get("acceleration_boundary_independence_scope")
        != M4_P29_ACCELERATION_BOUNDARY_SCOPE
        or execution.get("oracle_construction_process_isolated") is not False
        or execution.get("oracle_construction_fully_implementation_independent")
        is not False
        or execution.get("benchmark_attempt_id")
        != benchmark_attempt["benchmark_attempt_id"]
        or execution.get("benchmark_attempt_path")
        != benchmark_attempt["benchmark_attempt_path"]
        or execution.get("measured_workdir_path")
        != benchmark_attempt["measured_workdir_path"]
        or execution.get("correctness_replay_workdir_path")
        != benchmark_attempt["correctness_replay_workdir_path"]
        or execution.get("journal_reused") is not False
        or execution.get("fresh_workdir") is not True
        or execution.get("golden_reference_execution_artifact_digest")
        != golden_execution["artifact_digest"]
        or execution.get("golden_reference_plan_artifact_digest")
        != golden_plan["artifact_digest"]
        or execution.get("golden_reference_fixture_artifact_digest")
        != golden_fixture["artifact_digest"]
        or execution.get("golden_reference_replay_artifact_digest")
        != golden_replay["artifact_digest"]
        or execution.get("golden_source_integrity_attestation_artifact_digest")
        != golden_source_integrity["artifact_digest"]
        or execution.get("exact_golden_replay_verified") is not True
        or execution.get("shared_frozen_source_modified") is not False
        or execution.get("backend_source_modified")
        is not source_integrity["backend_source_modified"]
        or execution.get("acceleration_changed_paths")
        != source_integrity["acceleration_changed_paths"]
        or execution.get("backend_optimization_applied") is not False
        or execution.get("statistical_semantics_modified") is not False
        or execution.get("historical_outcomes_read") is not False
        or execution.get("p2_6_1_partial_statistical_results_read") is not False
        or execution.get("p2_6_3_statistical_results_read") is not False
        or execution.get("measurement_update_policy_digest")
        != PERIODIC_REFIT_CONTRACT_DIGEST
        or execution.get("p2_6_3_task_digest") != M4_P263_TASK_DIGEST
        or execution.get("evidence_created") is not False
        or execution.get("evidence_progress_before") != 0
        or execution.get("evidence_progress_after") != 0
        or execution.get("downstream_consumer")
        != "future independent optimization request"
        or execution.get("production_action") != "none"
        or execution.get("production_impact") != "none"
        or execution.get("git_commit") != git_commit
        or execution.get("working_tree_clean") is not True
        or execution.get("parent_digests") != expected_parent_digests
    ):
        raise MainlineSupervisorError("runtime audit commit marker identity changed")
    registrations = P24InjectedSignalCalibrationCapability._registrations(
        owner,
        control_plane_key=control_plane_key,
        task=task,
        execution_id=execution_id,
        git_commit=git_commit,
        child_payloads=child_payloads,
        execution_path=execution_path,
        execution_payload=execution,
    )
    if len(registrations) != 6:
        raise MainlineSupervisorError(
            "runtime audit commit marker registration set changed"
        )
    return CapabilityResult(
        execution_artifact=execution,
        execution_artifact_path=execution_path,
        registrations=registrations,
        completion_facts=(M4_P29_RUNTIME_AUDIT_COMPLETION_FACT,),
    )


_RUNTIME_AUDIT_PHASE_INVOCATIONS = {
    "dataset_generation": 1,
    "fold_construction": 1,
    "feature_cache": 62,
    "feature_cache_initialization": 1,
    "estimator_calibrator_fit": 64,
    "prediction_metric": 488,
    "bootstrap": 1,
    "permutation": 1,
    "checkpoint_artifact_persistence": 123,
}


def _finite_nonnegative(value: object, *, positive: bool = False) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and (float(value) > 0 if positive else float(value) >= 0)
    )


def _unavailable_or_nonnegative_integer(value: object) -> bool:
    return value == "UNAVAILABLE" or (
        isinstance(value, int) and not isinstance(value, bool) and value >= 0
    )


def _validate_runtime_observation(
    observation: Mapping[str, Any],
    *,
    benchmark_plan: Mapping[str, Any],
    execution_id: str,
    git_commit: str,
    executor_fingerprint_digest: str,
    benchmark_attempt_id: str,
    measured_result_float64_tree_digest: str,
    measured_checkpoint_journal_sha256: str,
) -> None:
    _verify_typed_digest(
        observation,
        artifact_type="RuntimeObservationArtifact",
        domain="dehps.m4.p2-9.runtime-observation.v1",
    )
    expected_fields = {
        "schema_version",
        "artifact_type",
        "artifact_digest",
        "benchmark_plan_digest",
        "execution_id",
        "git_commit",
        "executor_fingerprint_digest_before",
        "executor_fingerprint_digest_after",
        "executor_fingerprint_stable",
        "benchmark_attempt_id",
        "workload_kind",
        "trace_capture_enabled",
        "fresh_workdir",
        "journal_reused",
        "measured_result_float64_tree_digest",
        "measured_checkpoint_journal_sha256",
        "environmental_observation",
        "replay_timing_equality_required",
        "worker_count",
        "fold_count",
        "fit_count",
        "resample_count",
        "folds_per_second",
        "fits_per_second",
        "resamples_per_second",
        "wall_time_seconds",
        "process_cpu_time_seconds",
        "process_cpu_utilization_percent",
        "process_lifetime_peak_rss_bytes",
        "process_lifetime_peak_rss_attribution",
        "process_io_read_bytes",
        "process_io_write_bytes",
        "host_iowait_ticks_unattributed",
        "host_iowait_attribution",
        "artifact_write_latency_ms_p50",
        "artifact_write_latency_ms_p95",
        "artifact_write_latency_ms_max",
        "phase_wall_time_seconds",
        "phase_invocation_counts",
        "missing_metric_policy",
        "evidence_created",
        "evidence_progress_increment",
        "production_action",
        "promotion_gate_opened",
        "parent_digests",
    }
    phases = observation.get("phase_wall_time_seconds")
    phase_counts = observation.get("phase_invocation_counts")
    expected_phases = tuple(str(value) for value in benchmark_plan["observed_phases"])
    wall = observation.get("wall_time_seconds")
    cpu = observation.get("process_cpu_time_seconds")
    p50 = observation.get("artifact_write_latency_ms_p50")
    p95 = observation.get("artifact_write_latency_ms_p95")
    maximum = observation.get("artifact_write_latency_ms_max")
    if (
        set(observation) != expected_fields
        or observation.get("schema_version") != "dehps-m4-p2-9-runtime-observation.v1"
        or observation.get("benchmark_plan_digest")
        != benchmark_plan.get("artifact_digest")
        or observation.get("execution_id") != execution_id
        or observation.get("git_commit") != git_commit
        or observation.get("executor_fingerprint_digest_before")
        != executor_fingerprint_digest
        or observation.get("executor_fingerprint_digest_after")
        != executor_fingerprint_digest
        or observation.get("executor_fingerprint_stable") is not True
        or observation.get("benchmark_attempt_id") != benchmark_attempt_id
        or observation.get("workload_kind") != "production_like_trace_capture_disabled"
        or observation.get("trace_capture_enabled") is not False
        or observation.get("fresh_workdir") is not True
        or observation.get("journal_reused") is not False
        or observation.get("measured_result_float64_tree_digest")
        != measured_result_float64_tree_digest
        or observation.get("measured_checkpoint_journal_sha256")
        != measured_checkpoint_journal_sha256
        or observation.get("environmental_observation") is not True
        or observation.get("replay_timing_equality_required") is not False
        or observation.get("worker_count") != 1
        or observation.get("fold_count") != 61
        or observation.get("fit_count") != 64
        or observation.get("resample_count") != 4000
        or not isinstance(phases, Mapping)
        or set(phases) != set(expected_phases)
        or any(not _finite_nonnegative(phases[name]) for name in expected_phases)
        or phase_counts != _RUNTIME_AUDIT_PHASE_INVOCATIONS
        or not _finite_nonnegative(wall, positive=True)
        or not _finite_nonnegative(cpu)
        or not _finite_nonnegative(observation.get("process_cpu_utilization_percent"))
        or not _finite_nonnegative(observation.get("process_lifetime_peak_rss_bytes"))
        or observation.get("process_lifetime_peak_rss_attribution")
        != "PROCESS_LIFETIME_HIGH_WATER_MARK_NOT_AUDIT_WORKLOAD_ATTRIBUTABLE"
        or not _unavailable_or_nonnegative_integer(
            observation.get("process_io_read_bytes")
        )
        or not _unavailable_or_nonnegative_integer(
            observation.get("process_io_write_bytes")
        )
        or not _unavailable_or_nonnegative_integer(
            observation.get("host_iowait_ticks_unattributed")
        )
        or observation.get("host_iowait_attribution")
        != "HOST_LEVEL_NOT_PROCESS_ATTRIBUTABLE"
        or not _finite_nonnegative(p50)
        or not _finite_nonnegative(p95)
        or not _finite_nonnegative(maximum)
        or not float(p50) <= float(p95) <= float(maximum)
        or observation.get("missing_metric_policy") != "UNAVAILABLE"
        or observation.get("evidence_created") is not False
        or observation.get("evidence_progress_increment") != 0
        or observation.get("production_action") != "none"
        or observation.get("promotion_gate_opened") is not False
        or observation.get("parent_digests") != [benchmark_plan.get("artifact_digest")]
    ):
        raise MainlineSupervisorError(
            "runtime audit registered observation contract changed"
        )
    assert isinstance(wall, (int, float))
    assert isinstance(cpu, (int, float))
    fit_count = observation.get("fit_count")
    assert isinstance(fit_count, int) and not isinstance(fit_count, bool)
    if (
        observation.get("folds_per_second") != 61 / wall
        or observation.get("fits_per_second") != fit_count / wall
        or observation.get("resamples_per_second") != 4000 / wall
        or observation.get("process_cpu_utilization_percent") != 100.0 * cpu / wall
    ):
        raise MainlineSupervisorError("runtime audit observation arithmetic changed")


def _event_payload(event: Mapping[str, Any]) -> dict[str, Any]:
    raw = event.get("payload", ())
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, list):
        return {str(key): value for key, value in raw}
    return {}


class P23WalkForwardCapability:
    def __init__(self, *, root_dir: Path = ROOT_DIR) -> None:
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if task.task_key != P23_TASK_KEY or task.requested_capability != P23_CAPABILITY:
            raise MainlineSupervisorError("P2.3 capability received the wrong task")
        if len(task.input_artifact_digests) != 3:
            raise MainlineSupervisorError(
                "P2.3 requires exactly three frozen input digests"
            )
        dataset_digest, metric_digest, harness_digest = task.input_artifact_digests
        dataset_path = (
            self.root_dir
            / "runtime/research-os/information-theory/synthetic"
            / dataset_digest
            / "dataset.json"
        )
        if not dataset_path.is_file():
            raise MainlineSupervisorError(
                f"canonical P2.1 dataset artifact is missing: {dataset_digest}"
            )
        dataset = load_synthetic_dataset(dataset_path)
        if dataset.artifact_digest != dataset_digest:
            raise MainlineSupervisorError("located P2.1 dataset digest changed")

        metric_path = (
            self.root_dir
            / "configs/research-os/m4-information-theory-metric-kernel-v1.json"
        )
        metric_manifest = load_metric_kernel_manifest(metric_path)
        if metric_manifest.artifact_digest != metric_digest:
            raise MainlineSupervisorError("P2.2 Metric Kernel identity changed")

        harness_path = (
            self.root_dir
            / "configs/research-os/m4-information-theory-walk-forward-harness-v1.json"
        )
        harness = load_harness_manifest(harness_path)
        if harness.artifact_digest != harness_digest:
            raise MainlineSupervisorError("P2.3 harness identity changed")

        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        output_dir = task_dir / "artifacts"
        run_artifacts = [
            run_walk_forward(
                dataset=dataset,
                manifest=harness,
                probe_id=probe_id,
                output_dir=output_dir,
                git_commit=git_commit,
                working_tree_clean=True,
                dataset_path=dataset_path,
                manifest_path=harness_path,
                worker_count=1,
            )
            for probe_id in P23_PROBES
        ]

        artifact_paths = self._child_artifact_paths(
            output_dir=output_dir,
            run_artifacts=run_artifacts,
        )
        child_payloads = tuple(
            (path, _load_object(path)) for path in sorted(artifact_paths)
        )
        child_identities = tuple(
            sorted(
                {
                    (
                        _artifact_digest(payload),
                        str(payload.get("artifact_type") or "typed_artifact"),
                    )
                    for _, payload in child_payloads
                }
            )
        )
        actual_fold_count = sum(
            int(artifact["aggregate"]["fold_count"]) for artifact in run_artifacts
        )
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "run_digests": [str(item["run_digest"]) for item in run_artifacts],
            "run_artifact_digests": [
                str(item["artifact_digest"]) for item in run_artifacts
            ],
            "actual_fold_count": actual_fold_count,
            "registered_artifact_count": len(child_identities) + 1,
            "engineering_progress_before": 26,
            "engineering_progress_after": 30,
            "evidence_progress_before": 0,
            "evidence_progress_after": 0,
            "downstream_consumer": "m4-p2-injected-signal-calibration",
            "git_commit": git_commit,
            "working_tree_clean": True,
            "descriptive_only": True,
            "eligible_for_p2_gate": False,
            "production_impact": "none",
            "parent_digests": [
                *task.input_artifact_digests,
                *(str(item["artifact_digest"]) for item in run_artifacts),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)

        registrations = self._registrations(
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
        )

    @staticmethod
    def _child_artifact_paths(
        *,
        output_dir: Path,
        run_artifacts: list[Mapping[str, Any]],
    ) -> set[Path]:
        paths: set[Path] = set()
        for run in run_artifacts:
            paths.add(
                output_dir / "runs" / str(run["run_digest"]) / "run-artifact.json"
            )
            for digest in run["fold_digests"]:
                fold_path = output_dir / "folds" / str(digest) / "fold-manifest.json"
                paths.add(fold_path)
                fold = _load_object(fold_path)
                paths.add(
                    output_dir
                    / "feature-views"
                    / str(fold["feature_view_digest"])
                    / "feature-view.json"
                )
            for digest in run["probe_state_digests"]:
                paths.add(
                    output_dir / "probe-states" / str(digest) / "probe-state.json"
                )
            for digest in run["preprocessing_state_digests"]:
                paths.add(
                    output_dir
                    / "preprocessing-states"
                    / str(digest)
                    / "preprocessing-state.json"
                )
            for digest in run["prediction_checkpoint_digests"]:
                paths.add(output_dir / "predictions" / str(digest) / "prediction.json")
            for digest in run["settlement_digests"]:
                paths.add(output_dir / "settlements" / str(digest) / "settlement.json")
        missing = sorted(str(path) for path in paths if not path.is_file())
        if missing:
            raise MainlineSupervisorError(
                "P2.3 child artifact graph is incomplete: " + ", ".join(missing)
            )
        return paths

    def _registrations(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
        child_payloads: tuple[tuple[Path, Mapping[str, Any]], ...],
        execution_path: Path,
        execution_payload: Mapping[str, Any],
    ) -> tuple[MainlineArtifactRegistration, ...]:
        by_identity: dict[tuple[str, str], MainlineArtifactRegistration] = {}
        for path, payload in (
            *child_payloads,
            (execution_path, execution_payload),
        ):
            digest = _artifact_digest(payload)
            artifact_type = str(payload.get("artifact_type") or "typed_artifact")
            registration = MainlineArtifactRegistration(
                execution_id=execution_id,
                control_plane_key=control_plane_key,
                task_key=task.task_key,
                task_digest=task.artifact_digest,
                artifact_digest=digest,
                artifact_type=artifact_type,
                schema_version=str(payload.get("schema_version") or "unknown"),
                artifact_path=str(path.relative_to(self.root_dir)),
                parent_digests=tuple(
                    str(value) for value in payload.get("parent_digests", ())
                ),
                git_commit=git_commit,
            )
            by_identity[(digest, artifact_type)] = registration
        return tuple(by_identity[key] for key in sorted(by_identity))


class P24InjectedSignalCalibrationCapability:
    def __init__(self, *, root_dir: Path = ROOT_DIR) -> None:
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if task.task_key != P24_TASK_KEY or task.requested_capability != P24_CAPABILITY:
            raise MainlineSupervisorError("P2.4 capability received the wrong task")
        expected_inputs = (
            P24_PREREGISTRATION_DIGEST,
            P24_DECISION_POLICY_DIGEST,
            P24_SYNTHETIC_MANIFEST_DIGEST,
            P24_METRIC_KERNEL_DIGEST,
            P24_WALK_FORWARD_HARNESS_DIGEST,
            CALIBRATION_RUN_MANIFEST_DIGEST,
        )
        if task.input_artifact_digests != expected_inputs:
            raise MainlineSupervisorError(
                "P2.4 requires all six frozen input identities in order"
            )
        calibration_manifest_path = (
            self.root_dir / "configs/research-os/"
            "m4-information-theory-p2-4-calibration-run-manifest-v1.json"
        )
        calibration_manifest = load_calibration_manifest(calibration_manifest_path)
        metric_manifest = load_metric_kernel_manifest(
            self.root_dir / "configs/research-os/"
            "m4-information-theory-metric-kernel-v1.json"
        )
        if metric_manifest.artifact_digest != P24_METRIC_KERNEL_DIGEST:
            raise MainlineSupervisorError("P2.2 Metric Kernel identity changed")
        harness_path = (
            self.root_dir / "configs/research-os/"
            "m4-information-theory-walk-forward-harness-v1.json"
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        output_dir = task_dir / "artifacts"
        run = run_p24_calibration(
            manifest=calibration_manifest,
            harness_path=harness_path,
            output_dir=output_dir,
            execution_id=execution_id,
            git_commit=git_commit,
        )
        child_payloads = tuple(
            (path, _load_object(path)) for path in run.artifact_paths
        )
        child_identities = {
            (
                _artifact_digest(payload),
                str(payload.get("artifact_type") or "typed_artifact"),
            )
            for _, payload in child_payloads
        }
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "calibration_run_manifest_digest": (calibration_manifest.artifact_digest),
            "calibration_run_artifact_digest": run.calibration_artifact[
                "artifact_digest"
            ],
            "completion_artifact_digest": run.completion_artifact["artifact_digest"],
            "truth_artifact_digests": [
                item["artifact_digest"] for item in run.truth_artifacts
            ],
            "truth_artifact_count": len(run.truth_artifacts),
            "actual_fold_count": run.actual_fold_count,
            "registered_artifact_count": len(child_identities) + 1,
            "engineering_progress_before": 30,
            "engineering_progress_after": 34,
            "evidence_progress_before": 0,
            "evidence_progress_after": 0,
            "downstream_consumer": "m4-p2-resampling",
            "eligible_for_p2_5_input": True,
            "eligible_for_power_evidence": False,
            "formal_power_executed": False,
            "formal_false_positive_executed": False,
            "bootstrap_executed": False,
            "formal_permutation_executed": False,
            "real_history_used": False,
            "production_checkpoint_created": False,
            "git_commit": git_commit,
            "working_tree_clean": True,
            "descriptive_only": True,
            "eligible_for_p2_gate": False,
            "evidence_created": False,
            "production_impact": "none",
            "parent_digests": [
                *task.input_artifact_digests,
                run.calibration_artifact["artifact_digest"],
                run.completion_artifact["artifact_digest"],
                *(item["artifact_digest"] for item in run.truth_artifacts),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = self._registrations(
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        if len(registrations) != execution_payload["registered_artifact_count"]:
            raise MainlineSupervisorError("P2.4 registered artifact count changed")
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
        )

    def _registrations(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
        child_payloads: tuple[tuple[Path, Mapping[str, Any]], ...],
        execution_path: Path,
        execution_payload: Mapping[str, Any],
    ) -> tuple[MainlineArtifactRegistration, ...]:
        by_identity: dict[tuple[str, str], MainlineArtifactRegistration] = {}
        for path, payload in (
            *child_payloads,
            (execution_path, execution_payload),
        ):
            digest = _artifact_digest(payload)
            artifact_type = str(payload.get("artifact_type") or "typed_artifact")
            registration = MainlineArtifactRegistration(
                execution_id=execution_id,
                control_plane_key=control_plane_key,
                task_key=task.task_key,
                task_digest=task.artifact_digest,
                artifact_digest=digest,
                artifact_type=artifact_type,
                schema_version=str(payload.get("schema_version") or "unknown"),
                artifact_path=str(path.relative_to(self.root_dir)),
                parent_digests=tuple(
                    str(value) for value in payload.get("parent_digests", ())
                ),
                git_commit=str(payload.get("runtime_git_commit") or git_commit),
            )
            by_identity[(digest, artifact_type)] = registration
        return tuple(by_identity[key] for key in sorted(by_identity))


class P25ResamplingCapability:
    def __init__(self, *, root_dir: Path = ROOT_DIR) -> None:
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if task.task_key != P25_TASK_KEY or task.requested_capability != P25_CAPABILITY:
            raise MainlineSupervisorError("P2.5 capability received the wrong task")
        expected_inputs = (
            P25_PREREGISTRATION_DIGEST,
            P25_DECISION_POLICY_DIGEST,
            P25_SYNTHETIC_MANIFEST_DIGEST,
            P25_METRIC_KERNEL_DIGEST,
            P25_WALK_FORWARD_HARNESS_DIGEST,
            P25_P24_COMPLETION_DIGEST,
            KERNEL_MANIFEST_DIGEST,
        )
        if task.input_artifact_digests != expected_inputs:
            raise MainlineSupervisorError(
                "P2.5 requires all seven frozen input identities in order"
            )
        manifest = load_resampling_manifest(
            self.root_dir / "configs/research-os/"
            "m4-information-theory-p2-5-resampling-kernel-v1.json"
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        run = run_p25_resampling(
            manifest=manifest,
            root_dir=self.root_dir,
            output_dir=task_dir / "artifacts",
            execution_id=execution_id,
            git_commit=git_commit,
            working_tree_clean=True,
        )
        child_payloads = tuple(
            (path, _load_object(path)) for path in run.artifact_paths
        )
        child_identities = {
            (
                _artifact_digest(payload),
                str(payload.get("artifact_type") or "typed_artifact"),
            )
            for _, payload in child_payloads
        }
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "resampling_kernel_digest": manifest.artifact_digest,
            "resampling_run_digest": run.run_artifact["artifact_digest"],
            "resampling_completion_digest": run.completion_artifact["artifact_digest"],
            "child_replicate_digests": [
                item["artifact_digest"] for item in run.child_artifacts
            ],
            "aggregate_digests": [
                item["artifact_digest"] for item in run.aggregate_artifacts
            ],
            "replicate_count": run.replicate_count,
            "aggregate_count": len(run.aggregate_artifacts),
            "actual_fold_count": 0,
            "registered_artifact_count": len(child_identities) + 1,
            "engineering_progress_before": 34,
            "engineering_progress_after": 37,
            "evidence_progress_before": 0,
            "evidence_progress_after": 0,
            "downstream_consumer": "m4-p2-false-positive-and-power-runs",
            "eligible_for_formal_inference": False,
            "formal_power_executed": False,
            "formal_false_positive_executed": False,
            "mde_computed": False,
            "pe2_finalized": False,
            "real_history_used": False,
            "production_checkpoint_created": False,
            "git_commit": git_commit,
            "working_tree_clean": True,
            "descriptive_only": True,
            "eligible_for_p2_gate": False,
            "evidence_created": False,
            "production_impact": "none",
            "parent_digests": [
                *task.input_artifact_digests,
                run.run_artifact["artifact_digest"],
                run.completion_artifact["artifact_digest"],
                *(item["artifact_digest"] for item in run.aggregate_artifacts),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity, domain="dehps.research-os.mainline-execution.v1"
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        if len(registrations) != execution_payload["registered_artifact_count"]:
            raise MainlineSupervisorError("P2.5 registered artifact count changed")
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
        )


class P26IdentifiabilityPreflightCapability:
    def __init__(self, *, root_dir: Path = ROOT_DIR) -> None:
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != P26_PREFLIGHT_TASK_KEY
            or task.requested_capability != P26_PREFLIGHT_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "P2.6 identifiability preflight received the wrong task"
            )
        expected_inputs = (
            P25_P24_COMPLETION_DIGEST,
            P25_METRIC_KERNEL_DIGEST,
            P25_WALK_FORWARD_HARNESS_DIGEST,
            "38bfbb983f65e4d800cb3e177fc6bbb65ac13a38496ab8ffdd9afdea10897134",
            MEASUREMENT_VALIDATION_MANIFEST_DIGEST,
            SUPERSEDED_RUN_ARCHIVE_DIGEST,
            IDENTIFIABILITY_PREFLIGHT_MANIFEST_DIGEST,
        )
        if task.input_artifact_digests != expected_inputs:
            raise MainlineSupervisorError(
                "P2.6 identifiability preflight requires all seven frozen "
                "input identities in order"
            )
        manifest = load_identifiability_preflight_manifest(
            self.root_dir / "configs/research-os/"
            "m4-information-theory-p2-6-identifiability-preflight-v1.json"
        )
        archive = load_superseded_run_archive(
            self.root_dir / "configs/research-os/"
            "m4-information-theory-p2-6-superseded-run-archive-v1.json"
        )
        if archive["artifact_digest"] != SUPERSEDED_RUN_ARCHIVE_DIGEST:
            raise MainlineSupervisorError(
                "P2.6 superseded run archive identity changed"
            )
        run = run_identifiability_preflight(
            manifest=manifest,
            root_dir=self.root_dir,
            execution_id=execution_id,
            git_commit=git_commit,
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        report_path = task_dir / "artifacts/preflight-report.json"
        _persist_immutable(report_path, run.report)
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "identifiability_preflight_manifest_digest": (manifest.artifact_digest),
            "identifiability_preflight_report_digest": (run.report["artifact_digest"]),
            "superseded_run_archive_digest": (archive["artifact_digest"]),
            "decision": run.report["decision"],
            "decision_fact": run.decision_fact,
            "failed_requirements": run.report["failed_classifications"],
            "scenario_count": run.report["scenario_count"],
            "actual_fold_count": 0,
            "registered_artifact_count": 2,
            "engineering_progress_before": 37,
            "engineering_progress_after": 38,
            "evidence_progress_before": 0,
            "evidence_progress_after": 0,
            "downstream_consumer": "m4-p2-repair-measurement-system",
            "p2_6_partial_statistical_results_inspected": False,
            "old_p2_6_execution_resumable": False,
            "eligible_for_formal_inference": False,
            "eligible_for_p2_gate": False,
            "evidence_created": False,
            "production_impact": "none",
            "git_commit": git_commit,
            "working_tree_clean": True,
            "replay_status": "DETERMINISTIC",
            "parent_digests": [
                *task.input_artifact_digests,
                run.report["artifact_digest"],
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=((report_path, run.report),),
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        if len(registrations) != execution_payload["registered_artifact_count"]:
            raise MainlineSupervisorError(
                "P2.6 identifiability preflight registered artifact count changed"
            )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=(run.decision_fact,),
        )


class P26MeasurementSystemRepairCapability:
    def __init__(self, *, root_dir: Path = ROOT_DIR) -> None:
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != P26_REPAIR_TASK_KEY
            or task.requested_capability != P26_REPAIR_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "P2 measurement repair received the wrong task"
            )
        expected_inputs = (
            "79ba9b17b0e620e2a06e5fcfe96603351843d7e17510a3ca1ae5a9a1eba7986a",
            SUPERSEDED_RUN_ARCHIVE_DIGEST,
            MEASUREMENT_REPAIR_MANIFEST_DIGEST,
            REPAIRED_MEASUREMENT_VALIDATION_MANIFEST_DIGEST,
            "1a76f46d7a47a134c1688657749bc040290f65a03dbc7c860e38144e02005981",
        )
        if task.input_artifact_digests != expected_inputs:
            raise MainlineSupervisorError(
                "P2 measurement repair requires all five frozen repair "
                "identities in order"
            )
        run = run_measurement_contract_repair(
            root_dir=self.root_dir,
            execution_id=execution_id,
            git_commit=git_commit,
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        development_path = (
            task_dir
            / "artifacts/development-selection"
            / str(run.development_selection["artifact_digest"])
            / "selection.json"
        )
        _persist_immutable(development_path, run.development_selection)
        truth_payloads: list[tuple[Path, Mapping[str, Any]]] = []
        for truth in run.truth_artifacts:
            path = (
                task_dir
                / "artifacts/truth"
                / str(truth["artifact_digest"])
                / "truth.json"
            )
            _persist_immutable(path, truth)
            truth_payloads.append((path, truth))
        confirmation_path = (
            task_dir
            / "artifacts/identifiability"
            / str(run.identifiability_confirmation["artifact_digest"])
            / "confirmation.json"
        )
        _persist_immutable(
            confirmation_path,
            run.identifiability_confirmation,
        )
        completion_path = (
            task_dir
            / "artifacts/completion"
            / str(run.completion["artifact_digest"])
            / "completion.json"
        )
        _persist_immutable(completion_path, run.completion)
        child_payloads = (
            (development_path, run.development_selection),
            *truth_payloads,
            (confirmation_path, run.identifiability_confirmation),
            (completion_path, run.completion),
        )
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "measurement_repair_manifest_digest": (run.manifest.artifact_digest),
            "repaired_measurement_validation_manifest_digest": (
                REPAIRED_MEASUREMENT_VALIDATION_MANIFEST_DIGEST
            ),
            "development_selection_artifact_digest": (
                run.development_selection["artifact_digest"]
            ),
            "truth_artifact_digests": [
                item["artifact_digest"] for item in run.truth_artifacts
            ],
            "identifiability_confirmation_digest": (
                run.identifiability_confirmation["artifact_digest"]
            ),
            "completion_artifact_digest": run.completion["artifact_digest"],
            "completion_fact": REPAIRED_FACT,
            "actual_fold_count": 0,
            "registered_artifact_count": len(child_payloads) + 1,
            "engineering_progress_before": 38,
            "engineering_progress_after": 40,
            "evidence_progress_before": 0,
            "evidence_progress_after": 0,
            "outer_fold_fit_count_before": 46,
            "outer_fold_fit_count_after": 4,
            "inner_model_selection_per_outer_fold": 0,
            "formal_power_target_count": 8,
            "joint_only_negative_control_count": 3,
            "feasibility_sentinel_count": 1,
            "downstream_consumer": P26_TASK_KEY,
            "old_p2_6_partial_statistical_results_inspected": False,
            "old_p2_6_execution_resumable": False,
            "eligible_for_formal_inference": False,
            "evidence_created": False,
            "production_impact": "none",
            "git_commit": git_commit,
            "working_tree_clean": True,
            "replay_status": "DETERMINISTIC",
            "parent_digests": [
                *task.input_artifact_digests,
                *(str(payload["artifact_digest"]) for _, payload in child_payloads),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        if len(registrations) != execution_payload["registered_artifact_count"]:
            raise MainlineSupervisorError(
                "P2 measurement repair registered artifact count changed"
            )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=(REPAIRED_FACT,),
        )


class M4P263SupersedingCompatibilityCapability:
    def __init__(
        self,
        *,
        root_dir: Path = ROOT_DIR,
        source_repository_dir: Path | None = None,
    ) -> None:
        self.root_dir = root_dir
        self.source_repository_dir = source_repository_dir or root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != M4_P263_COMPATIBILITY_TASK_KEY
            or task.requested_capability != M4_P263_COMPATIBILITY_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "M4 P2.6.3 compatibility received the wrong task"
            )
        expected_inputs = (
            COMPATIBILITY_REQUEST_DIGEST,
            P261_FROZEN_FIXTURE_DIGEST,
            P263_SUPERSEDING_FIXTURE_DIGEST,
            P263_POLICY_DIGEST,
        )
        if task.input_artifact_digests != expected_inputs:
            raise MainlineSupervisorError(
                "M4 P2.6.3 compatibility source identities changed"
            )
        p261 = load_measurement_compatibility_fixture(
            self.root_dir / P261_FROZEN_FIXTURE_PATH,
            expected_phase="M4-P2.6.1",
        )
        p263 = load_measurement_compatibility_fixture(
            self.root_dir / P263_SUPERSEDING_FIXTURE_PATH,
            expected_phase="M4-P2.6.3",
        )
        request = load_measurement_compatibility_request(
            self.root_dir / COMPATIBILITY_REQUEST_PATH,
            p261=p261,
            p263=p263,
        )
        p261_replay = replay_measurement_source_fixture(
            root_dir=self.source_repository_dir,
            fixture=p261,
        )
        p263_replay = replay_measurement_source_fixture(
            root_dir=self.source_repository_dir,
            fixture=p263,
        )
        acceptance = build_measurement_compatibility_acceptance(
            request=request,
            p261=p261,
            p263=p263,
            p261_replay=p261_replay,
            p263_replay=p263_replay,
            execution_id=execution_id,
            git_commit=git_commit,
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        child_paths = (
            task_dir
            / "artifacts/source-fixture-replay"
            / str(p261_replay["artifact_digest"])
            / "p2.6.1-replay.json",
            task_dir
            / "artifacts/source-fixture-replay"
            / str(p263_replay["artifact_digest"])
            / "p2.6.3-replay.json",
            task_dir
            / "artifacts/compatibility-acceptance"
            / str(acceptance["artifact_digest"])
            / "acceptance.json",
        )
        child_payloads = tuple(
            zip(
                child_paths,
                (p261_replay, p263_replay, acceptance),
                strict=True,
            )
        )
        for path, payload in child_payloads:
            _persist_immutable(path, payload)
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "compatibility_request_digest": request.artifact_digest,
            "p2_6_1_fixture_digest": p261.artifact_digest,
            "p2_6_1_source_replay_digest": p261_replay["artifact_digest"],
            "p2_6_3_fixture_digest": p263.artifact_digest,
            "p2_6_3_source_replay_digest": p263_replay["artifact_digest"],
            "compatibility_acceptance_digest": acceptance["artifact_digest"],
            "completion_fact": COMPATIBILITY_COMPLETION_FACT,
            "actual_fold_count": 0,
            "registered_artifact_count": 4,
            "historical_outcomes_read": False,
            "p2_6_1_partial_statistical_results_read": False,
            "old_results_or_checkpoints_reused": False,
            "evidence_created": False,
            "evidence_progress_before": 25,
            "evidence_progress_after": 25,
            "prediction_v2_promotion_allowed": False,
            "downstream_consumer": M4_V2_DESIGN_TASK_KEY,
            "production_action": "none",
            "production_impact": "none",
            "git_commit": git_commit,
            "working_tree_clean": True,
            "replay_status": "REPLAY_VERIFIED",
            "parent_digests": [
                *task.input_artifact_digests,
                *(str(payload["artifact_digest"]) for _, payload in child_payloads),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        if len(registrations) != execution_payload["registered_artifact_count"]:
            raise MainlineSupervisorError(
                "M4 P2.6.3 compatibility registered artifact count changed"
            )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=(COMPATIBILITY_COMPLETION_FACT,),
        )


class M4MeasurementContractV2DesignCapability:
    def __init__(self, *, root_dir: Path = ROOT_DIR) -> None:
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != M4_V2_DESIGN_TASK_KEY
            or task.requested_capability != M4_V2_DESIGN_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "M4 Measurement Contract v2 design received the wrong task"
            )
        expected_inputs = (
            MEASUREMENT_CONTRACT_V2_DIGEST,
            "ae4e741cfc55547785ca9cf57b5b49f37a3d8c4f2bd53daeff9228982f797a69",
            "56b9d0a62d43d167069e5222c7095383c9c5106bb3361b0b1def75cf2b6c86a2",
            "177a3d591b7557a4231a276bfb007f0d42a94d942824403f5376f94fe904d2ca",
            MEASUREMENT_REPAIR_MANIFEST_DIGEST,
            REPAIRED_MEASUREMENT_VALIDATION_MANIFEST_DIGEST,
            COMPATIBILITY_REQUEST_DIGEST,
        )
        if task.input_artifact_digests != expected_inputs:
            raise MainlineSupervisorError(
                "M4 v2 design requires the seven frozen source-only identities"
            )
        contract = load_measurement_contract_v2(
            self.root_dir / MEASUREMENT_CONTRACT_V2_PATH
        )
        run = build_design_artifacts(
            contract,
            execution_id=execution_id,
            git_commit=git_commit,
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        child_paths = (
            task_dir
            / "artifacts/estimand-contract"
            / str(run.estimand_contract["artifact_digest"])
            / "contract.json",
            task_dir
            / "artifacts/mechanism-role-contract"
            / str(run.mechanism_role_contract["artifact_digest"])
            / "contract.json",
            task_dir
            / "artifacts/gate-compiler-contract"
            / str(run.gate_compiler_contract["artifact_digest"])
            / "contract.json",
            task_dir
            / "artifacts/completion"
            / str(run.completion["artifact_digest"])
            / "completion.json",
        )
        child_payloads = tuple(zip(child_paths, run.artifacts, strict=True))
        for path, payload in child_payloads:
            _persist_immutable(path, payload)
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "measurement_contract_v2_digest": contract.artifact_digest,
            "estimand_contract_digest": run.estimand_contract["artifact_digest"],
            "mechanism_role_contract_digest": run.mechanism_role_contract[
                "artifact_digest"
            ],
            "gate_compiler_contract_digest": run.gate_compiler_contract[
                "artifact_digest"
            ],
            "completion_artifact_digest": run.completion["artifact_digest"],
            "completion_fact": DESIGN_COMPLETION_FACT,
            "actual_fold_count": 0,
            "registered_artifact_count": len(child_payloads) + 1,
            "formal_branch_runs_executed": 0,
            "historical_outcomes_read": False,
            "p2_6_1_partial_statistical_results_read": False,
            "evidence_created": False,
            "evidence_progress_before": 0,
            "evidence_progress_after": 0,
            "downstream_consumer": ("m4-v2-branch-identifiability-preflight-design"),
            "production_impact": "none",
            "git_commit": git_commit,
            "working_tree_clean": True,
            "replay_status": "DETERMINISTIC",
            "parent_digests": [
                *task.input_artifact_digests,
                *(str(payload["artifact_digest"]) for _, payload in child_payloads),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        if len(registrations) != execution_payload["registered_artifact_count"]:
            raise MainlineSupervisorError(
                "M4 v2 design registered artifact count changed"
            )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=(DESIGN_COMPLETION_FACT,),
        )


class M4MeasurementContractV2DesignReplayCapability:
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository,
        root_dir: Path = ROOT_DIR,
    ) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != M4_V2_DESIGN_REPLAY_TASK_KEY
            or task.requested_capability != M4_V2_DESIGN_REPLAY_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "M4 Measurement Contract v2 design replay received the wrong task"
            )
        fixture = load_gate_replay_fixture(self.root_dir / GATE_REPLAY_FIXTURE_PATH)
        if task.input_artifact_digests != (
            MEASUREMENT_CONTRACT_V2_DIGEST,
            fixture.artifact_digest,
        ):
            raise MainlineSupervisorError(
                "M4 v2 design replay source identities changed"
            )
        events = self.repository.list_mainline_execution_events(
            control_plane_key=control_plane_key,
            task_key=M4_V2_DESIGN_TASK_KEY,
        )
        completed = [
            event for event in events if event.get("event_type") == "completed"
        ]
        if len(completed) != 1:
            raise MainlineSupervisorError(
                "M4 v2 design replay requires one completed design execution"
            )
        parent_event = completed[0]
        summary = _event_payload(parent_event)
        parent_path = self.root_dir / str(summary["execution_artifact_path"])
        parent_execution = _load_object(parent_path)
        expected_parent_digest = canonical_digest(
            {
                key: value
                for key, value in parent_execution.items()
                if key != "artifact_digest"
            },
            domain="dehps.research-os.mainline-execution.v1",
        )
        if (
            parent_execution.get("artifact_digest") != expected_parent_digest
            or parent_execution.get("task_key") != M4_V2_DESIGN_TASK_KEY
            or parent_execution.get("execution_id") != parent_event.get("execution_id")
        ):
            raise MainlineSupervisorError(
                "M4 v2 design replay parent execution identity changed"
            )
        parent_registrations = list(
            self.repository.list_mainline_artifacts(
                control_plane_key=control_plane_key,
                execution_id=str(parent_event["execution_id"]),
            )
        )
        contract = load_measurement_contract_v2(
            self.root_dir / MEASUREMENT_CONTRACT_V2_PATH
        )
        reconstructed = build_design_artifacts(
            contract,
            execution_id=str(parent_execution["execution_id"]),
            git_commit=str(parent_execution["git_commit"]),
        )
        _verify_v2_registered_artifacts(
            root_dir=self.root_dir,
            registrations=parent_registrations,
            expected_payloads=(*reconstructed.artifacts, parent_execution),
        )
        replay = build_design_replay_artifacts(
            contract,
            fixture=fixture,
            design_execution=parent_execution,
            design_child_digests=[
                str(item["artifact_digest"])
                for item in parent_registrations
                if item.get("artifact_type") != "research_os_mainline_execution"
            ],
            registration_payloads=parent_registrations,
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        child_paths = (
            task_dir
            / "artifacts/measurement-contract-replay"
            / str(replay.measurement_contract_replay["artifact_digest"])
            / "replay.json",
            task_dir
            / "artifacts/gate-compiler-replay"
            / str(replay.gate_compiler_replay["artifact_digest"])
            / "replay.json",
        )
        child_payloads = tuple(zip(child_paths, replay.artifacts, strict=True))
        for path, payload in child_payloads:
            _persist_immutable(path, payload)
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "measurement_contract_v2_digest": contract.artifact_digest,
            "design_execution_id": parent_execution["execution_id"],
            "design_execution_artifact_digest": parent_execution["artifact_digest"],
            "measurement_contract_replay_digest": (
                replay.measurement_contract_replay["artifact_digest"]
            ),
            "gate_compiler_replay_digest": replay.gate_compiler_replay[
                "artifact_digest"
            ],
            "completion_fact": DESIGN_REPLAY_COMPLETION_FACT,
            "actual_fold_count": 0,
            "registered_artifact_count": 3,
            "formal_branch_runs_executed": 0,
            "historical_outcomes_read": False,
            "p2_6_1_partial_statistical_results_read": False,
            "evidence_created": False,
            "evidence_progress_before": 0,
            "evidence_progress_after": 0,
            "downstream_consumer": ("m4-v2-branch-identifiability-preflight-design"),
            "production_impact": "none",
            "git_commit": git_commit,
            "working_tree_clean": True,
            "replay_status": "REPLAY_VERIFIED",
            "parent_digests": [
                *task.input_artifact_digests,
                str(parent_execution["artifact_digest"]),
                *(str(item["artifact_digest"]) for item in replay.artifacts),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=(DESIGN_REPLAY_COMPLETION_FACT,),
        )


class M4BranchIdentifiabilityPreflightDesignCapability:
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository,
        root_dir: Path = ROOT_DIR,
    ) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != PREFLIGHT_DESIGN_TASK_KEY
            or task.requested_capability != PREFLIGHT_DESIGN_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "M4 v2 branch preflight design received the wrong task"
            )
        fixture = load_gate_replay_fixture(self.root_dir / GATE_REPLAY_FIXTURE_PATH)
        if len(task.input_artifact_digests) != 3 or task.input_artifact_digests[:2] != (
            MEASUREMENT_CONTRACT_V2_DIGEST,
            fixture.artifact_digest,
        ):
            raise MainlineSupervisorError(
                "M4 v2 branch preflight design source identities changed"
            )
        source_contract = load_preflight_source_contract(
            self.root_dir / PREFLIGHT_SOURCE_CONTRACT_PATH
        )
        if source_contract["artifact_digest"] != task.input_artifact_digests[2]:
            raise MainlineSupervisorError(
                "M4 v2 branch preflight source contract changed"
            )
        verify_preflight_source_bytes(
            root_dir=self.root_dir,
            contract=source_contract,
        )
        _, design_execution, _ = _load_single_completed_execution(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=control_plane_key,
            task_key=M4_V2_DESIGN_TASK_KEY,
        )
        _, replay_execution, replay_registrations = _load_single_completed_execution(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=control_plane_key,
            task_key=M4_V2_DESIGN_REPLAY_TASK_KEY,
        )
        gate_replay = _load_registered_type(
            root_dir=self.root_dir,
            registrations=replay_registrations,
            artifact_type="GateCompilerReplayArtifact",
        )
        if (
            replay_execution.get("measurement_contract_v2_digest")
            != MEASUREMENT_CONTRACT_V2_DIGEST
            or replay_execution.get("design_execution_id")
            != design_execution.get("execution_id")
            or replay_execution.get("design_execution_artifact_digest")
            != design_execution.get("artifact_digest")
            or replay_execution.get("gate_compiler_replay_digest")
            != gate_replay.get("artifact_digest")
            or gate_replay.get("status") != "REPLAY_VERIFIED"
            or gate_replay.get("promotion_gate_opened") is not False
        ):
            raise MainlineSupervisorError(
                "M4 v2 branch preflight design replay lineage changed"
            )
        contract = load_measurement_contract_v2(
            self.root_dir / MEASUREMENT_CONTRACT_V2_PATH
        )
        run = build_branch_preflight_design_artifacts(
            contract,
            design_execution_artifact_digest=str(design_execution["artifact_digest"]),
            design_replay_execution_artifact_digest=str(
                replay_execution["artifact_digest"]
            ),
            gate_compiler_replay_digest=str(gate_replay["artifact_digest"]),
            execution_id=execution_id,
            git_commit=git_commit,
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        branch_paths = tuple(
            task_dir
            / "artifacts/branch-preflight-design"
            / str(payload["branch_id"])
            / str(payload["artifact_digest"])
            / "contract.json"
            for payload in run.branch_contracts
        )
        cross_path = (
            task_dir
            / "artifacts/cross-branch-preflight-design"
            / str(run.cross_branch_contract["artifact_digest"])
            / "contract.json"
        )
        completion_path = (
            task_dir
            / "artifacts/completion"
            / str(run.completion["artifact_digest"])
            / "completion.json"
        )
        child_payloads = (
            *zip(branch_paths, run.branch_contracts, strict=True),
            (cross_path, run.cross_branch_contract),
            (completion_path, run.completion),
        )
        for path, payload in child_payloads:
            _persist_immutable(path, payload)
        branch_digests = [
            str(payload["artifact_digest"]) for payload in run.branch_contracts
        ]
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "measurement_contract_v2_digest": contract.artifact_digest,
            "design_execution_id": design_execution["execution_id"],
            "design_execution_artifact_digest": design_execution["artifact_digest"],
            "design_replay_execution_id": replay_execution["execution_id"],
            "design_replay_execution_artifact_digest": replay_execution[
                "artifact_digest"
            ],
            "gate_compiler_replay_digest": gate_replay["artifact_digest"],
            "preflight_source_contract_digest": source_contract["artifact_digest"],
            "preflight_source_set_digest": source_contract["source_set_digest"],
            "branch_preflight_design_digests": branch_digests,
            "cross_branch_preflight_design_digest": run.cross_branch_contract[
                "artifact_digest"
            ],
            "preflight_design_completion_digest": run.completion["artifact_digest"],
            "completion_fact": PREFLIGHT_DESIGN_COMPLETION_FACT,
            "actual_fold_count": 0,
            "registered_artifact_count": len(child_payloads) + 1,
            "formal_branch_runs_executed": 0,
            "preflight_execution_count": 0,
            "preflight_result_count": 0,
            "historical_outcomes_read": False,
            "p2_6_1_partial_statistical_results_read": False,
            "p2_6_3_statistical_results_read": False,
            "evidence_created": False,
            "evidence_progress_before": 0,
            "evidence_progress_after": 0,
            "downstream_consumer": PREFLIGHT_FIXTURE_FREEZE_TASK_KEY,
            "production_impact": "none",
            "production_action": "none",
            "git_commit": git_commit,
            "working_tree_clean": True,
            "replay_status": "DETERMINISTIC",
            "parent_digests": [
                *task.input_artifact_digests,
                str(design_execution["artifact_digest"]),
                str(replay_execution["artifact_digest"]),
                str(gate_replay["artifact_digest"]),
                *(str(payload["artifact_digest"]) for _, payload in child_payloads),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        if len(registrations) != execution_payload["registered_artifact_count"]:
            raise MainlineSupervisorError(
                "M4 v2 branch preflight design registration count changed"
            )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=(PREFLIGHT_DESIGN_COMPLETION_FACT,),
        )


class M4BranchIdentifiabilityFixtureFreezeCapability:
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository,
        root_dir: Path = ROOT_DIR,
    ) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != FIXTURE_FREEZE_TASK_KEY
            or task.requested_capability != FIXTURE_FREEZE_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "M4 v2 branch fixture freeze received the wrong task"
            )
        source_contract = load_fixture_freeze_source_contract(
            self.root_dir / FIXTURE_FREEZE_SOURCE_CONTRACT_PATH
        )
        verify_fixture_freeze_source_bytes(
            root_dir=self.root_dir,
            contract=source_contract,
        )
        _, preflight_execution, preflight_registrations = (
            _load_single_completed_execution(
                repository=self.repository,
                root_dir=self.root_dir,
                control_plane_key=control_plane_key,
                task_key=PREFLIGHT_DESIGN_TASK_KEY,
            )
        )
        preflight_completion = _load_registered_type(
            root_dir=self.root_dir,
            registrations=preflight_registrations,
            artifact_type="m4_v2_branch_preflight_design_completion",
        )
        cross_branch = _load_registered_type(
            root_dir=self.root_dir,
            registrations=preflight_registrations,
            artifact_type="m4_v2_cross_branch_preflight_design",
        )
        if task.input_artifact_digests != (
            str(source_contract["artifact_digest"]),
            str(preflight_completion["artifact_digest"]),
            str(cross_branch["artifact_digest"]),
        ):
            raise MainlineSupervisorError(
                "M4 v2 branch fixture freeze source identities changed"
            )
        if (
            preflight_execution.get("completion_fact")
            != PREFLIGHT_DESIGN_COMPLETION_FACT
            or preflight_execution.get("formal_branch_runs_executed") != 0
            or preflight_execution.get("preflight_result_count") != 0
            or preflight_execution.get("historical_outcomes_read") is not False
            or preflight_execution.get("evidence_created") is not False
            or preflight_completion.get("status") != "COMPLETE"
            or preflight_completion.get("next_consumer") != FIXTURE_FREEZE_TASK_KEY
            or cross_branch.get("formal_execution_allowed") is not False
            or cross_branch.get("preflight_result_count") != 0
        ):
            raise MainlineSupervisorError(
                "M4 v2 branch fixture freeze parent lineage changed"
            )
        run = build_fixture_freeze_artifacts(
            source_contract=source_contract,
            preflight_design_execution_artifact_digest=str(
                preflight_execution["artifact_digest"]
            ),
            preflight_design_completion_digest=str(
                preflight_completion["artifact_digest"]
            ),
            cross_branch_preflight_design_digest=str(cross_branch["artifact_digest"]),
            execution_id=execution_id,
            git_commit=git_commit,
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        child_paths = (
            task_dir
            / "artifacts/joint-maxent-fixture"
            / str(run.solver_contract["artifact_digest"])
            / "contract.json",
            task_dir
            / "artifacts/orthogonal-control-fixture"
            / str(run.orthogonal_control_contract["artifact_digest"])
            / "contract.json",
            task_dir
            / "artifacts/legacy-role-resolution-fixture"
            / str(run.legacy_role_resolution_contract["artifact_digest"])
            / "contract.json",
            task_dir
            / "artifacts/completion"
            / str(run.completion["artifact_digest"])
            / "completion.json",
        )
        child_payloads = tuple(zip(child_paths, run.artifacts, strict=True))
        for path, payload in child_payloads:
            _persist_immutable(path, payload)
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "fixture_freeze_source_contract_digest": source_contract["artifact_digest"],
            "fixture_freeze_source_set_digest": source_contract["source_set_digest"],
            "research_request_key": source_contract["research_request_key"],
            "research_request_id": source_contract["research_request_id"],
            "research_execution_id": source_contract["research_execution_id"],
            "preflight_design_execution_id": preflight_execution["execution_id"],
            "preflight_design_execution_artifact_digest": preflight_execution[
                "artifact_digest"
            ],
            "preflight_design_completion_digest": preflight_completion[
                "artifact_digest"
            ],
            "cross_branch_preflight_design_digest": cross_branch["artifact_digest"],
            "solver_fixture_contract_digest": run.solver_contract["artifact_digest"],
            "orthogonal_control_fixture_contract_digest": (
                run.orthogonal_control_contract["artifact_digest"]
            ),
            "legacy_role_resolution_fixture_contract_digest": (
                run.legacy_role_resolution_contract["artifact_digest"]
            ),
            "fixture_freeze_completion_digest": run.completion["artifact_digest"],
            "fixture_contract_count": 3,
            "completion_fact": FIXTURE_FREEZE_COMPLETION_FACT,
            "actual_fold_count": 0,
            "registered_artifact_count": len(child_payloads) + 1,
            "formal_branch_runs_executed": 0,
            "preflight_execution_count": 0,
            "preflight_result_count": 0,
            "historical_outcomes_read": False,
            "p2_6_1_partial_statistical_results_read": False,
            "p2_6_3_statistical_results_read": False,
            "evidence_created": False,
            "evidence_progress_before": 0,
            "evidence_progress_after": 0,
            "downstream_consumer": PREFLIGHT_EXECUTION_TASK_KEY,
            "production_impact": "none",
            "production_action": "none",
            "git_commit": git_commit,
            "working_tree_clean": True,
            "replay_status": "DETERMINISTIC",
            "parent_digests": [
                *task.input_artifact_digests,
                str(preflight_execution["artifact_digest"]),
                *(str(payload["artifact_digest"]) for _, payload in child_payloads),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        if len(registrations) != execution_payload["registered_artifact_count"]:
            raise MainlineSupervisorError(
                "M4 v2 branch fixture freeze registration count changed"
            )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=(FIXTURE_FREEZE_COMPLETION_FACT,),
        )


class M4BranchIdentifiabilityPreflightExecutionCapability:
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository,
        root_dir: Path = ROOT_DIR,
    ) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != PREFLIGHT_EXECUTION_TASK_KEY
            or task.requested_capability != PREFLIGHT_EXECUTION_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "M4 v2 branch preflight execution received the wrong task"
            )
        source_contract = load_preflight_execution_source_contract(
            self.root_dir / PREFLIGHT_EXECUTION_SOURCE_CONTRACT_PATH
        )
        verify_preflight_execution_source_bytes(
            root_dir=self.root_dir,
            contract=source_contract,
        )
        _, fixture_execution, fixture_registrations = _load_single_completed_execution(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=control_plane_key,
            task_key=FIXTURE_FREEZE_TASK_KEY,
        )
        solver_fixture = _load_registered_type(
            root_dir=self.root_dir,
            registrations=fixture_registrations,
            artifact_type="m4_v2_joint_maxent_fixture_contract",
        )
        orthogonal_fixture = _load_registered_type(
            root_dir=self.root_dir,
            registrations=fixture_registrations,
            artifact_type="m4_v2_orthogonal_control_fixture_contract",
        )
        legacy_fixture = _load_registered_type(
            root_dir=self.root_dir,
            registrations=fixture_registrations,
            artifact_type="m4_v2_legacy_role_resolution_fixture_contract",
        )
        fixture_completion = _load_registered_type(
            root_dir=self.root_dir,
            registrations=fixture_registrations,
            artifact_type="m4_v2_branch_fixture_freeze_completion",
        )
        _, _, design_registrations = _load_single_completed_execution(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=control_plane_key,
            task_key=PREFLIGHT_DESIGN_TASK_KEY,
        )
        branch_designs = tuple(
            sorted(
                _load_registered_type_group(
                    root_dir=self.root_dir,
                    registrations=design_registrations,
                    artifact_type=("m4_v2_branch_identifiability_preflight_design"),
                ),
                key=lambda item: int(item["branch_order_index"]),
            )
        )
        cross_branch_design = _load_registered_type(
            root_dir=self.root_dir,
            registrations=design_registrations,
            artifact_type="m4_v2_cross_branch_preflight_design",
        )
        expected_inputs = (
            str(source_contract["artifact_digest"]),
            str(fixture_execution["artifact_digest"]),
            str(solver_fixture["artifact_digest"]),
            str(orthogonal_fixture["artifact_digest"]),
            str(legacy_fixture["artifact_digest"]),
            str(fixture_completion["artifact_digest"]),
            *(str(item["artifact_digest"]) for item in branch_designs),
            str(cross_branch_design["artifact_digest"]),
        )
        if task.input_artifact_digests != expected_inputs:
            raise MainlineSupervisorError(
                "M4 v2 branch preflight execution source identities changed"
            )
        if (
            fixture_execution.get("completion_fact") != FIXTURE_FREEZE_COMPLETION_FACT
            or fixture_execution.get("fixture_contract_count") != 3
            or fixture_execution.get("formal_branch_runs_executed") != 0
            or fixture_execution.get("preflight_result_count") != 0
            or fixture_execution.get("historical_outcomes_read") is not False
            or fixture_execution.get("p2_6_3_statistical_results_read") is not False
            or fixture_execution.get("evidence_created") is not False
            or fixture_completion.get("next_consumer") != PREFLIGHT_EXECUTION_TASK_KEY
        ):
            raise MainlineSupervisorError(
                "M4 v2 branch preflight execution parent lineage changed"
            )
        run = build_preflight_execution_artifacts(
            source_contract=source_contract,
            fixture_execution_artifact_digest=str(fixture_execution["artifact_digest"]),
            solver_fixture=solver_fixture,
            orthogonal_fixture=orthogonal_fixture,
            legacy_fixture=legacy_fixture,
            fixture_completion=fixture_completion,
            branch_designs=branch_designs,
            cross_branch_design=cross_branch_design,
            execution_id=execution_id,
            git_commit=git_commit,
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        solver_path = (
            task_dir
            / "artifacts/joint-solver-preflight"
            / str(run.solver_result["artifact_digest"])
            / "result.json"
        )
        orthogonal_path = (
            task_dir
            / "artifacts/orthogonal-endpoint-preflight"
            / str(run.orthogonal_result["artifact_digest"])
            / "result.json"
        )
        legacy_path = (
            task_dir
            / "artifacts/legacy-role-preflight"
            / str(run.legacy_result["artifact_digest"])
            / "result.json"
        )
        branch_paths = tuple(
            task_dir
            / "artifacts/branch-health-preflight"
            / str(payload["branch_id"])
            / str(payload["artifact_digest"])
            / "result.json"
            for payload in run.branch_results
        )
        completion_path = (
            task_dir
            / "artifacts/completion"
            / str(run.completion["artifact_digest"])
            / "completion.json"
        )
        child_payloads = (
            (solver_path, run.solver_result),
            (orthogonal_path, run.orthogonal_result),
            (legacy_path, run.legacy_result),
            *zip(branch_paths, run.branch_results, strict=True),
            (completion_path, run.completion),
        )
        for path, payload in child_payloads:
            _persist_immutable(path, payload)
        branch_statuses = {
            str(item["branch_id"]): str(item["status"]) for item in run.branch_results
        }
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "preflight_execution_source_contract_digest": source_contract[
                "artifact_digest"
            ],
            "preflight_execution_source_set_digest": source_contract[
                "source_set_digest"
            ],
            "research_request_key": source_contract["research_request_key"],
            "research_request_id": source_contract["research_request_id"],
            "research_execution_id": source_contract["research_execution_id"],
            "fixture_execution_id": fixture_execution["execution_id"],
            "fixture_execution_artifact_digest": fixture_execution["artifact_digest"],
            "solver_fixture_contract_digest": solver_fixture["artifact_digest"],
            "orthogonal_control_fixture_contract_digest": (
                orthogonal_fixture["artifact_digest"]
            ),
            "legacy_role_resolution_fixture_contract_digest": (
                legacy_fixture["artifact_digest"]
            ),
            "fixture_freeze_completion_digest": fixture_completion["artifact_digest"],
            "branch_preflight_design_digests": [
                item["artifact_digest"] for item in branch_designs
            ],
            "cross_branch_preflight_design_digest": cross_branch_design[
                "artifact_digest"
            ],
            "solver_preflight_result_digest": run.solver_result["artifact_digest"],
            "orthogonal_endpoint_result_digest": run.orthogonal_result[
                "artifact_digest"
            ],
            "legacy_role_preflight_result_digest": run.legacy_result["artifact_digest"],
            "branch_preflight_result_digests": [
                item["artifact_digest"] for item in run.branch_results
            ],
            "preflight_execution_completion_digest": run.completion["artifact_digest"],
            "preflight_execution_status": run.completion["preflight_status"],
            "branch_preflight_statuses": branch_statuses,
            "solver_preflight_status": run.solver_result["status"],
            "orthogonal_endpoint_status": run.orthogonal_result["status"],
            "legacy_role_resolution_status": run.legacy_result["status"],
            "all_branches_pass": run.all_branches_pass,
            "completion_fact": PREFLIGHT_EXECUTION_COMPLETION_FACT,
            "all_branches_pass_fact": (
                PREFLIGHT_EXECUTION_PASS_FACT if run.all_branches_pass else None
            ),
            "actual_fold_count": 0,
            "registered_artifact_count": len(child_payloads) + 1,
            "formal_branch_runs_executed": 0,
            "preflight_execution_count": 1,
            "preflight_result_count": 3,
            "orthogonal_endpoint_count": 12,
            "legacy_state_result_count": 4,
            "monte_carlo_replicates": 0,
            "historical_outcomes_read": False,
            "p2_6_1_partial_statistical_results_read": False,
            "p2_6_3_statistical_results_read": False,
            "evidence_created": False,
            "evidence_progress_before": 0,
            "evidence_progress_after": 0,
            "downstream_consumer": (
                MARGINAL_CONTRACT_FREEZE_TASK_KEY if run.all_branches_pass else None
            ),
            "production_impact": "none",
            "production_action": "none",
            "git_commit": git_commit,
            "working_tree_clean": True,
            "replay_status": "DETERMINISTIC",
            "parent_digests": [
                *task.input_artifact_digests,
                *(str(payload["artifact_digest"]) for _, payload in child_payloads),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        if len(registrations) != execution_payload["registered_artifact_count"]:
            raise MainlineSupervisorError(
                "M4 v2 branch preflight execution registration count changed"
            )
        facts = [PREFLIGHT_EXECUTION_COMPLETION_FACT]
        if run.all_branches_pass:
            facts.append(PREFLIGHT_EXECUTION_PASS_FACT)
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=tuple(facts),
        )


class M4MarginalStaticContractFreezeCapability:
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository,
        root_dir: Path = ROOT_DIR,
    ) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != MARGINAL_STATIC_CONTRACT_FREEZE_TASK_KEY
            or task.requested_capability != MARGINAL_STATIC_CONTRACT_FREEZE_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "M4 v2 marginal-static contract freeze received the wrong task"
            )
        source_contract = load_marginal_static_source_contract(
            self.root_dir / MARGINAL_STATIC_SOURCE_CONTRACT_PATH
        )
        verify_marginal_static_source_bytes(
            root_dir=self.root_dir,
            contract=source_contract,
        )
        _, preflight_execution, preflight_registrations = (
            _load_single_completed_execution(
                repository=self.repository,
                root_dir=self.root_dir,
                control_plane_key=control_plane_key,
                task_key=PREFLIGHT_EXECUTION_TASK_KEY,
            )
        )
        branch_health = next(
            (
                item
                for item in _load_registered_type_group(
                    root_dir=self.root_dir,
                    registrations=preflight_registrations,
                    artifact_type="m4_v2_branch_health_preflight_result",
                )
                if item.get("branch_id") == "MARGINAL_STATIC"
            ),
            None,
        )
        if branch_health is None:
            raise MainlineSupervisorError(
                "M4 v2 marginal-static branch-health result is missing"
            )
        preflight_completion = _load_registered_type(
            root_dir=self.root_dir,
            registrations=preflight_registrations,
            artifact_type="m4_v2_branch_preflight_execution_completion",
        )
        _, _, design_registrations = _load_single_completed_execution(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=control_plane_key,
            task_key=PREFLIGHT_DESIGN_TASK_KEY,
        )
        marginal_design = next(
            (
                item
                for item in _load_registered_type_group(
                    root_dir=self.root_dir,
                    registrations=design_registrations,
                    artifact_type=("m4_v2_branch_identifiability_preflight_design"),
                )
                if item.get("branch_id") == "MARGINAL_STATIC"
            ),
            None,
        )
        if marginal_design is None:
            raise MainlineSupervisorError(
                "M4 v2 marginal-static branch design is missing"
            )
        _, _, binding_registrations = _load_single_completed_execution(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=control_plane_key,
            task_key=M4_V2_MARGINAL_BINDING_TASK_KEY,
        )
        legacy_decision = _load_registered_type(
            root_dir=self.root_dir,
            registrations=binding_registrations,
            artifact_type="marginal_measurement_acceptance_decision",
        )
        _, _, replay_registrations = _load_single_completed_execution(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=control_plane_key,
            task_key=M4_V2_MARGINAL_DECISION_REPLAY_TASK_KEY,
        )
        legacy_replay = _load_registered_type(
            root_dir=self.root_dir,
            registrations=replay_registrations,
            artifact_type="branch_decision_replay_attestation",
        )
        expected_inputs = (
            str(source_contract["artifact_digest"]),
            MEASUREMENT_CONTRACT_V2_DIGEST,
            str(marginal_design["artifact_digest"]),
            str(preflight_execution["artifact_digest"]),
            str(branch_health["artifact_digest"]),
            str(preflight_completion["artifact_digest"]),
            str(legacy_decision["artifact_digest"]),
            str(legacy_replay["artifact_digest"]),
        )
        if task.input_artifact_digests != expected_inputs:
            raise MainlineSupervisorError(
                "M4 v2 marginal-static contract source identities changed"
            )
        if (
            preflight_execution.get("completion_fact")
            != PREFLIGHT_EXECUTION_COMPLETION_FACT
            or preflight_execution.get("all_branches_pass") is not True
            or preflight_execution.get("all_branches_pass_fact")
            != PREFLIGHT_EXECUTION_PASS_FACT
            or preflight_execution.get("historical_outcomes_read") is not False
            or preflight_execution.get("evidence_created") is not False
        ):
            raise MainlineSupervisorError(
                "M4 v2 marginal-static preflight lineage changed"
            )
        run = build_marginal_static_contract_artifacts(
            source_contract=source_contract,
            measurement_contract_v2_digest=MEASUREMENT_CONTRACT_V2_DIGEST,
            marginal_branch_design=marginal_design,
            preflight_execution_artifact_digest=str(
                preflight_execution["artifact_digest"]
            ),
            marginal_branch_health=branch_health,
            preflight_completion=preflight_completion,
            legacy_marginal_decision=legacy_decision,
            legacy_decision_replay=legacy_replay,
            execution_id=execution_id,
            git_commit=git_commit,
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        contract_path = (
            task_dir
            / "artifacts/marginal-static-measurement-contract"
            / str(run.measurement_contract["artifact_digest"])
            / "contract.json"
        )
        completion_path = (
            task_dir
            / "artifacts/completion"
            / str(run.completion["artifact_digest"])
            / "completion.json"
        )
        child_payloads = (
            (contract_path, run.measurement_contract),
            (completion_path, run.completion),
        )
        for path, payload in child_payloads:
            _persist_immutable(path, payload)
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "marginal_static_source_contract_digest": source_contract[
                "artifact_digest"
            ],
            "marginal_static_source_set_digest": source_contract["source_set_digest"],
            "research_request_key": source_contract["research_request_key"],
            "research_request_id": source_contract["research_request_id"],
            "research_execution_id": source_contract["research_execution_id"],
            "preflight_execution_id": preflight_execution["execution_id"],
            "preflight_execution_artifact_digest": preflight_execution[
                "artifact_digest"
            ],
            "marginal_branch_design_digest": marginal_design["artifact_digest"],
            "marginal_branch_health_digest": branch_health["artifact_digest"],
            "preflight_execution_completion_digest": preflight_completion[
                "artifact_digest"
            ],
            "legacy_marginal_decision_digest": legacy_decision["artifact_digest"],
            "legacy_decision_replay_digest": legacy_replay["artifact_digest"],
            "marginal_static_measurement_contract_digest": run.measurement_contract[
                "artifact_digest"
            ],
            "marginal_static_contract_completion_digest": run.completion[
                "artifact_digest"
            ],
            "branch_id": "MARGINAL_STATIC",
            "estimator_id": "EXPANDING_LEGAL_MARGINAL_ALPHA_1",
            "identifiability_preflight_status": "PASS",
            "legacy_measurement_health": "REPAIR",
            "legacy_repair_overridden": False,
            "accepted_model_artifact_digest": None,
            "sampled_synthetic_execution_status": "NOT_AUTHORIZED",
            "historical_execution_status": "NOT_AUTHORIZED",
            "completion_fact": MARGINAL_STATIC_CONTRACT_FREEZE_COMPLETION_FACT,
            "actual_fold_count": 0,
            "registered_artifact_count": len(child_payloads) + 1,
            "formal_branch_runs_executed": 0,
            "synthetic_replicates": 0,
            "historical_outcomes_read": False,
            "p2_6_1_partial_statistical_results_read": False,
            "p2_6_3_statistical_results_read": False,
            "evidence_created": False,
            "evidence_progress_before": 0,
            "evidence_progress_after": 0,
            "downstream_consumer": MARGINAL_STATIC_FIXTURE_FREEZE_TASK_KEY,
            "production_impact": "none",
            "production_action": "none",
            "git_commit": git_commit,
            "working_tree_clean": True,
            "replay_status": "DETERMINISTIC",
            "parent_digests": [
                *task.input_artifact_digests,
                *(str(payload["artifact_digest"]) for _, payload in child_payloads),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        if len(registrations) != execution_payload["registered_artifact_count"]:
            raise MainlineSupervisorError(
                "M4 v2 marginal-static contract registration count changed"
            )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=(MARGINAL_STATIC_CONTRACT_FREEZE_COMPLETION_FACT,),
        )


class M4MarginalStaticFixtureFreezeCapability:
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository,
        root_dir: Path = ROOT_DIR,
    ) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != MARGINAL_STATIC_FIXTURE_FREEZE_TASK_KEY
            or task.requested_capability != MARGINAL_STATIC_FIXTURE_FREEZE_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "M4 v2 marginal-static fixture freeze received the wrong task"
            )
        source_contract = load_marginal_static_fixture_source_contract(
            self.root_dir / MARGINAL_STATIC_FIXTURE_SOURCE_CONTRACT_PATH
        )
        verify_marginal_static_fixture_source_bytes(
            root_dir=self.root_dir,
            contract=source_contract,
        )
        _, marginal_execution, marginal_registrations = (
            _load_single_completed_execution(
                repository=self.repository,
                root_dir=self.root_dir,
                control_plane_key=control_plane_key,
                task_key=MARGINAL_STATIC_CONTRACT_FREEZE_TASK_KEY,
            )
        )
        marginal_contract = _load_registered_type(
            root_dir=self.root_dir,
            registrations=marginal_registrations,
            artifact_type="m4_v2_marginal_static_measurement_contract",
        )
        marginal_completion = _load_registered_type(
            root_dir=self.root_dir,
            registrations=marginal_registrations,
            artifact_type="m4_v2_marginal_static_contract_freeze_completion",
        )
        _, _, fixture_registrations = _load_single_completed_execution(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=control_plane_key,
            task_key=FIXTURE_FREEZE_TASK_KEY,
        )
        orthogonal_fixture = _load_registered_type(
            root_dir=self.root_dir,
            registrations=fixture_registrations,
            artifact_type="m4_v2_orthogonal_control_fixture_contract",
        )
        fixture_completion = _load_registered_type(
            root_dir=self.root_dir,
            registrations=fixture_registrations,
            artifact_type="m4_v2_branch_fixture_freeze_completion",
        )
        _, _, preflight_registrations = _load_single_completed_execution(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=control_plane_key,
            task_key=PREFLIGHT_EXECUTION_TASK_KEY,
        )
        marginal_health = next(
            (
                item
                for item in _load_registered_type_group(
                    root_dir=self.root_dir,
                    registrations=preflight_registrations,
                    artifact_type="m4_v2_branch_health_preflight_result",
                )
                if item.get("branch_id") == "MARGINAL_STATIC"
            ),
            None,
        )
        if marginal_health is None:
            raise MainlineSupervisorError(
                "M4 v2 marginal-static fixture health lineage is missing"
            )
        preflight_completion = _load_registered_type(
            root_dir=self.root_dir,
            registrations=preflight_registrations,
            artifact_type="m4_v2_branch_preflight_execution_completion",
        )
        expected_inputs = (
            str(source_contract["artifact_digest"]),
            str(marginal_execution["artifact_digest"]),
            str(marginal_contract["artifact_digest"]),
            str(marginal_completion["artifact_digest"]),
            str(orthogonal_fixture["artifact_digest"]),
            str(fixture_completion["artifact_digest"]),
            str(marginal_health["artifact_digest"]),
            str(preflight_completion["artifact_digest"]),
        )
        if task.input_artifact_digests != expected_inputs:
            raise MainlineSupervisorError(
                "M4 v2 marginal-static fixture source identities changed"
            )
        if (
            marginal_execution.get("completion_fact")
            != MARGINAL_STATIC_CONTRACT_FREEZE_COMPLETION_FACT
            or marginal_execution.get("actual_fold_count") != 0
            or marginal_execution.get("synthetic_replicates") != 0
            or marginal_execution.get("historical_outcomes_read") is not False
            or marginal_execution.get("evidence_created") is not False
            or marginal_execution.get("legacy_repair_overridden") is not False
        ):
            raise MainlineSupervisorError(
                "M4 v2 marginal-static fixture parent execution changed"
            )
        run = build_marginal_static_fixture_artifacts(
            source_contract=source_contract,
            marginal_contract_execution_artifact_digest=str(
                marginal_execution["artifact_digest"]
            ),
            marginal_measurement_contract=marginal_contract,
            marginal_contract_completion=marginal_completion,
            orthogonal_fixture_contract=orthogonal_fixture,
            branch_fixture_completion=fixture_completion,
            marginal_branch_health=marginal_health,
            preflight_completion=preflight_completion,
            execution_id=execution_id,
            git_commit=git_commit,
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        child_payloads: list[tuple[Path, Mapping[str, Any]]] = []
        for fixture in run.fixtures:
            fixture_path = (
                task_dir
                / "artifacts/fixture"
                / str(fixture["fixture_id"])
                / str(fixture["artifact_digest"])
                / "fixture.json"
            )
            child_payloads.append((fixture_path, fixture))
        bundle_path = (
            task_dir
            / "artifacts/fixture-bundle"
            / str(run.bundle["artifact_digest"])
            / "bundle.json"
        )
        completion_path = (
            task_dir
            / "artifacts/completion"
            / str(run.completion["artifact_digest"])
            / "completion.json"
        )
        child_payloads.extend(
            ((bundle_path, run.bundle), (completion_path, run.completion))
        )
        for path, payload in child_payloads:
            _persist_immutable(path, payload)
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "marginal_static_fixture_source_contract_digest": source_contract[
                "artifact_digest"
            ],
            "marginal_static_fixture_source_set_digest": source_contract[
                "source_set_digest"
            ],
            "research_request_key": source_contract["research_request_key"],
            "research_request_id": source_contract["research_request_id"],
            "research_execution_id": source_contract["research_execution_id"],
            "marginal_contract_execution_id": marginal_execution["execution_id"],
            "marginal_contract_execution_artifact_digest": marginal_execution[
                "artifact_digest"
            ],
            "marginal_static_measurement_contract_digest": marginal_contract[
                "artifact_digest"
            ],
            "marginal_static_contract_completion_digest": marginal_completion[
                "artifact_digest"
            ],
            "orthogonal_fixture_contract_digest": orthogonal_fixture["artifact_digest"],
            "branch_fixture_completion_digest": fixture_completion["artifact_digest"],
            "marginal_branch_health_digest": marginal_health["artifact_digest"],
            "preflight_execution_completion_digest": preflight_completion[
                "artifact_digest"
            ],
            "marginal_static_fixture_digests": [
                item["artifact_digest"] for item in run.fixtures
            ],
            "marginal_static_fixture_bundle_digest": run.bundle["artifact_digest"],
            "marginal_static_fixture_completion_digest": run.completion[
                "artifact_digest"
            ],
            "fixture_count": len(run.fixtures),
            "positive_fixture_count": 1,
            "negative_fixture_count": 3,
            "branch_id": "MARGINAL_STATIC",
            "estimator_id": "EXPANDING_LEGAL_MARGINAL_ALPHA_1",
            "identifiability_preflight_status": "PASS",
            "legacy_measurement_health": "REPAIR",
            "legacy_repair_overridden": False,
            "accepted_model_artifact_digest": None,
            "sampled_synthetic_execution_status": "NOT_AUTHORIZED",
            "historical_execution_status": "NOT_AUTHORIZED",
            "runtime_state": (
                "issue_count plus ordered signed_int64[33] number-event counts"
            ),
            "database_reads_during_replicate": 0,
            "database_writes_during_replicate": 0,
            "csv_materialized": False,
            "duplicate_raw_replay": False,
            "routine_physical_checkpoint_scan": False,
            "sampled_workload_status": "NOT_FROZEN",
            "completion_fact": MARGINAL_STATIC_FIXTURE_FREEZE_COMPLETION_FACT,
            "generated_issues": 0,
            "synthetic_replicates": 0,
            "actual_fold_count": 0,
            "registered_artifact_count": len(child_payloads) + 1,
            "formal_branch_runs_executed": 0,
            "historical_outcomes_read": False,
            "p2_6_1_partial_statistical_results_read": False,
            "p2_6_3_statistical_results_read": False,
            "evidence_created": False,
            "evidence_progress_before": 0,
            "evidence_progress_after": 0,
            "downstream_consumer": MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY,
            "production_impact": "none",
            "production_action": "none",
            "git_commit": git_commit,
            "working_tree_clean": True,
            "replay_status": "DETERMINISTIC",
            "parent_digests": [
                *task.input_artifact_digests,
                *(str(payload["artifact_digest"]) for _, payload in child_payloads),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=tuple(child_payloads),
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        if len(registrations) != execution_payload["registered_artifact_count"]:
            raise MainlineSupervisorError(
                "M4 v2 marginal-static fixture registration count changed"
            )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=(MARGINAL_STATIC_FIXTURE_FREEZE_COMPLETION_FACT,),
        )


def _ordered_marginal_static_fixture_contracts(
    fixtures: tuple[dict[str, Any], ...],
) -> tuple[dict[str, Any], ...]:
    by_id = {str(item.get("fixture_id") or ""): item for item in fixtures}
    if (
        len(fixtures) != len(MARGINAL_STATIC_FIXTURE_ORDER)
        or len(by_id) != len(fixtures)
        or set(by_id) != set(MARGINAL_STATIC_FIXTURE_ORDER)
    ):
        raise MainlineSupervisorError(
            "M4 v2 marginal-static fixture registration identities changed"
        )
    return tuple(by_id[fixture_id] for fixture_id in MARGINAL_STATIC_FIXTURE_ORDER)


class M4MarginalStaticHealthDesignCapability:
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository,
        root_dir: Path = ROOT_DIR,
    ) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY
            or task.requested_capability != MARGINAL_STATIC_HEALTH_DESIGN_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "M4 v2 marginal-static health design received the wrong task"
            )
        source_contract = load_marginal_static_health_design_source_contract(
            self.root_dir / MARGINAL_STATIC_HEALTH_DESIGN_SOURCE_CONTRACT_PATH
        )
        verify_marginal_static_health_design_source_bytes(
            root_dir=self.root_dir,
            contract=source_contract,
        )
        _, fixture_execution, fixture_registrations = _load_single_completed_execution(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=control_plane_key,
            task_key=MARGINAL_STATIC_FIXTURE_FREEZE_TASK_KEY,
        )
        fixture_contracts = _ordered_marginal_static_fixture_contracts(
            _load_registered_type_group(
                root_dir=self.root_dir,
                registrations=fixture_registrations,
                artifact_type="m4_v2_marginal_static_measurement_fixture",
            )
        )
        fixture_bundle = _load_registered_type(
            root_dir=self.root_dir,
            registrations=fixture_registrations,
            artifact_type="m4_v2_marginal_static_fixture_bundle",
        )
        fixture_completion = _load_registered_type(
            root_dir=self.root_dir,
            registrations=fixture_registrations,
            artifact_type="m4_v2_marginal_static_fixture_freeze_completion",
        )
        expected_inputs = (
            str(source_contract["artifact_digest"]),
            str(fixture_execution["artifact_digest"]),
            *(str(item["artifact_digest"]) for item in fixture_contracts),
            str(fixture_bundle["artifact_digest"]),
            str(fixture_completion["artifact_digest"]),
        )
        if task.input_artifact_digests != expected_inputs:
            raise MainlineSupervisorError(
                "M4 v2 marginal-static health-design source identities changed"
            )
        if (
            fixture_execution.get("completion_fact")
            != MARGINAL_STATIC_FIXTURE_FREEZE_COMPLETION_FACT
            or fixture_execution.get("fixture_count") != 4
            or fixture_execution.get("generated_issues") != 0
            or fixture_execution.get("synthetic_replicates") != 0
            or fixture_execution.get("historical_outcomes_read") is not False
            or fixture_execution.get("evidence_created") is not False
            or fixture_execution.get("duplicate_raw_replay") is not False
            or fixture_execution.get("routine_physical_checkpoint_scan") is not False
        ):
            raise MainlineSupervisorError(
                "M4 v2 marginal-static health-design parent execution changed"
            )
        run = build_marginal_static_health_design_artifacts(
            source_contract=source_contract,
            fixture_execution_artifact_digest=str(fixture_execution["artifact_digest"]),
            fixture_contracts=fixture_contracts,
            fixture_bundle=fixture_bundle,
            fixture_completion=fixture_completion,
            execution_id=execution_id,
            git_commit=git_commit,
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        workload_path = (
            task_dir
            / "artifacts/workload-design"
            / str(run.workload["artifact_digest"])
            / "workload.json"
        )
        inference_path = (
            task_dir
            / "artifacts/inference-design"
            / str(run.inference["artifact_digest"])
            / "inference.json"
        )
        completion_path = (
            task_dir
            / "artifacts/completion"
            / str(run.completion["artifact_digest"])
            / "completion.json"
        )
        child_payloads = (
            (workload_path, run.workload),
            (inference_path, run.inference),
            (completion_path, run.completion),
        )
        for path, payload in child_payloads:
            _persist_immutable(path, payload)
        frozen_workload = source_contract["frozen_contract"]["workload"]
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "marginal_static_health_design_source_contract_digest": (
                source_contract["artifact_digest"]
            ),
            "marginal_static_health_design_source_set_digest": (
                source_contract["source_set_digest"]
            ),
            "research_request_key": source_contract["research_request_key"],
            "research_request_id": source_contract["research_request_id"],
            "research_execution_id": source_contract["research_execution_id"],
            "fixture_execution_id": fixture_execution["execution_id"],
            "fixture_execution_artifact_digest": fixture_execution["artifact_digest"],
            "marginal_static_fixture_digests": [
                item["artifact_digest"] for item in fixture_contracts
            ],
            "marginal_static_fixture_bundle_digest": fixture_bundle["artifact_digest"],
            "marginal_static_fixture_completion_digest": fixture_completion[
                "artifact_digest"
            ],
            "fixture_count": 4,
            "positive_fixture_count": 1,
            "negative_fixture_count": 3,
            "branch_id": "MARGINAL_STATIC",
            "estimator_id": "EXPANDING_LEGAL_MARGINAL_ALPHA_1",
            "identifiability_preflight_status": "PASS",
            "legacy_measurement_health": "REPAIR",
            "legacy_repair_overridden": False,
            "accepted_model_artifact_digest": None,
            "runtime_state": (
                "issue_count plus ordered signed_int64[33] number-event counts"
            ),
            "marginal_static_health_workload_digest": run.workload["artifact_digest"],
            "marginal_static_health_inference_digest": run.inference["artifact_digest"],
            "marginal_static_health_design_completion_digest": run.completion[
                "artifact_digest"
            ],
            "planned_total_replicates": frozen_workload["total_replicates"],
            "planned_total_generated_issues": frozen_workload[
                "total_generated_issues_if_executed"
            ],
            "planned_total_outer_evaluation_issues": frozen_workload[
                "total_outer_evaluation_issues_if_executed"
            ],
            "planned_execution_shards": frozen_workload["execution_shards"],
            "execution_shard_size": frozen_workload["execution_shard_size"],
            "bootstrap_replicates_per_interval": 511,
            "primary_block_size": 5,
            "sensitivity_block_sizes": [3, 8, 13],
            "legacy_replicates": 31000,
            "legacy_outer_issue_predictions": 64656000,
            "legacy_probe_fits_reused": False,
            "legacy_results_reused": False,
            "sampled_workload_status": "FROZEN_NOT_EXECUTED",
            "sampled_synthetic_execution_status": "NOT_AUTHORIZED",
            "historical_execution_status": "NOT_AUTHORIZED",
            "database_reads_during_replicate": 0,
            "database_writes_during_replicate": 0,
            "csv_materialized": False,
            "duplicate_raw_replay": False,
            "routine_physical_checkpoint_scan": False,
            "completion_index_loads": 0,
            "completion_fact": MARGINAL_STATIC_HEALTH_DESIGN_COMPLETION_FACT,
            "generated_issues": 0,
            "synthetic_replicates": 0,
            "bootstrap_replicates_executed": 0,
            "actual_fold_count": 0,
            "registered_artifact_count": len(child_payloads) + 1,
            "formal_branch_runs_executed": 0,
            "historical_outcomes_read": False,
            "p2_6_1_partial_statistical_results_read": False,
            "p2_6_3_statistical_results_read": False,
            "evidence_created": False,
            "evidence_progress_before": 0,
            "evidence_progress_after": 0,
            "downstream_consumer": MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY,
            "production_impact": "none",
            "production_action": "none",
            "git_commit": git_commit,
            "working_tree_clean": True,
            "replay_status": "DETERMINISTIC",
            "parent_digests": [
                *task.input_artifact_digests,
                *(str(payload["artifact_digest"]) for _, payload in child_payloads),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        if len(registrations) != execution_payload["registered_artifact_count"]:
            raise MainlineSupervisorError(
                "M4 v2 marginal-static health-design registration count changed"
            )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=(MARGINAL_STATIC_HEALTH_DESIGN_COMPLETION_FACT,),
        )


class M4MarginalStaticHealthExecutionCapability:
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository,
        root_dir: Path = ROOT_DIR,
    ) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY
            or task.requested_capability != MARGINAL_STATIC_HEALTH_EXECUTION_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "M4 v2 marginal-static health execution received the wrong task"
            )
        source_contract = load_marginal_static_health_execution_source_contract(
            self.root_dir / MARGINAL_STATIC_HEALTH_EXECUTION_SOURCE_CONTRACT_PATH
        )
        verify_marginal_static_health_execution_source_bytes(
            root_dir=self.root_dir,
            contract=source_contract,
        )
        _, design_execution, design_registrations = _load_single_completed_execution(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=control_plane_key,
            task_key=MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY,
        )
        workload = _load_registered_type(
            root_dir=self.root_dir,
            registrations=design_registrations,
            artifact_type="m4_v2_marginal_static_health_workload",
        )
        inference = _load_registered_type(
            root_dir=self.root_dir,
            registrations=design_registrations,
            artifact_type="m4_v2_marginal_static_health_inference",
        )
        design_completion = _load_registered_type(
            root_dir=self.root_dir,
            registrations=design_registrations,
            artifact_type="m4_v2_marginal_static_health_design_completion",
        )
        expected_inputs = (
            str(source_contract["artifact_digest"]),
            str(design_execution["artifact_digest"]),
            str(workload["artifact_digest"]),
            str(inference["artifact_digest"]),
            str(design_completion["artifact_digest"]),
        )
        if task.input_artifact_digests != expected_inputs:
            raise MainlineSupervisorError(
                "M4 v2 marginal-static health execution source identities changed"
            )
        if (
            design_execution.get("completion_fact")
            != MARGINAL_STATIC_HEALTH_DESIGN_COMPLETION_FACT
            or design_execution.get("generated_issues") != 0
            or design_execution.get("synthetic_replicates") != 0
            or design_execution.get("historical_outcomes_read") is not False
            or design_execution.get("evidence_created") is not False
            or design_execution.get("duplicate_raw_replay") is not False
            or design_execution.get("routine_physical_checkpoint_scan") is not False
        ):
            raise MainlineSupervisorError(
                "M4 v2 marginal-static health execution parent changed"
            )
        run = execute_health_program(
            root_dir=self.root_dir,
            task_key=task.task_key,
            execution_id=execution_id,
            git_commit=git_commit,
            task_digest=task.artifact_digest,
            source_contract=source_contract,
            workload_artifact=workload,
            inference_artifact=inference,
            design_completion=design_completion,
            design_execution_artifact_digest=str(design_execution["artifact_digest"]),
            progress_path=self.root_dir / MARGINAL_STATIC_HEALTH_PROGRESS_PATH,
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        index_path = (
            task_dir
            / "artifacts/completion-index"
            / str(run.index_artifact["artifact_digest"])
            / "index.json"
        )
        health_path = (
            task_dir
            / "artifacts/measurement-health"
            / str(run.health_result["artifact_digest"])
            / "result.json"
        )
        completion_path = (
            task_dir
            / "artifacts/completion"
            / str(run.completion["artifact_digest"])
            / "completion.json"
        )
        child_payloads = (
            (index_path, run.index_artifact),
            (health_path, run.health_result),
            (completion_path, run.completion),
        )
        for path, payload in child_payloads:
            _persist_immutable(path, payload)
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "marginal_static_health_execution_source_contract_digest": (
                source_contract["artifact_digest"]
            ),
            "marginal_static_health_execution_source_set_digest": source_contract[
                "source_set_digest"
            ],
            "research_request_key": source_contract["research_request_key"],
            "research_request_id": source_contract["research_request_id"],
            "research_execution_id": source_contract["research_execution_id"],
            "engineering_request_key": source_contract["engineering_request_key"],
            "engineering_request_id": source_contract["engineering_request_id"],
            "design_execution_id": design_execution["execution_id"],
            "design_execution_artifact_digest": design_execution["artifact_digest"],
            "marginal_static_health_workload_digest": workload["artifact_digest"],
            "marginal_static_health_inference_digest": inference["artifact_digest"],
            "marginal_static_health_design_completion_digest": design_completion[
                "artifact_digest"
            ],
            "marginal_static_fixture_bundle_digest": design_execution.get(
                "marginal_static_fixture_bundle_digest"
            ),
            "marginal_static_fixture_completion_digest": design_execution.get(
                "marginal_static_fixture_completion_digest"
            ),
            "fixture_count": design_execution.get("fixture_count", 4),
            "positive_fixture_count": design_execution.get("positive_fixture_count", 1),
            "negative_fixture_count": design_execution.get("negative_fixture_count", 3),
            "runtime_state": design_execution.get(
                "runtime_state",
                "issue_count plus ordered signed_int64[33] number-event counts",
            ),
            "marginal_static_health_completion_index_digest": run.index_artifact[
                "artifact_digest"
            ],
            "marginal_static_health_result_digest": run.health_result[
                "artifact_digest"
            ],
            "marginal_static_health_execution_completion_digest": run.completion[
                "artifact_digest"
            ],
            "branch_id": "MARGINAL_STATIC",
            "estimator_id": "EXPANDING_LEGAL_MARGINAL_ALPHA_1",
            "identifiability_preflight_status": "PASS",
            "legacy_measurement_health": "REPAIR",
            "legacy_repair_overridden": False,
            "measurement_health": run.health_result["measurement_health"],
            "replicate_count": run.health_result["replicate_count"],
            "generated_issues": run.health_result["generated_issues"],
            "outer_evaluation_issues": run.health_result["outer_evaluation_issues"],
            "completed_replicates_before_run": run.completed_before_run,
            "completed_replicates_during_run": run.completed_during_run,
            "execution_runtime_seconds": run.runtime_seconds,
            "worker_count": run.worker_count,
            "planned_execution_shards": 112,
            "execution_shard_size": 64,
            "bootstrap_replicates_per_interval": 511,
            "primary_block_size": 5,
            "sensitivity_block_sizes": [3, 8, 13],
            "completion_index_loads": 1,
            "database_reads_during_replicate": 0,
            "database_writes_during_replicate": 0,
            "csv_materialized": False,
            "duplicate_raw_replay": False,
            "routine_physical_checkpoint_scan": False,
            "historical_execution_status": "NOT_AUTHORIZED",
            "historical_outcomes_read": False,
            "statistical_results_read": False,
            "evidence_created": False,
            "accepted_model_artifact_digest": None,
            "completion_fact": MARGINAL_STATIC_HEALTH_EXECUTION_COMPLETION_FACT,
            "actual_fold_count": 0,
            "registered_artifact_count": len(child_payloads) + 1,
            "formal_branch_runs_executed": 1,
            "downstream_consumer": MARGINAL_STATIC_HEALTH_DECISION_TASK_KEY,
            "production_impact": "none",
            "production_action": "none",
            "git_commit": git_commit,
            "working_tree_clean": True,
            "replay_status": "COMPACT_INDEX_PLUS_SENTINEL",
            "parent_digests": [
                *task.input_artifact_digests,
                *(str(payload["artifact_digest"]) for _, payload in child_payloads),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        if len(registrations) != execution_payload["registered_artifact_count"]:
            raise MainlineSupervisorError(
                "M4 v2 marginal-static health execution registration count changed"
            )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=(MARGINAL_STATIC_HEALTH_EXECUTION_COMPLETION_FACT,),
        )


class M4MarginalStaticHealthDecisionCapability:
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository,
        root_dir: Path = ROOT_DIR,
    ) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != MARGINAL_STATIC_HEALTH_DECISION_TASK_KEY
            or task.requested_capability != MARGINAL_STATIC_HEALTH_DECISION_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "M4 v2 marginal-static health decision received the wrong task"
            )
        source_contract = load_marginal_static_health_decision_source_contract(
            self.root_dir / MARGINAL_STATIC_HEALTH_DECISION_SOURCE_CONTRACT_PATH
        )
        verify_marginal_static_health_decision_source_bytes(
            root_dir=self.root_dir,
            contract=source_contract,
        )
        _, health_execution, health_registrations = _load_single_completed_execution(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=control_plane_key,
            task_key=MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY,
        )
        health_result = _load_registered_type(
            root_dir=self.root_dir,
            registrations=health_registrations,
            artifact_type="m4_v2_marginal_static_measurement_health_result",
        )
        health_completion = _load_registered_type(
            root_dir=self.root_dir,
            registrations=health_registrations,
            artifact_type="m4_v2_marginal_static_health_execution_completion",
        )
        expected_inputs = (
            str(source_contract["artifact_digest"]),
            MARGINAL_STATIC_DECISION_CONTRACT_DIGEST,
            str(health_execution["artifact_digest"]),
            str(health_result["artifact_digest"]),
            str(health_completion["artifact_digest"]),
        )
        if task.input_artifact_digests != expected_inputs:
            raise MainlineSupervisorError(
                "M4 v2 marginal-static health decision identities changed"
            )
        decision = build_marginal_static_health_decision(
            source_contract=source_contract,
            health_execution=health_execution,
            health_result=health_result,
            health_completion=health_completion,
        )
        return _persist_small_capability(
            root_dir=self.root_dir,
            owner=self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_name="marginal-static-health-decision",
            child_filename="decision.json",
            child_payload=decision,
            completion_fact=str(decision["decision_fact"]),
            downstream_consumer=str(decision["next_consumer"]),
            extra_execution={
                "marginal_static_health_decision_source_contract_digest": (
                    source_contract["artifact_digest"]
                ),
                "marginal_static_health_decision_source_set_digest": source_contract[
                    "source_set_digest"
                ],
                "health_execution_artifact_digest": health_execution["artifact_digest"],
                "health_result_digest": health_result["artifact_digest"],
                "health_completion_digest": health_completion["artifact_digest"],
                "marginal_static_health_decision_artifact_digest": decision[
                    "artifact_digest"
                ],
                "decision": decision["decision"],
                "decision_fact": decision["decision_fact"],
                "measurement_health": decision["measurement_health"],
                "failed_cell_ids": decision["failed_cell_ids"],
                "failed_cell_count": decision["failed_cell_count"],
                "eligible_for_historical_measurement": decision[
                    "eligible_for_historical_measurement"
                ],
                "accepted_model_artifact_digest": None,
                "historical_evidence": "NOT_RUN",
                "historical_execution_status": "NOT_AUTHORIZED",
                "statistical_results_read": True,
                "generated_issues": 0,
                "compact_index_reads": 0,
                "sentinel_replicates_recomputed": 0,
                "duplicate_validation": False,
                "promotion_gate_opened": False,
                "repair_required": decision["measurement_health"] == "REPAIR",
                "production_action": "none",
                "replay_status": "DETERMINISTIC_DECISION_ONLY",
            },
        )


class M4MarginalStaticRepairDesignCapability:
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository,
        root_dir: Path = ROOT_DIR,
    ) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != MARGINAL_STATIC_REPAIR_DESIGN_TASK_KEY
            or task.requested_capability != MARGINAL_STATIC_REPAIR_DESIGN_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "M4 v2 marginal-static repair design received the wrong task"
            )
        source_contract = load_marginal_static_repair_design_source_contract(
            self.root_dir / MARGINAL_STATIC_REPAIR_DESIGN_SOURCE_CONTRACT_PATH
        )
        verify_marginal_static_repair_design_source_bytes(
            root_dir=self.root_dir,
            contract=source_contract,
        )
        _, decision_execution, decision_registrations = (
            _load_single_completed_execution(
                repository=self.repository,
                root_dir=self.root_dir,
                control_plane_key=control_plane_key,
                task_key=MARGINAL_STATIC_HEALTH_DECISION_TASK_KEY,
            )
        )
        decision = _load_registered_type(
            root_dir=self.root_dir,
            registrations=decision_registrations,
            artifact_type="m4_v2_marginal_static_measurement_health_decision",
        )
        expected_inputs = (
            str(source_contract["artifact_digest"]),
            str(decision_execution["artifact_digest"]),
            str(decision["artifact_digest"]),
        )
        if task.input_artifact_digests != expected_inputs:
            raise MainlineSupervisorError(
                "M4 v2 marginal-static repair design identities changed"
            )
        run = build_marginal_static_repair_design_artifacts(
            source_contract=source_contract,
            health_decision_execution=decision_execution,
            health_decision=decision,
            execution_id=execution_id,
            git_commit=git_commit,
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        feasibility_path = (
            task_dir
            / "artifacts/analytic-feasibility"
            / str(run.feasibility["artifact_digest"])
            / "feasibility.json"
        )
        repair_design_path = (
            task_dir
            / "artifacts/repair-design"
            / str(run.repair_design["artifact_digest"])
            / "repair-design.json"
        )
        completion_path = (
            task_dir
            / "artifacts/completion"
            / str(run.completion["artifact_digest"])
            / "completion.json"
        )
        child_payloads = (
            (feasibility_path, run.feasibility),
            (repair_design_path, run.repair_design),
            (completion_path, run.completion),
        )
        for path, payload in child_payloads:
            _persist_immutable(path, payload)
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "marginal_static_repair_design_source_contract_digest": (
                source_contract["artifact_digest"]
            ),
            "marginal_static_repair_design_source_set_digest": source_contract[
                "source_set_digest"
            ],
            "research_request_key": source_contract["research_request_key"],
            "research_request_id": source_contract["research_request_id"],
            "research_execution_id": source_contract["research_execution_id"],
            "health_decision_execution_id": decision_execution["execution_id"],
            "health_decision_execution_artifact_digest": decision_execution[
                "artifact_digest"
            ],
            "health_decision_artifact_digest": decision["artifact_digest"],
            "old_measurement_health": "REPAIR",
            "old_decision_preserved": "REPAIR_MEASUREMENT_SYSTEM",
            "measurement_health": "REPAIR",
            "decision": "REPAIR_MEASUREMENT_SYSTEM",
            "decision_fact": MARGINAL_STATIC_HEALTH_DECISION_REPAIR_FACT,
            "eligible_for_historical_measurement": False,
            "failed_cell_ids": decision["failed_cell_ids"],
            "failed_cell_count": decision["failed_cell_count"],
            "marginal_static_repair_analytic_feasibility_digest": run.feasibility[
                "artifact_digest"
            ],
            "marginal_static_repair_design_artifact_digest": run.repair_design[
                "artifact_digest"
            ],
            "marginal_static_repair_design_completion_digest": run.completion[
                "artifact_digest"
            ],
            "forward_61_gate_admissible": {"0.010": False, "0.050": False},
            "forward_61_classification": "ANALYTICALLY_INFEASIBLE",
            "independent_root_seed_domain": ("M4_V2_MARGINAL_STATIC_REPAIR_HEALTH_V1"),
            "independent_bootstrap_seed_domain": (
                "M4_V2_MARGINAL_STATIC_REPAIR_HEALTH_BOOTSTRAP_V1"
            ),
            "round_42_seed_reuse": False,
            "automatic_pass_from_reanalysis": False,
            "same_seed_tuning": "forbidden",
            "posthoc_threshold_change": "forbidden",
            "completion_fact": MARGINAL_STATIC_REPAIR_DESIGN_COMPLETION_FACT,
            "generated_issues": 0,
            "synthetic_replicates": 0,
            "checkpoint_reads": 0,
            "compact_index_reads": 0,
            "sentinel_replicates_recomputed": 0,
            "duplicate_validation": False,
            "actual_fold_count": 0,
            "registered_artifact_count": len(child_payloads) + 1,
            "formal_branch_runs_executed": 0,
            "historical_outcomes_read": False,
            "statistical_results_read": True,
            "p2_6_1_partial_statistical_results_read": False,
            "evidence_created": False,
            "evidence_progress_before": 0,
            "evidence_progress_after": 0,
            "accepted_model_artifact_digest": None,
            "promotion_gate_opened": False,
            "downstream_consumer": MARGINAL_STATIC_REPAIR_PREREGISTRATION_TASK_KEY,
            "production_impact": "none",
            "production_action": "none",
            "git_commit": git_commit,
            "working_tree_clean": True,
            "replay_status": "DETERMINISTIC_DESIGN_ONLY",
            "parent_digests": [
                *task.input_artifact_digests,
                *(str(payload["artifact_digest"]) for _, payload in child_payloads),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        if len(registrations) != execution_payload["registered_artifact_count"]:
            raise MainlineSupervisorError(
                "M4 v2 marginal-static repair-design registration count changed"
            )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=(MARGINAL_STATIC_REPAIR_DESIGN_COMPLETION_FACT,),
        )


class M4MarginalStaticRepairPreregistrationCapability:
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository,
        root_dir: Path = ROOT_DIR,
    ) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != MARGINAL_STATIC_REPAIR_PREREGISTRATION_TASK_KEY
            or task.requested_capability
            != MARGINAL_STATIC_REPAIR_PREREGISTRATION_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "M4 v2 marginal-static repair preregistration received the wrong task"
            )
        source_contract = load_marginal_static_repair_preregistration_source_contract(
            self.root_dir / MARGINAL_STATIC_REPAIR_PREREGISTRATION_SOURCE_CONTRACT_PATH
        )
        verify_marginal_static_repair_preregistration_source_bytes(
            root_dir=self.root_dir,
            contract=source_contract,
        )
        _, repair_execution, repair_registrations = _load_single_completed_execution(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=control_plane_key,
            task_key=MARGINAL_STATIC_REPAIR_DESIGN_TASK_KEY,
        )
        feasibility = _load_registered_type(
            root_dir=self.root_dir,
            registrations=repair_registrations,
            artifact_type="m4_v2_marginal_static_repair_analytic_feasibility",
        )
        repair_design = _load_registered_type(
            root_dir=self.root_dir,
            registrations=repair_registrations,
            artifact_type="m4_v2_marginal_static_measurement_repair_design",
        )
        repair_completion = _load_registered_type(
            root_dir=self.root_dir,
            registrations=repair_registrations,
            artifact_type="m4_v2_marginal_static_repair_design_completion",
        )
        expected_inputs = (
            str(source_contract["artifact_digest"]),
            str(repair_execution["artifact_digest"]),
            str(feasibility["artifact_digest"]),
            str(repair_design["artifact_digest"]),
            str(repair_completion["artifact_digest"]),
        )
        if task.input_artifact_digests != expected_inputs:
            raise MainlineSupervisorError(
                "M4 v2 marginal-static repair preregistration identities changed"
            )
        run = build_marginal_static_repair_preregistration_artifacts(
            source_contract=source_contract,
            repair_design_execution=repair_execution,
            analytic_feasibility=feasibility,
            repair_design=repair_design,
            repair_design_completion=repair_completion,
            execution_id=execution_id,
            git_commit=git_commit,
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        workload_path = (
            task_dir
            / "artifacts/workload-seeds"
            / str(run.workload_and_seeds["artifact_digest"])
            / "workload-seeds.json"
        )
        inference_path = (
            task_dir
            / "artifacts/inference-gates"
            / str(run.inference_and_gates["artifact_digest"])
            / "inference-gates.json"
        )
        preregistration_path = (
            task_dir
            / "artifacts/preregistration"
            / str(run.preregistration["artifact_digest"])
            / "preregistration.json"
        )
        completion_path = (
            task_dir
            / "artifacts/completion"
            / str(run.completion["artifact_digest"])
            / "completion.json"
        )
        child_payloads = (
            (workload_path, run.workload_and_seeds),
            (inference_path, run.inference_and_gates),
            (preregistration_path, run.preregistration),
            (completion_path, run.completion),
        )
        for path, payload in child_payloads:
            _persist_immutable(path, payload)
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "marginal_static_repair_preregistration_source_contract_digest": (
                source_contract["artifact_digest"]
            ),
            "marginal_static_repair_preregistration_source_set_digest": (
                source_contract["source_set_digest"]
            ),
            "research_request_key": source_contract["research_request_key"],
            "research_request_id": source_contract["research_request_id"],
            "research_execution_id": source_contract["research_execution_id"],
            "research_addendum_key": source_contract["research_addendum_key"],
            "research_addendum_request_id": source_contract[
                "research_addendum_request_id"
            ],
            "research_addendum_execution_id": source_contract[
                "research_addendum_execution_id"
            ],
            "repair_design_execution_id": repair_execution["execution_id"],
            "repair_design_execution_artifact_digest": repair_execution[
                "artifact_digest"
            ],
            "repair_analytic_feasibility_digest": feasibility["artifact_digest"],
            "repair_design_artifact_digest": repair_design["artifact_digest"],
            "repair_design_completion_digest": repair_completion["artifact_digest"],
            "marginal_static_repair_analytic_feasibility_digest": feasibility[
                "artifact_digest"
            ],
            "marginal_static_repair_design_artifact_digest": repair_design[
                "artifact_digest"
            ],
            "marginal_static_repair_design_completion_digest": repair_completion[
                "artifact_digest"
            ],
            "old_measurement_health": "REPAIR",
            "old_decision_preserved": "REPAIR_MEASUREMENT_SYSTEM",
            "measurement_health": "REPAIR",
            "decision": repair_execution["decision"],
            "decision_fact": repair_execution["decision_fact"],
            "failed_cell_ids": repair_execution["failed_cell_ids"],
            "failed_cell_count": repair_execution["failed_cell_count"],
            "repair_required": True,
            "eligible_for_historical_measurement": False,
            "marginal_static_repair_health_workload_seed_digest": (
                run.workload_and_seeds["artifact_digest"]
            ),
            "marginal_static_repair_health_inference_gate_digest": (
                run.inference_and_gates["artifact_digest"]
            ),
            "marginal_static_repair_health_preregistration_digest": (
                run.preregistration["artifact_digest"]
            ),
            "marginal_static_repair_health_preregistration_completion_digest": (
                run.completion["artifact_digest"]
            ),
            "planned_calibration_replicates": CALIBRATION_REPLICATES,
            "planned_evaluation_replicates": EVALUATION_REPLICATES,
            "planned_total_replicates": TOTAL_REPLICATES,
            "planned_total_generated_issues": TOTAL_GENERATED_ISSUES,
            "planned_total_outer_evaluation_issues": (TOTAL_OUTER_EVALUATION_ISSUES),
            "planned_execution_shards": EXECUTION_SHARDS,
            "execution_shard_size": EXECUTION_SHARD_SIZE,
            "max_rejecting_exceedance_count": 24,
            "nested_bootstrap_replicates_per_formal_replicate": 0,
            "independent_root_seed_domain": ("M4_V2_MARGINAL_STATIC_REPAIR_HEALTH_V1"),
            "independent_calibration_seed_domain": (
                "M4_V2_MARGINAL_STATIC_REPAIR_HEALTH_CALIBRATION_V1"
            ),
            "independent_evaluation_seed_domain": (
                "M4_V2_MARGINAL_STATIC_REPAIR_HEALTH_EVALUATION_V1"
            ),
            "round_42_seed_reuse": False,
            "calibration_evaluation_seed_overlap": False,
            "formal_execution_authorized": False,
            "automatic_pass_from_preregistration": False,
            "completion_fact": (MARGINAL_STATIC_REPAIR_PREREGISTRATION_COMPLETION_FACT),
            "generated_issues": 0,
            "synthetic_replicates": 0,
            "bootstrap_replicates_executed": 0,
            "checkpoint_reads": 0,
            "compact_index_reads": 0,
            "sentinel_replicates_recomputed": 0,
            "duplicate_validation": False,
            "actual_fold_count": 0,
            "registered_artifact_count": len(child_payloads) + 1,
            "formal_branch_runs_executed": 0,
            "historical_outcomes_read": False,
            "statistical_results_read": False,
            "evidence_created": False,
            "evidence_progress_before": 0,
            "evidence_progress_after": 0,
            "accepted_model_artifact_digest": None,
            "promotion_gate_opened": False,
            "downstream_consumer": MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_TASK_KEY,
            "production_impact": "none",
            "production_action": "none",
            "git_commit": git_commit,
            "working_tree_clean": True,
            "replay_status": "DETERMINISTIC_PREREGISTRATION_ONLY",
            "parent_digests": [
                *task.input_artifact_digests,
                *(str(payload["artifact_digest"]) for _, payload in child_payloads),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        if len(registrations) != execution_payload["registered_artifact_count"]:
            raise MainlineSupervisorError(
                "M4 v2 marginal-static repair preregistration registration "
                "count changed"
            )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=(MARGINAL_STATIC_REPAIR_PREREGISTRATION_COMPLETION_FACT,),
        )


class M4MarginalStaticRepairHealthExecutionCapability:
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository,
        root_dir: Path = ROOT_DIR,
    ) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_TASK_KEY
            or task.requested_capability
            != MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "M4 v2 marginal-static repair health execution received the wrong task"
            )
        source_contract = load_marginal_static_repair_health_execution_source_contract(
            self.root_dir / MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_SOURCE_CONTRACT_PATH
        )
        verify_marginal_static_repair_health_execution_source_bytes(
            root_dir=self.root_dir,
            contract=source_contract,
        )
        _, preregistration_execution, preregistration_registrations = (
            _load_single_completed_execution(
                repository=self.repository,
                root_dir=self.root_dir,
                control_plane_key=control_plane_key,
                task_key=MARGINAL_STATIC_REPAIR_PREREGISTRATION_TASK_KEY,
            )
        )
        workload = _load_registered_type(
            root_dir=self.root_dir,
            registrations=preregistration_registrations,
            artifact_type="m4_v2_marginal_static_repair_health_workload_seeds",
        )
        inference = _load_registered_type(
            root_dir=self.root_dir,
            registrations=preregistration_registrations,
            artifact_type="m4_v2_marginal_static_repair_health_inference_gates",
        )
        preregistration = _load_registered_type(
            root_dir=self.root_dir,
            registrations=preregistration_registrations,
            artifact_type="m4_v2_marginal_static_repair_health_preregistration",
        )
        preregistration_completion = _load_registered_type(
            root_dir=self.root_dir,
            registrations=preregistration_registrations,
            artifact_type=(
                "m4_v2_marginal_static_repair_health_preregistration_completion"
            ),
        )
        expected_inputs = (
            str(source_contract["artifact_digest"]),
            str(preregistration_execution["artifact_digest"]),
            str(workload["artifact_digest"]),
            str(inference["artifact_digest"]),
            str(preregistration["artifact_digest"]),
            str(preregistration_completion["artifact_digest"]),
        )
        if task.input_artifact_digests != expected_inputs:
            raise MainlineSupervisorError(
                "M4 v2 marginal-static repair health execution identities changed"
            )
        if (
            preregistration_execution.get("completion_fact")
            != MARGINAL_STATIC_REPAIR_PREREGISTRATION_COMPLETION_FACT
            or preregistration_execution.get("generated_issues") != 0
            or preregistration_execution.get("synthetic_replicates") != 0
            or preregistration_execution.get("formal_execution_authorized") is not False
            or preregistration_execution.get("duplicate_validation") is not False
            or preregistration_execution.get("historical_outcomes_read") is not False
            or preregistration_execution.get("evidence_created") is not False
            or preregistration_execution.get("promotion_gate_opened") is not False
        ):
            raise MainlineSupervisorError(
                "M4 v2 marginal-static repair health preregistration parent changed"
            )
        run = execute_repair_health_program(
            root_dir=self.root_dir,
            task_key=task.task_key,
            execution_id=execution_id,
            git_commit=git_commit,
            task_digest=task.artifact_digest,
            source_contract=source_contract,
            preregistration_execution=preregistration_execution,
            workload_artifact=workload,
            inference_artifact=inference,
            preregistration_artifact=preregistration,
            preregistration_completion=preregistration_completion,
            progress_path=self.root_dir / MARGINAL_STATIC_REPAIR_HEALTH_PROGRESS_PATH,
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        index_path = (
            task_dir
            / "artifacts/completion-index"
            / str(run.index_artifact["artifact_digest"])
            / "index.json"
        )
        feasibility_path = (
            task_dir
            / "artifacts/pre-sample-feasibility"
            / str(run.feasibility_artifact["artifact_digest"])
            / "feasibility.json"
        )
        health_path = (
            task_dir
            / "artifacts/measurement-health"
            / str(run.health_result["artifact_digest"])
            / "result.json"
        )
        completion_path = (
            task_dir
            / "artifacts/completion"
            / str(run.completion["artifact_digest"])
            / "completion.json"
        )
        child_payloads = (
            (index_path, run.index_artifact),
            (feasibility_path, run.feasibility_artifact),
            (health_path, run.health_result),
            (completion_path, run.completion),
        )
        for path, payload in child_payloads:
            _persist_immutable(path, payload)
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "marginal_static_repair_health_execution_source_contract_digest": (
                source_contract["artifact_digest"]
            ),
            "marginal_static_repair_health_execution_source_set_digest": (
                source_contract["source_set_digest"]
            ),
            "research_request_key": source_contract["research_request_key"],
            "research_request_id": source_contract["research_request_id"],
            "research_execution_id": source_contract["research_execution_id"],
            "engineering_request_key": source_contract["engineering_request_key"],
            "engineering_request_id": source_contract["engineering_request_id"],
            "engineering_execution_id": source_contract["engineering_execution_id"],
            "repair_preregistration_execution_id": preregistration_execution[
                "execution_id"
            ],
            "repair_preregistration_execution_artifact_digest": (
                preregistration_execution["artifact_digest"]
            ),
            "marginal_static_repair_health_workload_seed_digest": workload[
                "artifact_digest"
            ],
            "marginal_static_repair_health_inference_gate_digest": inference[
                "artifact_digest"
            ],
            "marginal_static_repair_health_preregistration_digest": preregistration[
                "artifact_digest"
            ],
            "marginal_static_repair_health_preregistration_completion_digest": (
                preregistration_completion["artifact_digest"]
            ),
            "marginal_static_repair_health_completion_index_digest": (
                run.index_artifact["artifact_digest"]
            ),
            "marginal_static_repair_health_feasibility_digest": (
                run.feasibility_artifact["artifact_digest"]
            ),
            "marginal_static_repair_health_result_digest": run.health_result[
                "artifact_digest"
            ],
            "marginal_static_repair_health_execution_completion_digest": (
                run.completion["artifact_digest"]
            ),
            "old_measurement_health": "REPAIR",
            "old_decision_preserved": "REPAIR_MEASUREMENT_SYSTEM",
            "measurement_health": "REPAIR",
            "decision": preregistration_execution["decision"],
            "decision_fact": preregistration_execution["decision_fact"],
            "repair_health_preliminary_measurement_health": run.health_result[
                "preliminary_measurement_health"
            ],
            "repair_health_authoritative_decision": None,
            "eligible_for_historical_measurement": False,
            "repair_required": True,
            "failed_cell_ids": preregistration_execution["failed_cell_ids"],
            "failed_cell_count": preregistration_execution["failed_cell_count"],
            "replicate_count": run.health_result["replicate_count"],
            "calibration_replicates": CALIBRATION_REPLICATES,
            "evaluation_replicates": EVALUATION_REPLICATES,
            "generated_issues": run.health_result["generated_issues"],
            "outer_evaluation_issues": run.health_result["outer_evaluation_issues"],
            "completed_replicates_before_run": run.completed_before_run,
            "completed_replicates_during_run": run.completed_during_run,
            "execution_runtime_seconds": run.runtime_seconds,
            "worker_count": run.worker_count,
            "planned_execution_shards": EXECUTION_SHARDS,
            "execution_shard_size": EXECUTION_SHARD_SIZE,
            "nested_bootstrap_replicates_per_formal_replicate": 0,
            "checkpoint_mode": "compact_index_direct_resume_without_scan",
            "completion_index_loads": 1,
            "compact_index_reads": 1,
            "checkpoint_reads": 1,
            "sentinel_replicates_recomputed": 0,
            "database_reads_during_replicate": 0,
            "database_writes_during_replicate": 0,
            "csv_materialized": False,
            "duplicate_raw_replay": False,
            "duplicate_validation": False,
            "routine_physical_checkpoint_scan": False,
            "round_42_seed_reuse": False,
            "round_42_statistical_results_read": False,
            "historical_execution_status": "NOT_AUTHORIZED",
            "historical_outcomes_read": False,
            "statistical_results_read": False,
            "evidence_created": False,
            "evidence_progress_before": 0,
            "evidence_progress_after": 0,
            "accepted_model_artifact_digest": None,
            "promotion_gate_opened": False,
            "completion_fact": MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_COMPLETION_FACT,
            "actual_fold_count": 0,
            "registered_artifact_count": len(child_payloads) + 1,
            "formal_branch_runs_executed": 1,
            "downstream_consumer": MARGINAL_STATIC_REPAIR_HEALTH_DECISION_TASK_KEY,
            "production_impact": "none",
            "production_action": "none",
            "git_commit": git_commit,
            "working_tree_clean": True,
            "replay_status": "COMPACT_INDEX_AGGREGATE_ONLY",
            "parent_digests": [
                *task.input_artifact_digests,
                *(str(payload["artifact_digest"]) for _, payload in child_payloads),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        if len(registrations) != execution_payload["registered_artifact_count"]:
            raise MainlineSupervisorError(
                "M4 v2 marginal-static repair health registration count changed"
            )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=(MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_COMPLETION_FACT,),
        )


class M4MarginalStaticRepairHealthDecisionCapability:
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository,
        root_dir: Path = ROOT_DIR,
    ) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != MARGINAL_STATIC_REPAIR_HEALTH_DECISION_TASK_KEY
            or task.requested_capability
            != MARGINAL_STATIC_REPAIR_HEALTH_DECISION_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "M4 v2 marginal-static repair health decision received the wrong task"
            )
        source_contract = load_marginal_static_repair_health_decision_source_contract(
            self.root_dir / MARGINAL_STATIC_REPAIR_HEALTH_DECISION_SOURCE_CONTRACT_PATH
        )
        verify_marginal_static_repair_health_decision_source_bytes(
            root_dir=self.root_dir,
            contract=source_contract,
        )
        _, health_execution, health_registrations = _load_single_completed_execution(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=control_plane_key,
            task_key=MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_TASK_KEY,
        )
        health_result = _load_registered_type(
            root_dir=self.root_dir,
            registrations=health_registrations,
            artifact_type=("m4_v2_marginal_static_repaired_measurement_health_result"),
        )
        health_completion = _load_registered_type(
            root_dir=self.root_dir,
            registrations=health_registrations,
            artifact_type=("m4_v2_marginal_static_repair_health_execution_completion"),
        )
        expected_inputs = (
            str(source_contract["artifact_digest"]),
            str(health_execution["artifact_digest"]),
            str(health_result["artifact_digest"]),
            str(health_completion["artifact_digest"]),
        )
        if task.input_artifact_digests != expected_inputs:
            raise MainlineSupervisorError(
                "M4 v2 marginal-static repair health decision identities changed"
            )
        decision = build_marginal_static_repair_health_decision(
            source_contract=source_contract,
            health_execution=health_execution,
            health_result=health_result,
            health_completion=health_completion,
        )
        return _persist_small_capability(
            root_dir=self.root_dir,
            owner=self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_name="marginal-static-repair-health-decision",
            child_filename="decision.json",
            child_payload=decision,
            completion_fact=str(decision["decision_fact"]),
            downstream_consumer=str(decision["next_consumer"]),
            extra_execution={
                "marginal_static_repair_health_decision_source_contract_digest": (
                    source_contract["artifact_digest"]
                ),
                "marginal_static_repair_health_decision_source_set_digest": (
                    source_contract["source_set_digest"]
                ),
                "repair_health_execution_artifact_digest": health_execution[
                    "artifact_digest"
                ],
                "repair_health_result_digest": health_result["artifact_digest"],
                "repair_health_completion_digest": health_completion["artifact_digest"],
                "marginal_static_repair_health_decision_artifact_digest": decision[
                    "artifact_digest"
                ],
                "authoritative_decision": decision["authoritative_decision"],
                "decision": decision["decision"],
                "decision_fact": decision["decision_fact"],
                "measurement_health": decision["measurement_health"],
                "failed_control_cell_ids": decision["failed_control_cell_ids"],
                "failed_control_topology": decision["failed_control_topology"],
                "failed_control_cell_count": decision["failed_control_cell_count"],
                "instrument_limit_cell_count": decision["instrument_limit_cell_count"],
                "eligible_for_historical_measurement": decision[
                    "eligible_for_historical_measurement"
                ],
                "accepted_model_artifact_digest": None,
                "historical_evidence": "NOT_RUN",
                "historical_execution_status": "NOT_AUTHORIZED",
                "statistical_results_read": True,
                "generated_issues": 0,
                "compact_index_reads": 0,
                "raw_replicates_regenerated": 0,
                "sentinel_replicates_recomputed": 0,
                "duplicate_validation": False,
                "promotion_gate_opened": False,
                "repair_required": decision["measurement_health"] == "REPAIR",
                "production_action": "none",
                "replay_status": "DETERMINISTIC_DECISION_ONLY",
            },
        )


class M4MarginalStaticRepairV2DesignCapability:
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository,
        root_dir: Path = ROOT_DIR,
    ) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != MARGINAL_STATIC_REPAIR_V2_DESIGN_TASK_KEY
            or task.requested_capability != MARGINAL_STATIC_REPAIR_V2_DESIGN_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "M4 v2 marginal-static repair-v2 design received the wrong task"
            )
        source_contract = load_marginal_static_repair_v2_design_source_contract(
            self.root_dir / MARGINAL_STATIC_REPAIR_V2_DESIGN_SOURCE_CONTRACT_PATH
        )
        verify_marginal_static_repair_v2_design_source_bytes(
            root_dir=self.root_dir,
            contract=source_contract,
        )
        _, decision_execution, decision_registrations = (
            _load_single_completed_execution(
                repository=self.repository,
                root_dir=self.root_dir,
                control_plane_key=control_plane_key,
                task_key=REPAIR_HEALTH_DECISION_TASK_KEY,
            )
        )
        decision = _load_registered_type(
            root_dir=self.root_dir,
            registrations=decision_registrations,
            artifact_type=("m4_v2_marginal_static_measurement_repair_health_decision"),
        )
        expected_inputs = (
            str(source_contract["artifact_digest"]),
            str(decision_execution["artifact_digest"]),
            str(decision["artifact_digest"]),
        )
        if task.input_artifact_digests != expected_inputs:
            raise MainlineSupervisorError(
                "M4 v2 marginal-static repair-v2 design identities changed"
            )
        run = build_marginal_static_repair_v2_design_artifacts(
            source_contract=source_contract,
            repair_health_decision_execution=decision_execution,
            repair_health_decision=decision,
            execution_id=execution_id,
            git_commit=git_commit,
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        feasibility_path = (
            task_dir
            / "artifacts/presample-feasibility"
            / str(run.presample_feasibility["artifact_digest"])
            / "feasibility.json"
        )
        design_path = (
            task_dir
            / "artifacts/repair-v2-design"
            / str(run.repair_v2_design["artifact_digest"])
            / "repair-v2-design.json"
        )
        completion_path = (
            task_dir
            / "artifacts/completion"
            / str(run.completion["artifact_digest"])
            / "completion.json"
        )
        child_payloads = (
            (feasibility_path, run.presample_feasibility),
            (design_path, run.repair_v2_design),
            (completion_path, run.completion),
        )
        for path, payload in child_payloads:
            _persist_immutable(path, payload)
        workload = source_contract["frozen_contract"]["future_workload"]
        proof = source_contract["frozen_contract"]["presample_sample_size_proof"]
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "marginal_static_repair_v2_design_source_contract_digest": (
                source_contract["artifact_digest"]
            ),
            "marginal_static_repair_v2_design_source_set_digest": source_contract[
                "source_set_digest"
            ],
            "research_request_key": source_contract["research_request_key"],
            "research_request_id": source_contract["research_request_id"],
            "research_execution_id": source_contract["research_execution_id"],
            "engineering_request_key": source_contract["engineering_request_key"],
            "engineering_request_id": source_contract["engineering_request_id"],
            "engineering_execution_id": source_contract["engineering_execution_id"],
            "repair_health_decision_execution_id": decision_execution["execution_id"],
            "repair_health_decision_execution_digest": decision_execution[
                "artifact_digest"
            ],
            "repair_health_decision_digest": decision["artifact_digest"],
            "presample_feasibility_digest": run.presample_feasibility[
                "artifact_digest"
            ],
            "repair_v2_design_digest": run.repair_v2_design["artifact_digest"],
            "repair_v2_design_completion_digest": run.completion["artifact_digest"],
            "old_measurement_health": "REPAIR",
            "old_decision_preserved": "REPAIR_MEASUREMENT_SYSTEM",
            "measurement_health": "REPAIR",
            "decision": "REPAIR_MEASUREMENT_SYSTEM",
            "failed_control_cell_ids": decision["failed_control_cell_ids"],
            "failed_control_cell_count": decision["failed_control_cell_count"],
            "reference_scores_per_block": 19,
            "evaluation_replicates_per_cell": 1024,
            "future_total_replicates": workload["total_replicates"],
            "future_generated_issues": workload["planned_generated_issues"],
            "familywise_false_repair_union_bound": proof["six_control_union_bound"],
            "formal_replicates_executed": 0,
            "generated_issues": 0,
            "synthetic_replicates": 0,
            "checkpoint_reads": 0,
            "compact_index_reads": 0,
            "raw_replicates_regenerated": 0,
            "sentinel_replicates_recomputed": 0,
            "duplicate_validation": False,
            "actual_fold_count": 0,
            "registered_artifact_count": len(child_payloads) + 1,
            "historical_outcomes_read": False,
            "statistical_results_read": True,
            "evidence_created": False,
            "evidence_progress_before": 0,
            "evidence_progress_after": 0,
            "accepted_model_artifact_digest": None,
            "promotion_gate_opened": False,
            "completion_fact": MARGINAL_STATIC_REPAIR_V2_DESIGN_COMPLETION_FACT,
            "downstream_consumer": MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_TASK_KEY,
            "production_impact": "none",
            "production_action": "none",
            "git_commit": git_commit,
            "working_tree_clean": True,
            "replay_status": "DETERMINISTIC_DESIGN_ONLY",
            "parent_digests": [
                *task.input_artifact_digests,
                *(str(payload["artifact_digest"]) for _, payload in child_payloads),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        if len(registrations) != execution_payload["registered_artifact_count"]:
            raise MainlineSupervisorError(
                "M4 v2 marginal-static repair-v2 design registration count changed"
            )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=(MARGINAL_STATIC_REPAIR_V2_DESIGN_COMPLETION_FACT,),
        )


class M4MarginalStaticRepairV2PreregistrationCapability:
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository,
        root_dir: Path = ROOT_DIR,
    ) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_TASK_KEY
            or task.requested_capability
            != MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "M4 v2 marginal-static repair-v2 preregistration received "
                "the wrong task"
            )
        source_contract = (
            load_marginal_static_repair_v2_preregistration_source_contract(
                self.root_dir
                / MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_SOURCE_CONTRACT_PATH
            )
        )
        verify_marginal_static_repair_v2_preregistration_source_bytes(
            root_dir=self.root_dir,
            contract=source_contract,
        )
        _, design_execution, design_registrations = _load_single_completed_execution(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=control_plane_key,
            task_key=MARGINAL_STATIC_REPAIR_V2_DESIGN_TASK_KEY,
        )
        presample_feasibility = _load_registered_type(
            root_dir=self.root_dir,
            registrations=design_registrations,
            artifact_type="m4_v2_marginal_static_repair_v2_presample_feasibility",
        )
        repair_v2_design = _load_registered_type(
            root_dir=self.root_dir,
            registrations=design_registrations,
            artifact_type="m4_v2_marginal_static_measurement_repair_v2_design",
        )
        design_completion = _load_registered_type(
            root_dir=self.root_dir,
            registrations=design_registrations,
            artifact_type="m4_v2_marginal_static_repair_v2_design_completion",
        )
        expected_inputs = (
            str(source_contract["artifact_digest"]),
            str(design_execution["artifact_digest"]),
            str(presample_feasibility["artifact_digest"]),
            str(repair_v2_design["artifact_digest"]),
            str(design_completion["artifact_digest"]),
        )
        if task.input_artifact_digests != expected_inputs:
            raise MainlineSupervisorError(
                "M4 v2 marginal-static repair-v2 preregistration identities changed"
            )
        run = build_marginal_static_repair_v2_preregistration_artifacts(
            source_contract=source_contract,
            design_execution=design_execution,
            presample_feasibility=presample_feasibility,
            repair_v2_design=repair_v2_design,
            design_completion=design_completion,
            execution_id=execution_id,
            git_commit=git_commit,
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        paths = (
            task_dir
            / "artifacts/workload-and-seeds"
            / str(run.workload_and_seeds["artifact_digest"])
            / "workload-and-seeds.json",
            task_dir
            / "artifacts/inference-and-gates"
            / str(run.inference_and_gates["artifact_digest"])
            / "inference-and-gates.json",
            task_dir
            / "artifacts/preregistration"
            / str(run.preregistration["artifact_digest"])
            / "preregistration.json",
            task_dir
            / "artifacts/completion"
            / str(run.completion["artifact_digest"])
            / "completion.json",
        )
        child_payloads = tuple(zip(paths, run.artifacts, strict=True))
        for path, payload in child_payloads:
            _persist_immutable(path, payload)
        frozen = source_contract["frozen_contract"]
        workload = frozen["workload"]
        resume = frozen["resume_and_uniqueness"]
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "marginal_static_repair_v2_preregistration_source_contract_digest": (
                source_contract["artifact_digest"]
            ),
            "marginal_static_repair_v2_preregistration_source_set_digest": (
                source_contract["source_set_digest"]
            ),
            "research_request_key": source_contract["research_request_key"],
            "research_request_id": source_contract["research_request_id"],
            "research_execution_id": source_contract["research_execution_id"],
            "engineering_request_key": source_contract["engineering_request_key"],
            "engineering_request_id": source_contract["engineering_request_id"],
            "engineering_execution_id": source_contract["engineering_execution_id"],
            "repair_v2_design_execution_id": design_execution["execution_id"],
            "repair_v2_design_execution_digest": design_execution["artifact_digest"],
            "repair_v2_presample_feasibility_digest": presample_feasibility[
                "artifact_digest"
            ],
            "repair_v2_design_digest": repair_v2_design["artifact_digest"],
            "repair_v2_design_completion_digest": design_completion["artifact_digest"],
            "repair_v2_workload_seed_digest": run.workload_and_seeds["artifact_digest"],
            "repair_v2_inference_gate_digest": run.inference_and_gates[
                "artifact_digest"
            ],
            "repair_v2_preregistration_digest": run.preregistration["artifact_digest"],
            "repair_v2_preregistration_completion_digest": run.completion[
                "artifact_digest"
            ],
            "future_reference_children": workload["reference_children"],
            "future_evaluation_children": workload["evaluation_children"],
            "future_total_children": workload["total_children"],
            "future_shard_count": workload["shard_count"],
            "future_shard_size": workload["shard_size"],
            "future_generated_issues": workload["planned_generated_issues"],
            "future_outer_evaluation_issues": workload[
                "planned_outer_evaluation_issues"
            ],
            "future_completion_index_loads": resume["completion_index_loads"],
            "completed_matching_child_action": resume["completed_matching_child"],
            "new_child_dispatch": resume["new_child_dispatch_count"],
            "formal_replicates_executed": 0,
            "generated_issues": 0,
            "synthetic_replicates": 0,
            "checkpoint_reads": 0,
            "compact_index_reads": 0,
            "raw_replicates_regenerated": 0,
            "sentinel_replicates_recomputed": 0,
            "duplicate_validation": False,
            "actual_fold_count": 0,
            "registered_artifact_count": len(child_payloads) + 1,
            "historical_outcomes_read": False,
            "statistical_results_read": False,
            "evidence_created": False,
            "evidence_progress_before": 0,
            "evidence_progress_after": 0,
            "accepted_model_artifact_digest": None,
            "promotion_gate_opened": False,
            "completion_fact": (
                MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_COMPLETION_FACT
            ),
            "downstream_consumer": MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_TASK_KEY,
            "production_impact": "none",
            "production_action": "none",
            "git_commit": git_commit,
            "working_tree_clean": True,
            "replay_status": "DETERMINISTIC_PREREGISTRATION_ONLY",
            "parent_digests": [
                *task.input_artifact_digests,
                *(str(payload["artifact_digest"]) for _, payload in child_payloads),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        if len(registrations) != execution_payload["registered_artifact_count"]:
            raise MainlineSupervisorError(
                "M4 v2 marginal-static repair-v2 preregistration registration "
                "count changed"
            )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=(
                MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_COMPLETION_FACT,
            ),
        )


class M4MarginalStaticRepairV2HealthExecutionCapability:
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository,
        root_dir: Path = ROOT_DIR,
    ) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_TASK_KEY
            or task.requested_capability
            != MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "M4 v2 marginal-static repair-v2 health execution received "
                "the wrong task"
            )
        source_contract = (
            load_marginal_static_repair_v2_health_execution_source_contract(
                self.root_dir
                / MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_SOURCE_CONTRACT_PATH
            )
        )
        verify_marginal_static_repair_v2_health_execution_source_bytes(
            root_dir=self.root_dir,
            contract=source_contract,
        )
        _, preregistration_execution, preregistration_registrations = (
            _load_single_completed_execution(
                repository=self.repository,
                root_dir=self.root_dir,
                control_plane_key=control_plane_key,
                task_key=MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_TASK_KEY,
            )
        )
        workload = _load_registered_type(
            root_dir=self.root_dir,
            registrations=preregistration_registrations,
            artifact_type=("m4_v2_marginal_static_repair_v2_health_workload_seeds"),
        )
        inference = _load_registered_type(
            root_dir=self.root_dir,
            registrations=preregistration_registrations,
            artifact_type=("m4_v2_marginal_static_repair_v2_health_inference_gates"),
        )
        preregistration = _load_registered_type(
            root_dir=self.root_dir,
            registrations=preregistration_registrations,
            artifact_type=("m4_v2_marginal_static_repair_v2_health_preregistration"),
        )
        preregistration_completion = _load_registered_type(
            root_dir=self.root_dir,
            registrations=preregistration_registrations,
            artifact_type=(
                "m4_v2_marginal_static_repair_v2_health_preregistration_completion"
            ),
        )
        expected_inputs = (
            str(source_contract["artifact_digest"]),
            str(preregistration_execution["artifact_digest"]),
            str(workload["artifact_digest"]),
            str(inference["artifact_digest"]),
            str(preregistration["artifact_digest"]),
            str(preregistration_completion["artifact_digest"]),
        )
        if task.input_artifact_digests != expected_inputs:
            raise MainlineSupervisorError(
                "M4 v2 marginal-static repair-v2 health identities changed"
            )
        run = execute_repair_v2_health_program(
            root_dir=self.root_dir,
            task_key=task.task_key,
            execution_id=execution_id,
            git_commit=git_commit,
            task_digest=task.artifact_digest,
            source_contract=source_contract,
            preregistration_execution=preregistration_execution,
            workload_artifact=workload,
            inference_artifact=inference,
            preregistration_artifact=preregistration,
            preregistration_completion=preregistration_completion,
            progress_path=self.root_dir
            / MARGINAL_STATIC_REPAIR_V2_HEALTH_PROGRESS_PATH,
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        paths = (
            task_dir
            / "artifacts/completion-index"
            / str(run.index_artifact["artifact_digest"])
            / "index.json",
            task_dir
            / "artifacts/measurement-health"
            / str(run.health_result["artifact_digest"])
            / "result.json",
            task_dir
            / "artifacts/completion"
            / str(run.completion["artifact_digest"])
            / "completion.json",
        )
        child_payloads = tuple(zip(paths, run.artifacts, strict=True))
        for path, payload in child_payloads:
            _persist_immutable(path, payload)
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "marginal_static_repair_v2_health_execution_source_contract_digest": (
                source_contract["artifact_digest"]
            ),
            "marginal_static_repair_v2_health_execution_source_set_digest": (
                source_contract["source_set_digest"]
            ),
            "research_request_key": source_contract["research_request_key"],
            "research_request_id": source_contract["research_request_id"],
            "research_execution_id": source_contract["research_execution_id"],
            "engineering_request_key": source_contract["engineering_request_key"],
            "engineering_request_id": source_contract["engineering_request_id"],
            "engineering_execution_id": source_contract["engineering_execution_id"],
            "repair_v2_preregistration_execution_id": preregistration_execution[
                "execution_id"
            ],
            "repair_v2_preregistration_execution_digest": (
                preregistration_execution["artifact_digest"]
            ),
            "repair_v2_workload_seed_digest": workload["artifact_digest"],
            "repair_v2_inference_gate_digest": inference["artifact_digest"],
            "repair_v2_preregistration_digest": preregistration["artifact_digest"],
            "repair_v2_preregistration_completion_digest": (
                preregistration_completion["artifact_digest"]
            ),
            "repair_v2_health_completion_index_digest": run.index_artifact[
                "artifact_digest"
            ],
            "repair_v2_health_result_digest": run.health_result["artifact_digest"],
            "repair_v2_health_execution_completion_digest": run.completion[
                "artifact_digest"
            ],
            "repair_v2_preliminary_measurement_health": run.health_result[
                "preliminary_measurement_health"
            ],
            "repair_v2_authoritative_decision": None,
            "failed_required_gate_cell_ids": run.health_result[
                "failed_required_gate_cell_ids"
            ],
            "failed_required_gate_cell_count": run.health_result[
                "failed_required_gate_cell_count"
            ],
            "reference_children": REPAIR_V2_REFERENCE_CHILDREN,
            "evaluation_children": REPAIR_V2_EVALUATION_CHILDREN,
            "total_children": REPAIR_V2_TOTAL_CHILDREN,
            "generated_issues": REPAIR_V2_GENERATED_ISSUES,
            "outer_evaluation_issues": REPAIR_V2_OUTER_EVALUATION_ISSUES,
            "completed_children_before_run": run.completed_before_run,
            "completed_children_during_run": run.completed_during_run,
            "completed_shards_during_run": run.completed_shards_during_run,
            "execution_runtime_seconds": run.runtime_seconds,
            "worker_count": run.worker_count,
            "process_pool_jobs": REPAIR_V2_SHARD_COUNT,
            "planned_execution_shards": REPAIR_V2_SHARD_COUNT,
            "execution_shard_size": REPAIR_V2_SHARD_SIZE,
            "checkpoint_mode": "compact_index_load_once_no_revalidation",
            "completion_index_loads": 1,
            "compact_index_reads": 1,
            "checkpoint_reads": 1,
            "completed_matching_child_action": (
                "skip_without_generation_or_revalidation"
            ),
            "new_child_dispatch": "at_most_once_per_execution",
            "slow_scalar_oracle_in_formal_child": False,
            "independent_vectorized_identity_reduction": True,
            "raw_replicates_regenerated": 0,
            "sentinel_replicates_recomputed": 0,
            "duplicate_validation": False,
            "database_reads_during_child": 0,
            "database_writes_during_child": 0,
            "csv_materialized": False,
            "historical_execution_status": "NOT_AUTHORIZED",
            "historical_outcomes_read": False,
            "statistical_results_read": True,
            "evidence_created": False,
            "evidence_progress_before": 25,
            "evidence_progress_after": 25,
            "accepted_model_artifact_digest": None,
            "promotion_gate_opened": False,
            "completion_fact": (
                MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_COMPLETION_FACT
            ),
            "actual_fold_count": 0,
            "registered_artifact_count": len(child_payloads) + 1,
            "formal_branch_runs_executed": 1,
            "downstream_consumer": MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_TASK_KEY,
            "production_impact": "none",
            "production_action": "none",
            "git_commit": git_commit,
            "working_tree_clean": True,
            "replay_status": "REGISTERED_AGGREGATE_ONLY",
            "parent_digests": [
                *task.input_artifact_digests,
                *(str(payload["artifact_digest"]) for _, payload in child_payloads),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        if len(registrations) != execution_payload["registered_artifact_count"]:
            raise MainlineSupervisorError(
                "M4 v2 marginal-static repair-v2 health registration count changed"
            )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=(
                MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_COMPLETION_FACT,
            ),
        )


class M4MarginalStaticRepairV2HealthDecisionCapability:
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository,
        root_dir: Path = ROOT_DIR,
    ) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_TASK_KEY
            or task.requested_capability
            != MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "M4 v2 marginal-static repair-v2 health decision received "
                "the wrong task"
            )
        source_contract = (
            load_marginal_static_repair_v2_health_decision_source_contract(
                self.root_dir
                / MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_SOURCE_CONTRACT_PATH
            )
        )
        verify_marginal_static_repair_v2_health_decision_source_bytes(
            root_dir=self.root_dir,
            contract=source_contract,
        )
        _, health_execution, health_registrations = _load_single_completed_execution(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=control_plane_key,
            task_key=MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_TASK_KEY,
        )
        health_result = _load_registered_type(
            root_dir=self.root_dir,
            registrations=health_registrations,
            artifact_type=("m4_v2_marginal_static_repair_v2_measurement_health_result"),
        )
        health_completion = _load_registered_type(
            root_dir=self.root_dir,
            registrations=health_registrations,
            artifact_type=(
                "m4_v2_marginal_static_repair_v2_health_execution_completion"
            ),
        )
        expected_inputs = (
            str(source_contract["artifact_digest"]),
            str(health_execution["artifact_digest"]),
            str(health_result["artifact_digest"]),
            str(health_completion["artifact_digest"]),
        )
        if task.input_artifact_digests != expected_inputs:
            raise MainlineSupervisorError(
                "M4 v2 marginal-static repair-v2 health decision identities changed"
            )
        decision = build_marginal_static_repair_v2_health_decision(
            source_contract=source_contract,
            health_execution=health_execution,
            health_result=health_result,
            health_completion=health_completion,
        )
        return _persist_small_capability(
            root_dir=self.root_dir,
            owner=self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_name="marginal-static-repair-v2-health-decision",
            child_filename="decision.json",
            child_payload=decision,
            completion_fact=str(decision["decision_fact"]),
            downstream_consumer=str(decision["next_consumer"]),
            extra_execution={
                "marginal_static_repair_v2_health_decision_source_contract_digest": (
                    source_contract["artifact_digest"]
                ),
                "marginal_static_repair_v2_health_decision_source_set_digest": (
                    source_contract["source_set_digest"]
                ),
                "repair_v2_health_execution_artifact_digest": health_execution[
                    "artifact_digest"
                ],
                "repair_v2_health_result_digest": health_result["artifact_digest"],
                "repair_v2_health_completion_digest": health_completion[
                    "artifact_digest"
                ],
                "marginal_static_repair_v2_health_decision_artifact_digest": (
                    decision["artifact_digest"]
                ),
                "authoritative_decision": decision["authoritative_decision"],
                "decision": decision["decision"],
                "decision_fact": decision["decision_fact"],
                "measurement_health": decision["measurement_health"],
                "failed_required_gate_cell_ids": [],
                "failed_required_gate_cell_count": 0,
                "required_gate_cell_ids": decision["required_gate_cell_ids"],
                "required_gate_cell_count": decision["required_gate_cell_count"],
                "admissible_local_cell_ids": decision["admissible_local_cell_ids"],
                "admissible_local_cell_count": decision["admissible_local_cell_count"],
                "sensitivity_limit_cell_ids": decision["sensitivity_limit_cell_ids"],
                "sensitivity_limit_topology": decision["sensitivity_limit_topology"],
                "sensitivity_limit_cell_count": decision[
                    "sensitivity_limit_cell_count"
                ],
                "eligible_for_historical_measurement": decision[
                    "eligible_for_historical_measurement"
                ],
                "eligible_for_historical_measurement_design": decision[
                    "eligible_for_historical_measurement_design"
                ],
                "historical_measurement_execution_authorized": False,
                "accepted_model_artifact_digest": None,
                "historical_evidence": "NOT_RUN",
                "historical_execution_status": "NOT_AUTHORIZED",
                "statistical_results_read": True,
                "generated_issues": 0,
                "compact_index_reads": 0,
                "raw_replicates_regenerated": 0,
                "sentinel_replicates_recomputed": 0,
                "duplicate_validation": False,
                "promotion_gate_opened": False,
                "repair_required": False,
                "production_action": "none",
                "replay_status": "DETERMINISTIC_DECISION_ONLY",
            },
        )


class M4MarginalStaticHistoricalDesignCapability:
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository,
        root_dir: Path = ROOT_DIR,
    ) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != MARGINAL_STATIC_HISTORICAL_DESIGN_TASK_KEY
            or task.requested_capability != MARGINAL_STATIC_HISTORICAL_DESIGN_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "M4 v2 marginal-static historical design received the wrong task"
            )
        source_contract = load_marginal_static_historical_design_source_contract(
            self.root_dir / MARGINAL_STATIC_HISTORICAL_DESIGN_SOURCE_CONTRACT_PATH
        )
        verify_marginal_static_historical_design_source_bytes(
            root_dir=self.root_dir,
            contract=source_contract,
        )
        _, health_decision_execution, health_decision_registrations = (
            _load_single_completed_execution(
                repository=self.repository,
                root_dir=self.root_dir,
                control_plane_key=control_plane_key,
                task_key=MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_TASK_KEY,
            )
        )
        health_decision = _load_registered_type(
            root_dir=self.root_dir,
            registrations=health_decision_registrations,
            artifact_type=(
                "m4_v2_marginal_static_measurement_repair_v2_health_decision"
            ),
        )
        _, marginal_execution, marginal_registrations = (
            _load_single_completed_execution(
                repository=self.repository,
                root_dir=self.root_dir,
                control_plane_key=control_plane_key,
                task_key=HISTORICAL_MARGINAL_STATIC_CONTRACT_TASK_KEY,
            )
        )
        marginal_contract = _load_registered_type(
            root_dir=self.root_dir,
            registrations=marginal_registrations,
            artifact_type="m4_v2_marginal_static_measurement_contract",
        )
        _, measurement_execution, measurement_registrations = (
            _load_single_completed_execution(
                repository=self.repository,
                root_dir=self.root_dir,
                control_plane_key=control_plane_key,
                task_key=HISTORICAL_MEASUREMENT_CONTRACT_DESIGN_TASK_KEY,
            )
        )
        gate_compiler = _load_registered_type(
            root_dir=self.root_dir,
            registrations=measurement_registrations,
            artifact_type="measurement_v2_gate_compiler_contract",
        )
        frozen_preregistration = _load_object(
            self.root_dir / MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_PATH
        )
        expected_inputs = (
            str(source_contract["artifact_digest"]),
            str(health_decision_execution["artifact_digest"]),
            str(health_decision["artifact_digest"]),
            str(marginal_execution["artifact_digest"]),
            str(marginal_contract["artifact_digest"]),
            str(measurement_execution["artifact_digest"]),
            str(gate_compiler["artifact_digest"]),
            str(frozen_preregistration["artifact_digest"]),
        )
        if task.input_artifact_digests != expected_inputs:
            raise MainlineSupervisorError(
                "M4 v2 marginal-static historical design identities changed"
            )
        run = build_marginal_static_historical_design_artifacts(
            source_contract=source_contract,
            repair_v2_health_decision_execution=health_decision_execution,
            repair_v2_health_decision=health_decision,
            marginal_static_contract_execution=marginal_execution,
            marginal_static_measurement_contract=marginal_contract,
            measurement_contract_design_execution=measurement_execution,
            gate_compiler_contract=gate_compiler,
            frozen_preregistration=frozen_preregistration,
            execution_id=execution_id,
            git_commit=git_commit,
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        child_paths = (
            task_dir
            / "artifacts/historical-dataset-boundary"
            / str(run.dataset_boundary["artifact_digest"])
            / "boundary.json",
            task_dir
            / "artifacts/historical-walk-forward-design"
            / str(run.walk_forward_design["artifact_digest"])
            / "design.json",
            task_dir
            / "artifacts/historical-inference-design"
            / str(run.inference_design["artifact_digest"])
            / "design.json",
            task_dir
            / "artifacts/completion"
            / str(run.completion["artifact_digest"])
            / "completion.json",
        )
        child_payloads = tuple(zip(child_paths, run.artifacts, strict=True))
        for path, payload in child_payloads:
            _persist_immutable(path, payload)
        frozen = source_contract["frozen_contract"]
        boundary = frozen["historical_boundary"]
        walk_forward = frozen["walk_forward"]
        inference = frozen["inference"]
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "marginal_static_historical_design_source_contract_digest": (
                source_contract["artifact_digest"]
            ),
            "marginal_static_historical_design_source_set_digest": (
                source_contract["source_set_digest"]
            ),
            "research_request_key": source_contract["research_request_key"],
            "research_request_id": source_contract["research_request_id"],
            "research_execution_id": source_contract["research_execution_id"],
            "engineering_request_key": source_contract["engineering_request_key"],
            "engineering_request_id": source_contract["engineering_request_id"],
            "engineering_execution_id": source_contract["engineering_execution_id"],
            "repair_v2_health_decision_execution_digest": (
                health_decision_execution["artifact_digest"]
            ),
            "repair_v2_health_decision_digest": health_decision["artifact_digest"],
            "marginal_static_contract_execution_digest": marginal_execution[
                "artifact_digest"
            ],
            "marginal_static_measurement_contract_digest": marginal_contract[
                "artifact_digest"
            ],
            "measurement_contract_design_execution_digest": measurement_execution[
                "artifact_digest"
            ],
            "gate_compiler_contract_digest": gate_compiler["artifact_digest"],
            "frozen_preregistration_digest": frozen_preregistration["artifact_digest"],
            "historical_dataset_boundary_digest": run.dataset_boundary[
                "artifact_digest"
            ],
            "historical_walk_forward_design_digest": run.walk_forward_design[
                "artifact_digest"
            ],
            "historical_inference_design_digest": run.inference_design[
                "artifact_digest"
            ],
            "historical_design_completion_digest": run.completion["artifact_digest"],
            "historical_issue_count": boundary["issue_count"],
            "initial_training_issue_count": frozen["estimand_and_model"][
                "minimum_training_issues"
            ],
            "planned_evaluation_fold_count": walk_forward["evaluation_fold_count"],
            "planned_bootstrap_replicates": inference["bootstrap_replicates"],
            "formal_historical_folds_executed": 0,
            "bootstrap_replicates_executed": 0,
            "database_queries_during_capability": 0,
            "historical_red_outcomes_read": False,
            "historical_outcomes_read": False,
            "statistical_results_read": False,
            "evidence_created": False,
            "evidence_progress_before": 25,
            "evidence_progress_after": 25,
            "historical_evidence": "NOT_RUN",
            "historical_execution_status": "NOT_AUTHORIZED",
            "accepted_model_artifact_digest": None,
            "promotion_gate_opened": False,
            "actual_fold_count": 0,
            "registered_artifact_count": len(child_payloads) + 1,
            "completion_fact": MARGINAL_STATIC_HISTORICAL_DESIGN_COMPLETION_FACT,
            "downstream_consumer": (
                MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_KEY
            ),
            "production_impact": "none",
            "production_action": "none",
            "git_commit": git_commit,
            "working_tree_clean": True,
            "replay_status": "DETERMINISTIC_DESIGN_ONLY",
            "parent_digests": [
                *task.input_artifact_digests,
                *(str(payload["artifact_digest"]) for _, payload in child_payloads),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        if len(registrations) != execution_payload["registered_artifact_count"]:
            raise MainlineSupervisorError(
                "M4 v2 marginal-static historical design registration count changed"
            )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=(MARGINAL_STATIC_HISTORICAL_DESIGN_COMPLETION_FACT,),
        )


class M4P261RawExecutionReplayCapability:
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository,
        root_dir: Path = ROOT_DIR,
    ) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != M4_V2_P261_RAW_REPLAY_TASK_KEY
            or task.requested_capability != M4_V2_P261_RAW_REPLAY_CAPABILITY
        ):
            raise MainlineSupervisorError("P2.6.1 raw replay received the wrong task")
        contract = load_p261_marginal_binding_contract(
            self.root_dir / P261_MARGINAL_BINDING_CONTRACT_PATH
        )
        sources = contract.payload["source_identities"]
        if task.input_artifact_digests != (
            contract.artifact_digest,
            str(sources["p2_6_1_measurement_validation_manifest_digest"]),
        ):
            raise MainlineSupervisorError("P2.6.1 raw replay inputs changed")
        event, parent, registrations = _load_single_completed_execution(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=control_plane_key,
            task_key=P26_TASK_KEY,
        )
        manifest = load_repaired_measurement_validation_manifest(
            self.root_dir
            / "configs/research-os/m4-information-theory-p2-6-1-measurement-validation-v1.json"
        )
        synthetic = load_synthetic_run_manifest(
            self.root_dir
            / "configs/research-os/m4-information-theory-p2-synthetic-run-manifest-v1.0.1.json"
        )
        replay = verify_completion_replay(
            manifest=manifest,
            synthetic=synthetic,
            parent_execution_id=str(parent["execution_id"]),
            output_dir=(
                self.root_dir
                / "runtime/research-os/mainline/tasks"
                / P26_TASK_KEY
                / str(parent["execution_id"])
                / "artifacts"
            ),
            git_commit=str(parent["git_commit"]),
            expected_completion_digest=str(parent["completion_artifact_digest"]),
        )
        if replay.get("status") != "REPLAY_VERIFIED":
            raise MainlineSupervisorError("P2.6.1 raw deterministic replay failed")
        raw = build_p261_raw_replay_artifact(
            execution=parent,
            completion_event=event,
            registrations=registrations,
            expected_task_key=str(sources["p2_6_1_task_key"]),
            expected_task_digest=str(sources["p2_6_1_task_digest"]),
            expected_execution_id=str(sources["p2_6_1_execution_id"]),
            expected_manifest_digest=str(
                sources["p2_6_1_measurement_validation_manifest_digest"]
            ),
        )
        replay_artifact = _typed_artifact(
            raw,
            artifact_type="P261RawExecutionReplayArtifact",
            parent_digests=(
                contract.artifact_digest,
                str(parent["artifact_digest"]),
                str(parent["completion_artifact_digest"]),
            ),
            domain="dehps.m4.p261-raw-execution-replay-artifact.v1",
        )
        return _persist_small_capability(
            root_dir=self.root_dir,
            owner=self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_name="raw-execution-replay",
            child_filename="replay.json",
            child_payload=replay_artifact,
            completion_fact=P261_RAW_REPLAY_FACT,
            downstream_consumer=M4_V2_P27_GATE_REPLAY_TASK_KEY,
            extra_execution={
                "p2_6_1_execution_id": parent["execution_id"],
                "p2_6_1_execution_artifact_digest": parent["artifact_digest"],
                "raw_replay_artifact_digest": replay_artifact["artifact_digest"],
                "replay_status": "REPLAY_VERIFIED",
            },
        )


class M4P27GateReplayCapability:
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository,
        root_dir: Path = ROOT_DIR,
    ) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != M4_V2_P27_GATE_REPLAY_TASK_KEY
            or task.requested_capability != M4_V2_P27_GATE_REPLAY_CAPABILITY
        ):
            raise MainlineSupervisorError("P2.7 gate replay received the wrong task")
        contract = load_p261_marginal_binding_contract(
            self.root_dir / P261_MARGINAL_BINDING_CONTRACT_PATH
        )
        if task.input_artifact_digests != (contract.artifact_digest,):
            raise MainlineSupervisorError("P2.7 gate replay inputs changed")
        _, parent, _ = _load_single_completed_execution(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=control_plane_key,
            task_key=P27_TASK_KEY,
        )
        replay = ResearchEvidenceSupervisor(
            repository=self.repository,
            control_plane_key=control_plane_key,
            root_dir=self.root_dir,
            git_commit=git_commit,
            require_clean_tree=False,
        ).replay(task_key=P27_TASK_KEY, execution_id=str(parent["execution_id"]))
        gate = build_p27_gate_replay_artifact(
            execution=parent,
            replay=replay,
            parent_p261_execution_id=str(
                contract.payload["source_identities"]["p2_6_1_execution_id"]
            ),
        )
        gate_artifact = _typed_artifact(
            gate,
            artifact_type="P27MeasurementGateReplayArtifact",
            parent_digests=(
                contract.artifact_digest,
                str(parent["artifact_digest"]),
                str(parent["automatic_gate_digest"]),
            ),
            domain="dehps.m4.p27-measurement-gate-replay-artifact.v1",
        )
        return _persist_small_capability(
            root_dir=self.root_dir,
            owner=self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_name="measurement-gate-replay",
            child_filename="replay.json",
            child_payload=gate_artifact,
            completion_fact=P27_GATE_REPLAY_FACT,
            downstream_consumer=M4_V2_MARGINAL_BINDING_TASK_KEY,
            extra_execution={
                "p2_7_execution_id": parent["execution_id"],
                "p2_7_execution_artifact_digest": parent["artifact_digest"],
                "gate_replay_artifact_digest": gate_artifact["artifact_digest"],
                "replay_status": "REPLAY_VERIFIED",
            },
        )


class M4P261MarginalBindingCapability:
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository,
        root_dir: Path = ROOT_DIR,
    ) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != M4_V2_MARGINAL_BINDING_TASK_KEY
            or task.requested_capability != M4_V2_MARGINAL_BINDING_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "P2.6.1 Marginal binding received the wrong task"
            )
        contract = load_p261_marginal_binding_contract(
            self.root_dir / P261_MARGINAL_BINDING_CONTRACT_PATH
        )
        if task.input_artifact_digests != (contract.artifact_digest,):
            raise MainlineSupervisorError("P2.6.1 Marginal binding inputs changed")
        _, raw_parent, raw_registrations = _load_single_completed_execution(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=control_plane_key,
            task_key=M4_V2_P261_RAW_REPLAY_TASK_KEY,
        )
        _, gate_parent, gate_registrations = _load_single_completed_execution(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=control_plane_key,
            task_key=M4_V2_P27_GATE_REPLAY_TASK_KEY,
        )
        raw = _load_registered_type(
            root_dir=self.root_dir,
            registrations=raw_registrations,
            artifact_type="P261RawExecutionReplayArtifact",
        )
        gate = _load_registered_type(
            root_dir=self.root_dir,
            registrations=gate_registrations,
            artifact_type="P27MeasurementGateReplayArtifact",
        )
        raw_allowed = {
            key: raw[key]
            for key in contract.payload["input_allowlist"]["p2_6_1_raw_replay"]
            if key in raw
        }
        gate_allowed = {
            key: gate[key]
            for key in contract.payload["input_allowlist"]["p2_7_gate_replay"]
            if key in gate
        }
        decision = bind_p261_marginal_acceptance(
            contract,
            raw_replay=raw_allowed,
            gate_replay=gate_allowed,
        )
        return _persist_small_capability(
            root_dir=self.root_dir,
            owner=self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_name="marginal-measurement-acceptance-decision",
            child_filename="decision.json",
            child_payload=decision,
            completion_fact=MARGINAL_BINDING_COMPLETION_FACT,
            downstream_consumer=M4_V2_MARGINAL_DECISION_REPLAY_TASK_KEY,
            extra_execution={
                "binding_contract_digest": contract.artifact_digest,
                "raw_replay_execution_artifact_digest": raw_parent["artifact_digest"],
                "gate_replay_execution_artifact_digest": gate_parent["artifact_digest"],
                "marginal_decision_artifact_digest": decision["artifact_digest"],
                "measurement_health": decision["measurement_health"],
                "historical_evidence": "NOT_RUN",
            },
        )


class M4P261MarginalDecisionReplayCapability:
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository,
        root_dir: Path = ROOT_DIR,
    ) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != M4_V2_MARGINAL_DECISION_REPLAY_TASK_KEY
            or task.requested_capability != M4_V2_MARGINAL_DECISION_REPLAY_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "Marginal decision replay received the wrong task"
            )
        contract = load_p261_marginal_binding_contract(
            self.root_dir / P261_MARGINAL_BINDING_CONTRACT_PATH
        )
        if task.input_artifact_digests != (contract.artifact_digest,):
            raise MainlineSupervisorError("Marginal decision replay inputs changed")
        _, _, binding_registrations = _load_single_completed_execution(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=control_plane_key,
            task_key=M4_V2_MARGINAL_BINDING_TASK_KEY,
        )
        decision = _load_registered_type(
            root_dir=self.root_dir,
            registrations=binding_registrations,
            artifact_type="marginal_measurement_acceptance_decision",
        )
        _, _, raw_registrations = _load_single_completed_execution(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=control_plane_key,
            task_key=M4_V2_P261_RAW_REPLAY_TASK_KEY,
        )
        _, _, gate_registrations = _load_single_completed_execution(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=control_plane_key,
            task_key=M4_V2_P27_GATE_REPLAY_TASK_KEY,
        )
        raw = _load_registered_type(
            root_dir=self.root_dir,
            registrations=raw_registrations,
            artifact_type="P261RawExecutionReplayArtifact",
        )
        gate = _load_registered_type(
            root_dir=self.root_dir,
            registrations=gate_registrations,
            artifact_type="P27MeasurementGateReplayArtifact",
        )
        reconstructed = bind_p261_marginal_acceptance(
            contract,
            raw_replay={
                key: raw[key]
                for key in contract.payload["input_allowlist"]["p2_6_1_raw_replay"]
                if key in raw
            },
            gate_replay={
                key: gate[key]
                for key in contract.payload["input_allowlist"]["p2_7_gate_replay"]
                if key in gate
            },
        )
        replay_artifact = build_branch_decision_replay_artifact(
            decision=decision,
            reconstructed_decision=reconstructed,
        )
        return _persist_small_capability(
            root_dir=self.root_dir,
            owner=self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_name="branch-decision-replay",
            child_filename="replay.json",
            child_payload=replay_artifact,
            completion_fact=MARGINAL_DECISION_REPLAY_FACT,
            downstream_consumer="m4-v2-marginal-historical-measurement",
            extra_execution={
                "binding_contract_digest": contract.artifact_digest,
                "marginal_decision_artifact_digest": decision["artifact_digest"],
                "branch_decision_replay_artifact_digest": replay_artifact[
                    "artifact_digest"
                ],
                "measurement_health": decision["measurement_health"],
                "historical_evidence": "NOT_RUN",
                "replay_status": "REPLAY_VERIFIED",
            },
        )


class M4P29GoldenReferenceCapability:
    def __init__(self, *, root_dir: Path = ROOT_DIR) -> None:
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != M4_P29_GOLDEN_REFERENCE_TASK_KEY
            or task.requested_capability != M4_P29_GOLDEN_REFERENCE_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "M4-P2.9 golden reference received the wrong task"
            )
        _, _, _, _, expected_inputs = _golden_reference_sources(root_dir=self.root_dir)
        if task.input_artifact_digests != expected_inputs:
            raise MainlineSupervisorError(
                "M4-P2.9 golden reference source identities changed"
            )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        bundle = _build_golden_reference_bundle(
            root_dir=self.root_dir,
            work_dir=task_dir / "phase0-work",
        )
        if bundle.expected_input_digests != task.input_artifact_digests:
            raise MainlineSupervisorError(
                "M4-P2.9 golden reference source replay changed"
            )
        _validate_golden_artifact_set(
            plan=bundle.plan,
            fixture=bundle.fixture,
            replay=bundle.replay,
            expected_source_inputs=expected_inputs,
            expected_construction_source_identity=(
                construction_source_integrity_identity(bundle.runtime_audit_plan)
            ),
            expected_golden_source_identity=golden_source_integrity_identity(
                bundle.runtime_audit_plan
            ),
        )
        source_integrity = build_source_integrity_attestation(
            root_dir=self.root_dir,
            runtime_plan=bundle.runtime_audit_plan,
            execution_id=execution_id,
            git_commit=git_commit,
            exact_fixture_replay_artifact_digest=str(bundle.replay["artifact_digest"]),
        )
        validate_source_integrity_attestation(
            source_integrity,
            runtime_plan=bundle.runtime_audit_plan,
            execution_id=execution_id,
            git_commit=git_commit,
            exact_fixture_replay_artifact_digest=str(bundle.replay["artifact_digest"]),
        )
        child_payloads: tuple[tuple[Path, Mapping[str, Any]], ...] = (
            (
                task_dir
                / "artifacts/golden-reference-plan"
                / str(bundle.plan["artifact_digest"])
                / "plan.json",
                bundle.plan,
            ),
            (
                task_dir
                / "artifacts/phase0-golden-fixture"
                / str(bundle.fixture["artifact_digest"])
                / "fixture.json",
                bundle.fixture,
            ),
            (
                task_dir
                / "artifacts/golden-reference-replay"
                / str(bundle.replay["artifact_digest"])
                / "replay.json",
                bundle.replay,
            ),
            (
                task_dir
                / "artifacts/source-integrity-attestation"
                / str(source_integrity["artifact_digest"])
                / "attestation.json",
                source_integrity,
            ),
        )
        for path, payload in child_payloads:
            _persist_immutable(path, payload)
        work_counts = _golden_execution_work_counts(bundle)
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "golden_reference_plan_artifact_digest": bundle.plan["artifact_digest"],
            "golden_reference_fixture_artifact_digest": bundle.fixture[
                "artifact_digest"
            ],
            "golden_reference_replay_artifact_digest": bundle.replay["artifact_digest"],
            "source_integrity_attestation_artifact_digest": source_integrity[
                "artifact_digest"
            ],
            "completion_fact": M4_P29_GOLDEN_REFERENCE_COMPLETION_FACT,
            **work_counts,
            "registered_artifact_count": 5,
            "worker_count": 1,
            "immutable_golden_fixture_is_oracle": True,
            "acceleration_boundary_independent": True,
            "acceleration_boundary_independence_scope": (
                M4_P29_ACCELERATION_BOUNDARY_SCOPE
            ),
            "oracle_construction_process_isolated": False,
            "oracle_construction_fully_implementation_independent": False,
            "exact_replay_verified": True,
            "shared_frozen_source_modified": False,
            "backend_source_modified": source_integrity["backend_source_modified"],
            "acceleration_changed_paths": source_integrity[
                "acceleration_changed_paths"
            ],
            "backend_optimization_applied": False,
            "statistical_semantics_modified": False,
            "replay_status": "EXACT_GOLDEN_REPLAY_VERIFIED",
            "engineering_progress_before": 0,
            "engineering_progress_after": 100,
            "evidence_created": False,
            "evidence_progress_before": 0,
            "evidence_progress_after": 0,
            "historical_outcomes_read": False,
            "p2_6_1_partial_statistical_results_read": False,
            "p2_6_3_statistical_results_read": False,
            "measurement_update_policy_digest": PERIODIC_REFIT_CONTRACT_DIGEST,
            "p2_6_3_task_digest": M4_P263_TASK_DIGEST,
            "formal_benchmark_after_p263_compatibility": False,
            "downstream_consumer": M4_P29_RUNTIME_AUDIT_TASK_KEY,
            "production_action": "none",
            "production_impact": "none",
            "git_commit": git_commit,
            "fixture_source_git_commit": bundle.plan["fixture_source_git_commit"],
            "fixture_parent_execution_id": bundle.plan["fixture_parent_execution_id"],
            "working_tree_clean": True,
            "parent_digests": [
                *task.input_artifact_digests,
                *(str(payload["artifact_digest"]) for _, payload in child_payloads),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        if len(registrations) != execution_payload["registered_artifact_count"]:
            raise MainlineSupervisorError(
                "M4-P2.9 golden reference artifact registration changed"
            )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=(M4_P29_GOLDEN_REFERENCE_COMPLETION_FACT,),
        )


class M4P29MeasurementRuntimeAuditCapability:
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository,
        root_dir: Path = ROOT_DIR,
    ) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != M4_P29_RUNTIME_AUDIT_TASK_KEY
            or task.requested_capability != M4_P29_RUNTIME_AUDIT_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "M4-P2.9 runtime audit received the wrong task"
            )
        plan = load_runtime_audit_plan(self.root_dir / RUNTIME_AUDIT_PLAN_PATH)
        periodic_refit_contract = load_periodic_refit_contract(
            self.root_dir
            / "configs/research-os/m4-information-theory-p2-6-3-periodic-refit-v1.json"
        )
        if task.input_artifact_digests != (str(plan["artifact_digest"]),):
            raise MainlineSupervisorError("M4-P2.9 runtime audit plan changed")
        (
            golden_execution,
            _,
            golden_plan,
            golden_fixture,
            golden_replay,
            golden_source_integrity,
        ) = _load_verified_golden_parent(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=control_plane_key,
        )
        (
            source_runtime_plan,
            manifest,
            synthetic,
            truths,
            _expected_inputs,
        ) = _golden_reference_sources(root_dir=self.root_dir)
        if source_runtime_plan != plan:
            raise MainlineSupervisorError("M4-P2.9 runtime audit source plan changed")
        verified_construction_source_identity = preflight_source_integrity(
            root_dir=self.root_dir,
            runtime_plan=plan,
        )
        if (
            construction_source_integrity_identity(plan)
            != verified_construction_source_identity
        ):
            raise MainlineSupervisorError(
                "M4-P2.9 runtime source integrity preflight changed"
            )
        try:
            compatible_golden_source_identity = require_golden_source_compatibility(
                registered_golden_contract=golden_plan[
                    "golden_source_integrity_contract"
                ],
                registered_golden_identity=golden_plan[
                    "golden_source_integrity_identity"
                ],
                new_full_source_contract=plan["source_integrity_contract"],
            )
        except RuntimeError as exc:
            raise MainlineSupervisorError(
                f"M4-P2.9 runtime golden source compatibility changed: {exc}"
            ) from exc
        replicate = golden_full_replicate(
            manifest=manifest,
            synthetic=synthetic,
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        recovered = _recover_runtime_audit_commit_marker(
            root_dir=self.root_dir,
            owner=self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            task_dir=task_dir,
            runtime_plan=plan,
            golden_execution=golden_execution,
            golden_plan=golden_plan,
            golden_fixture=golden_fixture,
            golden_replay=golden_replay,
            golden_source_integrity=golden_source_integrity,
            compatible_golden_source_identity=(compatible_golden_source_identity),
        )
        if recovered is not None:
            return recovered
        benchmark_plan = build_benchmark_plan_artifact(plan)
        (
            benchmark_attempt_id,
            measured_workdir,
            correctness_workdir,
        ) = _prepare_fresh_runtime_audit_attempt(
            task_dir=task_dir,
            execution_id=execution_id,
        )
        pre_observation_fingerprint = build_canonical_executor_fingerprint()
        if pre_observation_fingerprint != golden_plan["executor_fingerprint"]:
            raise MainlineSupervisorError(
                "M4-P2.9 runtime executor fingerprint changed before observation"
            )
        observer = RuntimeAuditObserver(enabled=True)
        measured_evaluation = _observed_reference_evaluation(
            root_dir=self.root_dir,
            output_dir=measured_workdir,
            manifest=manifest,
            synthetic=synthetic,
            truths=truths,
            replicate=replicate,
            periodic_refit_contract=periodic_refit_contract,
            observer=observer,
            capture_trace=False,
        )
        post_observation_fingerprint = build_canonical_executor_fingerprint()
        if post_observation_fingerprint != pre_observation_fingerprint:
            raise MainlineSupervisorError(
                "M4-P2.9 runtime executor fingerprint changed during observation"
            )
        measured_result_float64_tree_digest = float64_tree_digest(
            measured_evaluation.result_payload,
            domain="dehps.m4.p2-9.measured-result-float64-tree.v1",
        )
        measured_checkpoint_journal_sha256 = sha256(
            measured_evaluation.checkpoint_journal_bytes
        ).hexdigest()
        observation = observer.observation(
            plan_digest=str(benchmark_plan["artifact_digest"]),
            execution_id=execution_id,
            git_commit=git_commit,
            executor_fingerprint_digest_before=str(
                pre_observation_fingerprint["artifact_digest"]
            ),
            executor_fingerprint_digest_after=str(
                post_observation_fingerprint["artifact_digest"]
            ),
            benchmark_attempt_id=benchmark_attempt_id,
            measured_result_float64_tree_digest=(measured_result_float64_tree_digest),
            measured_checkpoint_journal_sha256=(measured_checkpoint_journal_sha256),
        )
        _validate_runtime_observation(
            observation,
            benchmark_plan=benchmark_plan,
            execution_id=execution_id,
            git_commit=git_commit,
            executor_fingerprint_digest=str(golden_plan["executor_fingerprint_digest"]),
            benchmark_attempt_id=benchmark_attempt_id,
            measured_result_float64_tree_digest=(measured_result_float64_tree_digest),
            measured_checkpoint_journal_sha256=(measured_checkpoint_journal_sha256),
        )
        benchmark_attempt_path = str(measured_workdir.parent.relative_to(self.root_dir))
        measured_workdir_relative = str(measured_workdir.relative_to(self.root_dir))
        correctness_workdir_relative = str(
            correctness_workdir.relative_to(self.root_dir)
        )
        benchmark_attempt = build_runtime_benchmark_attempt_artifact(
            benchmark_plan_digest=str(benchmark_plan["artifact_digest"]),
            observation=observation,
            execution_id=execution_id,
            git_commit=git_commit,
            benchmark_attempt_id=benchmark_attempt_id,
            benchmark_attempt_path=benchmark_attempt_path,
            measured_workdir_path=measured_workdir_relative,
            correctness_replay_workdir_path=correctness_workdir_relative,
            measured_result_payload=measured_evaluation.result_payload,
            measured_checkpoint_journal_bytes=(
                measured_evaluation.checkpoint_journal_bytes
            ),
        )
        validate_runtime_benchmark_attempt_artifact(
            benchmark_attempt,
            benchmark_plan_digest=str(benchmark_plan["artifact_digest"]),
            observation=observation,
            execution_id=execution_id,
            git_commit=git_commit,
        )
        correctness_evaluation = _observed_reference_evaluation(
            root_dir=self.root_dir,
            output_dir=correctness_workdir,
            manifest=manifest,
            synthetic=synthetic,
            truths=truths,
            replicate=replicate,
            periodic_refit_contract=periodic_refit_contract,
            capture_trace=True,
        )
        _require_exact_runtime_correctness_replay(
            measured=measured_evaluation,
            correctness=correctness_evaluation,
        )
        audited_payload = dict(measured_evaluation.result_payload)
        observed_boundaries = _build_observed_boundary_snapshots(
            manifest=manifest,
            synthetic=synthetic,
            truths=truths,
        )
        observed_fixture = build_golden_fixture_artifact(
            plan_digest=str(golden_plan["artifact_digest"]),
            replicate=replicate,
            evaluation=correctness_evaluation,
            boundary_snapshots=observed_boundaries,
            parent_digests=tuple(
                str(value) for value in golden_fixture["parent_digests"]
            ),
            executor_fingerprint_digest=str(golden_plan["executor_fingerprint_digest"]),
            golden_source_integrity_identity=(compatible_golden_source_identity),
        )
        reconstructed_golden_replay = build_exact_golden_attestation(
            plan_digest=str(golden_plan["artifact_digest"]),
            reference_payload=golden_fixture,
            observed_payload=observed_fixture,
            reference_journal_bytes=str(
                golden_fixture["checkpoint_journal_utf8"]
            ).encode("utf-8"),
            observed_journal_bytes=correctness_evaluation.checkpoint_journal_bytes,
        )
        if reconstructed_golden_replay != golden_replay:
            raise MainlineSupervisorError(
                "M4-P2.9 frozen golden replay identity changed"
            )
        source_integrity = build_source_integrity_attestation(
            root_dir=self.root_dir,
            runtime_plan=plan,
            execution_id=execution_id,
            git_commit=git_commit,
            exact_fixture_replay_artifact_digest=str(golden_replay["artifact_digest"]),
            golden_reference_execution_artifact_digest=str(
                golden_execution["artifact_digest"]
            ),
            golden_source_identity=compatible_golden_source_identity,
        )
        validate_source_integrity_attestation(
            source_integrity,
            runtime_plan=plan,
            execution_id=execution_id,
            git_commit=git_commit,
            exact_fixture_replay_artifact_digest=str(golden_replay["artifact_digest"]),
            golden_reference_execution_artifact_digest=str(
                golden_execution["artifact_digest"]
            ),
            golden_source_identity=compatible_golden_source_identity,
        )
        equivalence = _build_runtime_golden_equivalence(
            benchmark_plan=benchmark_plan,
            golden_execution=golden_execution,
            golden_plan=golden_plan,
            golden_fixture=golden_fixture,
            golden_replay=golden_replay,
            observed_fixture=observed_fixture,
            audited_payload=audited_payload,
            benchmark_attempt=benchmark_attempt,
            source_integrity=source_integrity,
            golden_source_integrity=golden_source_integrity,
        )
        final_executor_fingerprint = build_canonical_executor_fingerprint()
        if final_executor_fingerprint != pre_observation_fingerprint:
            raise MainlineSupervisorError(
                "M4-P2.9 runtime executor fingerprint changed before attestation"
            )
        child_payloads: tuple[tuple[Path, Mapping[str, Any]], ...] = (
            (
                task_dir
                / "artifacts/benchmark-plan"
                / str(benchmark_plan["artifact_digest"])
                / "plan.json",
                benchmark_plan,
            ),
            (
                task_dir
                / "artifacts/runtime-observation"
                / str(observation["artifact_digest"])
                / "observation.json",
                observation,
            ),
            (
                task_dir
                / "artifacts/runtime-benchmark-attempt"
                / str(benchmark_attempt["artifact_digest"])
                / "attempt.json",
                benchmark_attempt,
            ),
            (
                task_dir
                / "artifacts/equivalence-attestation"
                / str(equivalence["artifact_digest"])
                / "attestation.json",
                equivalence,
            ),
            (
                task_dir
                / "artifacts/source-integrity-attestation"
                / str(source_integrity["artifact_digest"])
                / "attestation.json",
                source_integrity,
            ),
        )
        for path, payload in child_payloads:
            _persist_immutable(path, payload)
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "benchmark_plan_artifact_digest": benchmark_plan["artifact_digest"],
            "runtime_observation_artifact_digest": observation["artifact_digest"],
            "runtime_benchmark_attempt_artifact_digest": benchmark_attempt[
                "artifact_digest"
            ],
            "source_integrity_attestation_artifact_digest": source_integrity[
                "artifact_digest"
            ],
            "golden_source_integrity_attestation_artifact_digest": (
                golden_source_integrity["artifact_digest"]
            ),
            "runtime_executor_fingerprint_digest_before": observation[
                "executor_fingerprint_digest_before"
            ],
            "runtime_executor_fingerprint_digest_after": observation[
                "executor_fingerprint_digest_after"
            ],
            "equivalence_attestation_artifact_digest": equivalence["artifact_digest"],
            "completion_fact": M4_P29_RUNTIME_AUDIT_COMPLETION_FACT,
            "actual_fold_count": replicate.cell.outer_issue_count,
            "audited_fold_count": replicate.cell.outer_issue_count,
            "correctness_replay_fold_count": replicate.cell.outer_issue_count,
            "total_execution_fold_count": 2 * replicate.cell.outer_issue_count,
            "correctness_boundary_snapshot_count": len(observed_boundaries),
            "frozen_reference_fold_count": int(
                golden_fixture["replicate_result"]["actual_outer_fold_count"]
            ),
            "registered_artifact_count": 6,
            "benchmark_attempt_id": benchmark_attempt_id,
            "benchmark_attempt_path": benchmark_attempt_path,
            "measured_workdir_path": measured_workdir_relative,
            "correctness_replay_workdir_path": correctness_workdir_relative,
            "journal_reused": False,
            "fresh_workdir": True,
            "worker_count": 1,
            "formal_benchmark_after_p263_compatibility": True,
            "reference_evaluator_is_oracle": False,
            "immutable_golden_fixture_is_oracle": True,
            "acceleration_boundary_independent": True,
            "acceleration_boundary_independence_scope": (
                M4_P29_ACCELERATION_BOUNDARY_SCOPE
            ),
            "oracle_construction_process_isolated": False,
            "oracle_construction_fully_implementation_independent": False,
            "golden_reference_execution_artifact_digest": golden_execution[
                "artifact_digest"
            ],
            "golden_reference_plan_artifact_digest": golden_plan["artifact_digest"],
            "golden_reference_fixture_artifact_digest": golden_fixture[
                "artifact_digest"
            ],
            "golden_reference_replay_artifact_digest": golden_replay["artifact_digest"],
            "exact_golden_replay_verified": True,
            "shared_frozen_source_modified": False,
            "backend_source_modified": source_integrity["backend_source_modified"],
            "acceleration_changed_paths": source_integrity[
                "acceleration_changed_paths"
            ],
            "backend_optimization_applied": False,
            "statistical_semantics_modified": False,
            "historical_outcomes_read": False,
            "p2_6_1_partial_statistical_results_read": False,
            "p2_6_3_statistical_results_read": False,
            "measurement_update_policy_digest": PERIODIC_REFIT_CONTRACT_DIGEST,
            "p2_6_3_task_digest": M4_P263_TASK_DIGEST,
            "evidence_created": False,
            "evidence_progress_before": 0,
            "evidence_progress_after": 0,
            "downstream_consumer": "future independent optimization request",
            "production_action": "none",
            "production_impact": "none",
            "git_commit": git_commit,
            "working_tree_clean": True,
            "parent_digests": [
                *task.input_artifact_digests,
                golden_execution["artifact_digest"],
                golden_plan["artifact_digest"],
                golden_fixture["artifact_digest"],
                golden_replay["artifact_digest"],
                golden_source_integrity["artifact_digest"],
                *(str(payload["artifact_digest"]) for _, payload in child_payloads),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=(M4_P29_RUNTIME_AUDIT_COMPLETION_FACT,),
        )


class M4P263RuntimeSlotEligibilityCapability:
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository,
        root_dir: Path = ROOT_DIR,
    ) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            control_plane_key != M4_CONTROL_PLANE_KEY
            or task.task_key != P263_SLOT_ELIGIBILITY_TASK_KEY
            or task.requested_capability != P263_SLOT_ELIGIBILITY_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "M4 P2.6.3 slot eligibility received the wrong task"
            )
        expected_inputs = (
            COMPATIBILITY_REQUEST_DIGEST,
            P261_FROZEN_FIXTURE_DIGEST,
            P263_SUPERSEDING_FIXTURE_DIGEST,
            "8c97fd5fdc006cba6a4145dbd56acc566b9507e18279d06437d0aa472adb2cd2",
        )
        if (
            len(task.input_artifact_digests) != 5
            or task.input_artifact_digests[:4] != expected_inputs
        ):
            raise MainlineSupervisorError(
                "M4 P2.6.3 slot eligibility source identities changed"
            )
        source_contract = load_p263_slot_source_contract(
            self.root_dir / P263_SLOT_SOURCE_CONTRACT_PATH
        )
        if source_contract["artifact_digest"] != task.input_artifact_digests[4]:
            raise MainlineSupervisorError(
                "M4 P2.6.3 slot eligibility source contract changed"
            )
        verify_p263_slot_source_bytes(
            root_dir=self.root_dir,
            contract=source_contract,
        )
        p261 = load_measurement_compatibility_fixture(
            self.root_dir / P261_FROZEN_FIXTURE_PATH,
            expected_phase="M4-P2.6.1",
        )
        p263 = load_measurement_compatibility_fixture(
            self.root_dir / P263_SUPERSEDING_FIXTURE_PATH,
            expected_phase="M4-P2.6.3",
        )
        manifest = self.repository.load_manifest(control_plane_key=control_plane_key)
        event_task_keys = (
            M4_P263_COMPATIBILITY_TASK_KEY,
            M4_P29_GOLDEN_REFERENCE_TASK_KEY,
            M4_P29_P263_FAILED_RUNTIME_AUDIT_TASK_KEY,
            M4_P29_RUNTIME_AUDIT_TASK_KEY,
            P263_SLOT_ELIGIBILITY_TASK_KEY,
            M4_V2_DESIGN_TASK_KEY,
            M4_V2_DESIGN_REPLAY_TASK_KEY,
            "m4-v2-branch-identifiability-preflight-design",
            "m4-p3-strict-historical-walk-forward",
        )
        events = self.repository.list_mainline_execution_event_metadata(
            control_plane_key=control_plane_key,
            task_keys=event_task_keys,
        )
        registrations_by_execution: dict[str, Sequence[Mapping[str, Any]]] = {}
        for task_key in (
            M4_P263_COMPATIBILITY_TASK_KEY,
            M4_P29_GOLDEN_REFERENCE_TASK_KEY,
            M4_P29_RUNTIME_AUDIT_TASK_KEY,
        ):
            completed_task = next(
                item for item in manifest.tasks if item.task_key == task_key
            )
            completed_ids = completion_execution_ids(
                manifest,
                task=completed_task,
            )
            if len(completed_ids) != 1:
                raise MainlineSupervisorError(
                    f"M4 P2.6.3 slot prerequisite is not uniquely complete: {task_key}"
                )
            completed_id = completed_ids[0]
            registrations_by_execution[completed_id] = (
                self.repository.list_mainline_artifacts(
                    control_plane_key=control_plane_key,
                    execution_id=completed_id,
                )
            )
        eligibility = build_p263_slot_eligibility_artifact(
            manifest=manifest,
            events=events,
            registrations_by_execution=registrations_by_execution,
            execution_id=execution_id,
            git_commit=git_commit,
            p261_fixture_digest=p261.artifact_digest,
            p263_fixture_digest=p263.artifact_digest,
            slot_source_contract_digest=source_contract["artifact_digest"],
            slot_source_set_digest=source_contract["source_set_digest"],
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        eligibility_path = (
            task_dir
            / "artifacts/runtime-slot-eligibility"
            / str(eligibility["artifact_digest"])
            / "eligibility.json"
        )
        _persist_immutable(eligibility_path, eligibility)
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "slot_eligibility_artifact_digest": eligibility["artifact_digest"],
            "eligibility_basis_digest": eligibility["eligibility_basis_digest"],
            "slot_governance_source_contract_digest": source_contract[
                "artifact_digest"
            ],
            "slot_governance_source_set_digest": source_contract["source_set_digest"],
            "completion_fact": P263_SLOT_ELIGIBILITY_FACT,
            "actual_fold_count": 0,
            "registered_artifact_count": 2,
            "statistical_results_read": False,
            "historical_outcomes_read": False,
            "result_blind": True,
            "evidence_created": False,
            "evidence_progress_before": 25,
            "evidence_progress_after": 25,
            "prediction_v2_promotion_allowed": False,
            "promotion_gate_opened": False,
            "stop_service_required": True,
            "post_stop_guard_required": True,
            "downstream_consumer": "operator-p263-runtime-slot-release",
            "production_action": "none",
            "production_impact": "none",
            "git_commit": git_commit,
            "working_tree_clean": True,
            "replay_status": "REPLAYABLE_FROM_RESULT_BLIND_METADATA",
            "parent_digests": [
                *task.input_artifact_digests,
                eligibility["artifact_digest"],
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=((eligibility_path, eligibility),),
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=(P263_SLOT_ELIGIBILITY_FACT,),
        )


class P26MeasurementValidationCapability:
    def __init__(self, *, root_dir: Path = ROOT_DIR) -> None:
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if task.task_key != P26_TASK_KEY or task.requested_capability != P26_CAPABILITY:
            raise MainlineSupervisorError("P2.6 capability received the wrong task")
        contract_path = (
            self.root_dir / "configs/research-os/"
            "m4-information-theory-p2-6-1-measurement-validation-v1.json"
        )
        manifest = load_repaired_measurement_validation_manifest(contract_path)
        update_policy = load_periodic_refit_contract(
            self.root_dir / "configs/research-os/"
            "m4-information-theory-p2-6-3-periodic-refit-v1.json"
        )
        truth_digests = tuple(
            str(item["artifact_digest"]) for item in manifest.payload["truth_artifacts"]
        )
        expected_inputs = (
            MEASUREMENT_REPAIR_MANIFEST_DIGEST,
            REPAIRED_MEASUREMENT_VALIDATION_MANIFEST_DIGEST,
            PERIODIC_REFIT_CONTRACT_DIGEST,
            "90459ebf8b88afcc60ee1177043e436b90b71c00b557f15e9e4d7026f37586f2",
            "1a76f46d7a47a134c1688657749bc040290f65a03dbc7c860e38144e02005981",
            KERNEL_MANIFEST_DIGEST,
            P25_METRIC_KERNEL_DIGEST,
            P25_WALK_FORWARD_HARNESS_DIGEST,
            *truth_digests,
        )
        if task.input_artifact_digests != expected_inputs:
            raise MainlineSupervisorError(
                "P2.6.3 requires the repaired contract, fixed periodic-refit "
                "policy, frozen probes, resampling kernel, and all marginal truths"
            )
        synthetic = load_synthetic_run_manifest(
            self.root_dir / "configs/research-os/"
            "m4-information-theory-p2-synthetic-run-manifest-v1.0.1.json"
        )
        resampling_path = (
            self.root_dir / "configs/research-os/"
            "m4-information-theory-p2-5-resampling-kernel-v1.json"
        )
        truths = locate_repaired_truth_artifacts(
            self.root_dir,
            required_digests=truth_digests,
            repair_manifest_digest=MEASUREMENT_REPAIR_MANIFEST_DIGEST,
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        output_dir = task_dir / "artifacts"
        runtime_migration_paths = tuple(
            sorted((task_dir / "runtime-migrations").glob("*/migration.json"))
        )
        incident_recovery_paths = tuple(
            sorted((task_dir / "incident-recoveries").glob("*/recovery.json"))
        )
        evaluator = ReferenceReplicateEvaluator.from_paths(
            manifest=manifest,
            synthetic=synthetic,
            preregistration_path=(
                self.root_dir / "configs/research-os/"
                "m4-information-theory-preregistration-v1.0.3.json"
            ),
            walk_forward_harness_path=(
                self.root_dir / "configs/research-os/"
                "m4-information-theory-walk-forward-harness-v1.json"
            ),
            resampling_path=resampling_path,
            truth_by_scenario=truths,
            git_commit=git_commit,
            output_dir=output_dir,
            periodic_refit_contract=update_policy,
        )
        configured_workers = int(
            os.environ.get(
                "DEHPS_P26_WORKERS",
                str(max(1, min(20, (os.cpu_count() or 2) - 2))),
            )
        )
        executor_shard_count_raw = os.environ.get("DEHPS_P26_EXECUTOR_SHARD_COUNT")
        executor_shard_index_raw = os.environ.get("DEHPS_P26_EXECUTOR_SHARD_INDEX")
        if (executor_shard_count_raw is None) != (executor_shard_index_raw is None):
            raise MainlineSupervisorError(
                "P2.6 executor shard count and index must be configured together"
            )
        executor_shard_count = (
            None if executor_shard_count_raw is None else int(executor_shard_count_raw)
        )
        executor_shard_index = (
            None if executor_shard_index_raw is None else int(executor_shard_index_raw)
        )
        coordinator = run_parallel_execution(
            manifest=manifest,
            synthetic=synthetic,
            parent_execution_id=execution_id,
            output_dir=output_dir,
            evaluator=evaluator,
            worker_count=configured_workers,
            progress_projection_path=(
                self.root_dir / "runtime/logs/"
                "m4-p2-6-3-measurement-validation-progress.json"
            ),
            executor_shard_index=executor_shard_index,
            executor_shard_count=executor_shard_count,
            expected_update_policy_digest=update_policy.artifact_digest,
        )
        completion = assemble_completion(
            manifest=manifest,
            synthetic=synthetic,
            parent_execution_id=execution_id,
            output_dir=output_dir,
            git_commit=git_commit,
            expected_update_policy_digest=update_policy.artifact_digest,
        )
        schedule = manifest.payload["workload"]["schedule"]
        boundary_count = sum(
            int(item["scenario_count"])
            * int(item["replicates_per_scenario"])
            * (
                int(item["outer_issue_count"])
                + update_policy.learned_probe_refit_interval_folds
                - 1
            )
            // update_policy.learned_probe_refit_interval_folds
            for item in schedule
        )
        child_paths = (
            coordinator.execution_plan_path,
            *completion.replicate_paths,
            *completion.aggregate_paths,
            completion.mde_summary_path,
            completion.completion_artifact_path,
            *runtime_migration_paths,
            *incident_recovery_paths,
        )
        child_payloads = tuple((path, _load_object(path)) for path in child_paths)
        child_identities = {
            (
                _artifact_digest(payload),
                str(payload.get("artifact_type") or "typed_artifact"),
            )
            for _, payload in child_payloads
        }
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "measurement_validation_manifest_digest": manifest.artifact_digest,
            "measurement_update_policy_digest": update_policy.artifact_digest,
            "execution_plan_digest": coordinator.execution_plan["artifact_digest"],
            "completion_artifact_digest": completion.completion_artifact[
                "artifact_digest"
            ],
            "completion_artifact_path": str(
                completion.completion_artifact_path.relative_to(self.root_dir)
            ),
            "aggregate_digests": [
                item["artifact_digest"] for item in completion.aggregate_artifacts
            ],
            "mde_summary_digest": completion.mde_summary_artifact["artifact_digest"],
            "decision_policy_mde_at_61_bits_per_issue": (
                completion.mde_summary_artifact[
                    "decision_policy_mde_at_61_bits_per_issue"
                ]
            ),
            "replicate_count": len(completion.replicate_paths),
            "aggregate_count": len(completion.aggregate_artifacts),
            "actual_fold_count": manifest.outer_issue_predictions,
            "all_probe_outer_fold_count": manifest.outer_issue_predictions * 4,
            "estimator_and_calibrator_fit_count": boundary_count * 3,
            "learned_probe_fit_count": boundary_count * 3,
            "learned_probe_refit_boundary_count": boundary_count,
            "learned_probe_refit_interval_folds": (
                update_policy.learned_probe_refit_interval_folds
            ),
            "empirical_baseline_update_count": manifest.outer_issue_predictions,
            "probe_preparation_count": (
                manifest.outer_issue_predictions + boundary_count * 3
            ),
            "inner_model_selection_fit_count": 0,
            "superseded_every_fold_fit_count": (manifest.outer_issue_predictions * 4),
            "number_probability_predictions": (
                manifest.outer_issue_predictions * 33 * 4
            ),
            "bootstrap_replicate_count": (
                manifest.scenario_replicates * manifest.bootstrap_replicates
            ),
            "permutation_replicate_count": (
                manifest.scenario_replicates * manifest.permutation_replicates
            ),
            "negative_control_id": "NC6_SYNTHETIC_NULL",
            "negative_control_cell_count": 3,
            "negative_control_replicates_per_cell": (
                manifest.negative_control_replicates
            ),
            "negative_control_replicate_count": 3000,
            "runtime_migration_digests": [
                _artifact_digest(_load_object(path)) for path in runtime_migration_paths
            ],
            "runtime_git_commits": [
                str(_load_object(path)["runtime_git_commit"])
                for path in runtime_migration_paths
            ],
            "incident_recovery_digests": [
                _artifact_digest(_load_object(path)) for path in incident_recovery_paths
            ],
            "registered_artifact_count": len(child_identities) + 1,
            "engineering_progress_before": 37,
            "engineering_progress_after": 39,
            "evidence_progress_before": 0,
            "evidence_progress_after": 25,
            "downstream_consumer": P27_TASK_KEY,
            "eligible_for_formal_inference": True,
            "formal_power_executed": True,
            "formal_false_positive_executed": True,
            "mde_computed": True,
            "pe2_finalized": True,
            "real_history_used": False,
            "production_checkpoint_created": False,
            "git_commit": git_commit,
            "working_tree_clean": True,
            "evidence_created": True,
            "production_impact": "none",
            "parent_digests": [
                *task.input_artifact_digests,
                coordinator.execution_plan["artifact_digest"],
                completion.completion_artifact["artifact_digest"],
                completion.mde_summary_artifact["artifact_digest"],
                *(
                    _artifact_digest(_load_object(path))
                    for path in runtime_migration_paths
                ),
                *(
                    _artifact_digest(_load_object(path))
                    for path in incident_recovery_paths
                ),
                *(item["artifact_digest"] for item in completion.aggregate_artifacts),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        if len(registrations) != execution_payload["registered_artifact_count"]:
            raise MainlineSupervisorError("P2.6 registered artifact count changed")
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
        )


class P27AutomaticMeasurementGateCapability:
    def __init__(self, *, root_dir: Path = ROOT_DIR) -> None:
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if task.task_key != P27_TASK_KEY or task.requested_capability != P27_CAPABILITY:
            raise MainlineSupervisorError("P2.7 capability received the wrong task")
        manifest = load_repaired_measurement_validation_manifest(
            self.root_dir / "configs/research-os/"
            "m4-information-theory-p2-6-1-measurement-validation-v1.json"
        )
        update_policy = load_periodic_refit_contract(
            self.root_dir / "configs/research-os/"
            "m4-information-theory-p2-6-3-periodic-refit-v1.json"
        )
        if task.input_artifact_digests != (
            P25_DECISION_POLICY_DIGEST,
            REPAIRED_MEASUREMENT_VALIDATION_MANIFEST_DIGEST,
            PERIODIC_REFIT_CONTRACT_DIGEST,
        ):
            raise MainlineSupervisorError("P2.7 frozen inputs changed")
        synthetic = load_synthetic_run_manifest(
            self.root_dir / "configs/research-os/"
            "m4-information-theory-p2-synthetic-run-manifest-v1.0.1.json"
        )
        p26_root = self.root_dir / "runtime/research-os/mainline/tasks" / P26_TASK_KEY
        candidates = sorted(p26_root.glob("*/execution.json"))
        completed = [
            (path, _load_object(path))
            for path in candidates
            if _load_object(path).get("status") == "COMPLETE"
        ]
        if len(completed) != 1:
            raise MainlineSupervisorError(
                "P2.7 requires exactly one completed P2.6 execution artifact"
            )
        p26_execution_path, p26_execution = completed[0]
        if (
            p26_execution.get("measurement_update_policy_digest")
            != update_policy.artifact_digest
        ):
            raise MainlineSupervisorError(
                "P2.7 requires the frozen P2.6.3 update policy"
            )
        p26_execution_id = str(p26_execution["execution_id"])
        p26_output = p26_execution_path.parent / "artifacts"
        replay = verify_completion_replay(
            manifest=manifest,
            synthetic=synthetic,
            parent_execution_id=p26_execution_id,
            output_dir=p26_output,
            git_commit=str(p26_execution["git_commit"]),
            expected_completion_digest=str(p26_execution["completion_artifact_digest"]),
            expected_update_policy_digest=update_policy.artifact_digest,
        )
        completion_path = self.root_dir / str(p26_execution["completion_artifact_path"])
        completion = _load_object(completion_path)
        aggregate_paths = sorted(p26_output.glob("aggregates/*/*.json"))
        aggregates = [_load_object(path) for path in aggregate_paths]
        gate = evaluate_automatic_gate(
            manifest=manifest,
            completion=completion,
            aggregates=aggregates,
            deterministic_replay_passed=replay["status"] == "REPLAY_VERIFIED",
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        mde = dict(gate["mde_summary"])
        mde_path = task_dir / "artifacts/mde" / mde["artifact_digest"] / "mde.json"
        gate_path = (
            task_dir / "artifacts/gate" / str(gate["artifact_digest"]) / "gate.json"
        )
        _persist_immutable(mde_path, mde)
        _persist_immutable(gate_path, gate)
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "measurement_validation_manifest_digest": manifest.artifact_digest,
            "measurement_update_policy_digest": update_policy.artifact_digest,
            "p26_execution_artifact_digest": p26_execution["artifact_digest"],
            "execution_plan_digest": p26_execution["execution_plan_digest"],
            "completion_artifact_digest": completion["artifact_digest"],
            "aggregate_digests": p26_execution["aggregate_digests"],
            "automatic_gate_digest": gate["artifact_digest"],
            "mde_summary_digest": mde["artifact_digest"],
            "decision": gate["decision"],
            "decision_fact": gate["decision_fact"],
            "decision_policy_mde_at_61_bits_per_issue": mde[
                "decision_policy_mde_at_61_bits_per_issue"
            ],
            "false_positive_by_scale": [
                {
                    "scale_id": item["scale_id"],
                    "false_positive_rate": item["false_positive_rate"],
                    "wilson_95_upper": item["wilson_95_interval"]["upper"],
                    "point_gate_pass": item["false_positive_point_gate_pass"],
                    "wilson_gate_pass": item["false_positive_wilson_gate_pass"],
                }
                for item in aggregates
                if item["scenario_id"] == "NULL_UNIFORM"
            ],
            "power_by_cell": [
                {
                    "scale_id": item["scale_id"],
                    "scenario_id": item["scenario_id"],
                    "signal_strength": item["signal_strength"],
                    "truth_bits_per_issue": item["truth_bits_per_issue"],
                    "empirical_power": item["empirical_power"],
                }
                for item in aggregates
                if item["scenario_id"] != "NULL_UNIFORM"
            ],
            "estimator_quality_by_cell": [
                {
                    "scale_id": item["scale_id"],
                    "scenario_id": item["scenario_id"],
                    "bias_bits_per_issue": item["bias_bits_per_issue"],
                    "rmse_bits_per_issue": item["rmse_bits_per_issue"],
                    "PE2_coverage_rate": item["PE2_coverage_rate"],
                    "bias_gate_pass": item["bias_gate_pass"],
                    "coverage_gate_pass": item["coverage_gate_pass"],
                    "rmse_finite_gate_pass": item["rmse_finite_gate_pass"],
                }
                for item in aggregates
                if item["scenario_id"] != "NULL_UNIFORM"
            ],
            "completion_facts": [gate["decision_fact"]],
            "additional_completed_task_keys": (
                [P2_UMBRELLA_TASK_KEY] if gate["decision"] == "PASS_TO_P3" else []
            ),
            "failed_requirements": gate["failed_requirements"],
            "replay_status": replay["status"],
            "replicate_count": completion["replicate_count"],
            "aggregate_count": completion["cell_aggregate_count"],
            "bootstrap_replicate_count": p26_execution["bootstrap_replicate_count"],
            "permutation_replicate_count": p26_execution["permutation_replicate_count"],
            "negative_control_id": p26_execution["negative_control_id"],
            "negative_control_cell_count": p26_execution["negative_control_cell_count"],
            "negative_control_replicates_per_cell": p26_execution[
                "negative_control_replicates_per_cell"
            ],
            "negative_control_replicate_count": p26_execution[
                "negative_control_replicate_count"
            ],
            "actual_fold_count": 0,
            "registered_artifact_count": 3,
            "engineering_progress_before": 39,
            "engineering_progress_after": 40,
            "evidence_progress_before": 25,
            "evidence_progress_after": 25,
            "downstream_consumer": (
                "m4-p3-strict-historical-walk-forward"
                if gate["decision"] == "PASS_TO_P3"
                else "m4-p2-repair-measurement-system"
            ),
            "eligible_for_formal_inference": True,
            "git_commit": git_commit,
            "working_tree_clean": True,
            "production_impact": "none",
            "parent_digests": [
                *task.input_artifact_digests,
                p26_execution["artifact_digest"],
                completion["artifact_digest"],
                gate["artifact_digest"],
                mde["artifact_digest"],
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        child_payloads = ((mde_path, mde), (gate_path, gate))
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=(str(gate["decision_fact"]),),
            additional_completed_task_keys=(
                (P2_UMBRELLA_TASK_KEY,) if gate["decision"] == "PASS_TO_P3" else ()
            ),
        )


def _progress_projection_path(task_key: str) -> Path | None:
    return {
        P26_TASK_KEY: Path(
            "runtime/logs/m4-p2-6-3-measurement-validation-progress.json"
        ),
        MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY: (
            MARGINAL_STATIC_HEALTH_PROGRESS_PATH
        ),
        MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_TASK_KEY: (
            MARGINAL_STATIC_REPAIR_HEALTH_PROGRESS_PATH
        ),
        MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_TASK_KEY: (
            MARGINAL_STATIC_REPAIR_V2_HEALTH_PROGRESS_PATH
        ),
    }.get(task_key)


class ResearchEvidenceSupervisor:
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository | None = None,
        control_plane_key: str = M4_CONTROL_PLANE_KEY,
        root_dir: Path = ROOT_DIR,
        now: Callable[[], datetime] | None = None,
        git_commit: str | None = None,
        require_clean_tree: bool = True,
    ) -> None:
        if control_plane_key not in _TASK_ARTIFACT_NAMESPACE_BY_CONTROL_PLANE:
            raise MainlineSupervisorError(
                "mainline artifact control plane is not registered"
            )
        self.repository = repository or PostgresResearchOSRepository()
        self.control_plane_key = control_plane_key
        self.root_dir = root_dir
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.git_commit = git_commit
        self.require_clean_tree = require_clean_tree
        self.capabilities = {
            P23_CAPABILITY: P23WalkForwardCapability(root_dir=root_dir),
            P24_CAPABILITY: P24InjectedSignalCalibrationCapability(root_dir=root_dir),
            P25_CAPABILITY: P25ResamplingCapability(root_dir=root_dir),
            P26_PREFLIGHT_CAPABILITY: P26IdentifiabilityPreflightCapability(
                root_dir=root_dir
            ),
            P26_REPAIR_CAPABILITY: P26MeasurementSystemRepairCapability(
                root_dir=root_dir
            ),
            P26_CAPABILITY: P26MeasurementValidationCapability(root_dir=root_dir),
            P27_CAPABILITY: P27AutomaticMeasurementGateCapability(root_dir=root_dir),
            M4_P263_COMPATIBILITY_CAPABILITY: (
                M4P263SupersedingCompatibilityCapability(root_dir=root_dir)
            ),
            M4_V2_DESIGN_CAPABILITY: M4MeasurementContractV2DesignCapability(
                root_dir=root_dir
            ),
            M4_V2_DESIGN_REPLAY_CAPABILITY: (
                M4MeasurementContractV2DesignReplayCapability(
                    repository=self.repository,
                    root_dir=root_dir,
                )
            ),
            PREFLIGHT_DESIGN_CAPABILITY: (
                M4BranchIdentifiabilityPreflightDesignCapability(
                    repository=self.repository,
                    root_dir=root_dir,
                )
            ),
            FIXTURE_FREEZE_CAPABILITY: (
                M4BranchIdentifiabilityFixtureFreezeCapability(
                    repository=self.repository,
                    root_dir=root_dir,
                )
            ),
            PREFLIGHT_EXECUTION_CAPABILITY: (
                M4BranchIdentifiabilityPreflightExecutionCapability(
                    repository=self.repository,
                    root_dir=root_dir,
                )
            ),
            MARGINAL_STATIC_CONTRACT_FREEZE_CAPABILITY: (
                M4MarginalStaticContractFreezeCapability(
                    repository=self.repository,
                    root_dir=root_dir,
                )
            ),
            MARGINAL_STATIC_FIXTURE_FREEZE_CAPABILITY: (
                M4MarginalStaticFixtureFreezeCapability(
                    repository=self.repository,
                    root_dir=root_dir,
                )
            ),
            MARGINAL_STATIC_HEALTH_DESIGN_CAPABILITY: (
                M4MarginalStaticHealthDesignCapability(
                    repository=self.repository,
                    root_dir=root_dir,
                )
            ),
            MARGINAL_STATIC_HEALTH_EXECUTION_CAPABILITY: (
                M4MarginalStaticHealthExecutionCapability(
                    repository=self.repository,
                    root_dir=root_dir,
                )
            ),
            MARGINAL_STATIC_HEALTH_DECISION_CAPABILITY: (
                M4MarginalStaticHealthDecisionCapability(
                    repository=self.repository,
                    root_dir=root_dir,
                )
            ),
            MARGINAL_STATIC_REPAIR_DESIGN_CAPABILITY: (
                M4MarginalStaticRepairDesignCapability(
                    repository=self.repository,
                    root_dir=root_dir,
                )
            ),
            MARGINAL_STATIC_REPAIR_PREREGISTRATION_CAPABILITY: (
                M4MarginalStaticRepairPreregistrationCapability(
                    repository=self.repository,
                    root_dir=root_dir,
                )
            ),
            MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_CAPABILITY: (
                M4MarginalStaticRepairHealthExecutionCapability(
                    repository=self.repository,
                    root_dir=root_dir,
                )
            ),
            MARGINAL_STATIC_REPAIR_HEALTH_DECISION_CAPABILITY: (
                M4MarginalStaticRepairHealthDecisionCapability(
                    repository=self.repository,
                    root_dir=root_dir,
                )
            ),
            MARGINAL_STATIC_REPAIR_V2_DESIGN_CAPABILITY: (
                M4MarginalStaticRepairV2DesignCapability(
                    repository=self.repository,
                    root_dir=root_dir,
                )
            ),
            MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_CAPABILITY: (
                M4MarginalStaticRepairV2PreregistrationCapability(
                    repository=self.repository,
                    root_dir=root_dir,
                )
            ),
            MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_CAPABILITY: (
                M4MarginalStaticRepairV2HealthExecutionCapability(
                    repository=self.repository,
                    root_dir=root_dir,
                )
            ),
            MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_CAPABILITY: (
                M4MarginalStaticRepairV2HealthDecisionCapability(
                    repository=self.repository,
                    root_dir=root_dir,
                )
            ),
            MARGINAL_STATIC_HISTORICAL_DESIGN_CAPABILITY: (
                M4MarginalStaticHistoricalDesignCapability(
                    repository=self.repository,
                    root_dir=root_dir,
                )
            ),
            M4_V2_P261_RAW_REPLAY_CAPABILITY: (
                M4P261RawExecutionReplayCapability(
                    repository=self.repository,
                    root_dir=root_dir,
                )
            ),
            M4_V2_P27_GATE_REPLAY_CAPABILITY: M4P27GateReplayCapability(
                repository=self.repository,
                root_dir=root_dir,
            ),
            M4_V2_MARGINAL_BINDING_CAPABILITY: M4P261MarginalBindingCapability(
                repository=self.repository,
                root_dir=root_dir,
            ),
            M4_V2_MARGINAL_DECISION_REPLAY_CAPABILITY: (
                M4P261MarginalDecisionReplayCapability(
                    repository=self.repository,
                    root_dir=root_dir,
                )
            ),
            M4_P29_GOLDEN_REFERENCE_CAPABILITY: M4P29GoldenReferenceCapability(
                root_dir=root_dir
            ),
            M4_P29_RUNTIME_AUDIT_CAPABILITY: M4P29MeasurementRuntimeAuditCapability(
                repository=self.repository, root_dir=root_dir
            ),
            P263_SLOT_ELIGIBILITY_CAPABILITY: (
                M4P263RuntimeSlotEligibilityCapability(
                    repository=self.repository,
                    root_dir=root_dir,
                )
            ),
            PREDICTION_V2_REFERENCE_CAPABILITY: PredictionV2ReferenceCapability(
                root_dir=root_dir
            ),
            PREDICTION_V2_REPLAY_CAPABILITY: PredictionV2ReplayCapability(
                repository=self.repository,
                root_dir=root_dir,
            ),
            PREDICTION_V2_CUTOVER_CAPABILITY: PredictionV2LiveActivationCapability(
                root_dir=root_dir,
            ),
            PREDICTION_V2_PRE_CAPABILITY: PredictionV2IssuePreDrawCapability(
                root_dir=root_dir,
            ),
            PREDICTION_V2_PRE_REPLAY_CAPABILITY: PredictionV2IssuePreDrawReplayCapability(
                repository=self.repository,
                root_dir=root_dir,
            ),
            PREDICTION_V2_POST_CAPABILITY: PredictionV2IssuePostDrawCapability(
                repository=self.repository,
                root_dir=root_dir,
            ),
            PREDICTION_V2_POST_REPLAY_CAPABILITY: PredictionV2IssuePostDrawReplayCapability(
                repository=self.repository,
                root_dir=root_dir,
            ),
        }

    @property
    def state_path(self) -> Path:
        if self.control_plane_key == PREDICTION_V2_CONTROL_PLANE_KEY:
            return (
                self.root_dir
                / "runtime/logs/prediction-v2-shadow-supervisor-state.json"
            )
        return self.root_dir / "runtime/logs/research-evidence-supervisor-state.json"

    def run_once(self, *, task_key: str | None = None) -> dict[str, Any]:
        self.repository.ensure_schema()
        runtime_git_commit = self.git_commit or resolve_git_commit(self.root_dir)
        git_commit = runtime_git_commit
        runtime_migration: Mapping[str, Any] | None = None
        if self.require_clean_tree:
            dirty = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.root_dir,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            if dirty:
                raise MainlineSupervisorError(
                    "dirty_worktree: mainline execution requires a clean tree"
                )

        manifest = self.repository.load_manifest(
            control_plane_key=self.control_plane_key
        )
        snapshot = self.repository.control_plane.resolve(manifest)
        task_by_key = {task.task_key: task for task in manifest.tasks}
        task_states = manifest.task_state_by_digest
        failed_recovery_token = os.environ.get(P26_FAILED_RECOVERY_EVENT_ENV, "")
        running = [
            item
            for item in snapshot.resolutions
            if item.status is TaskStatus.RUNNING
            and (task_key is None or item.task_key == task_key)
            and task_by_key[item.task_key].requested_capability in self.capabilities
        ]
        ready = [
            item
            for item in snapshot.ready_queue
            if (task_key is None or item.task_key == task_key)
            and task_by_key[item.task_key].requested_capability in self.capabilities
        ]
        failed_recovery = [
            item
            for item in snapshot.resolutions
            if failed_recovery_token
            and item.status is TaskStatus.FAILED
            and item.task_key == P26_TASK_KEY
            and (task_key is None or item.task_key == task_key)
            and task_by_key[item.task_key].requested_capability in self.capabilities
        ]
        if not running and not ready and not failed_recovery:
            unsupported = [
                item.task_key
                for item in snapshot.ready_queue
                if task_by_key[item.task_key].requested_capability
                not in self.capabilities
            ]
            payload = {
                "schema_version": "dehps-research-evidence-supervisor-state.v1",
                "status": "WAITING_FOR_CAPABILITY" if unsupported else "IDLE",
                "control_plane_key": self.control_plane_key,
                "manifest_digest": manifest.artifact_digest,
                "snapshot_digest": snapshot.snapshot_digest,
                "ready_tasks": [item.task_key for item in snapshot.ready_queue],
                "unsupported_ready_tasks": unsupported,
                "dispatch_performed": False,
                "git_commit": git_commit,
                "heartbeat_at": self.now().isoformat(),
            }
            self._write_state(payload)
            self._write_lane_status(
                self._build_lane_status(
                    manifest,
                    snapshot=snapshot,
                    dispatch_performed=False,
                )
            )
            return payload

        item = (running or ready or failed_recovery)[0]
        task = task_by_key[item.task_key]
        capability = str(task.requested_capability)
        declared_status = task_states[task.artifact_digest].declared_status
        is_failed_recovery = declared_status is TaskStatus.FAILED
        is_resume = declared_status in {TaskStatus.RUNNING, TaskStatus.FAILED}
        terminal_sequence = 1
        incident_recovery: Mapping[str, Any] | None = None
        if is_resume:
            running_manifest = manifest
            running_manifest_digest = manifest.artifact_digest
            events = self.repository.list_mainline_execution_events(
                control_plane_key=self.control_plane_key,
                task_key=task.task_key,
            )
            completed = [
                event
                for event in events
                if event.get("task_digest") == task.artifact_digest
                and event.get("event_type") == "completed"
            ]
            if len(completed) == 1:
                return self._finalize_completed_execution(
                    manifest=manifest,
                    task=task,
                    event=completed[0],
                    git_commit=str(
                        _event_payload(completed[0]).get("git_commit") or git_commit
                    ),
                )
            started = [
                event
                for event in events
                if event.get("task_digest") == task.artifact_digest
                and event.get("event_type") == "started"
            ]
            failed = [
                event
                for event in events
                if event.get("task_digest") == task.artifact_digest
                and event.get("event_type") == "failed"
            ]
            recovered_failure = self._validated_p26_failed_recovery_event(
                task=task,
                events=events,
                token=failed_recovery_token,
            )
            if (
                (failed and recovered_failure is None)
                or len(started) > 1
                or len(completed) > 1
            ):
                raise MainlineSupervisorError(
                    f"inconsistent persisted execution state for running task: {task.task_key}"
                )
            if started:
                execution_id = str(started[0]["execution_id"])
                if recovered_failure is not None:
                    if execution_id != P26_FAILED_RECOVERY_EXECUTION_ID:
                        raise MainlineSupervisorError(
                            "P2.6 failed recovery execution identity changed"
                        )
                    terminal_sequence = 2
                    if is_failed_recovery:
                        incident_recovery = self._record_p26_failed_recovery(
                            task=task,
                            execution_id=execution_id,
                            failed_event=recovered_failure,
                            runtime_git_commit=runtime_git_commit,
                        )
                        running_payload = self._transition_manifest(
                            manifest,
                            task_key=task.task_key,
                            status=TaskStatus.RUNNING,
                            classification=CompletionClassification.INTEGRATED,
                        )
                        running_import = self.repository.import_manifest(
                            control_plane_key=self.control_plane_key,
                            payload=running_payload,
                            source=(
                                "research-evidence-supervisor-"
                                "recoverable-pre-dispatch-failure"
                            ),
                        )
                        running_manifest = self.repository.load_manifest(
                            control_plane_key=self.control_plane_key
                        )
                        running_manifest_digest = running_import.manifest_digest
                        if (
                            running_manifest_digest
                            != P26_FAILED_RECOVERY_RUNNING_MANIFEST_DIGEST
                        ):
                            raise MainlineSupervisorError(
                                "P2.6 failed recovery running manifest changed"
                            )
                original_commit = str(
                    _event_payload(started[0]).get("git_commit") or ""
                )
                if original_commit != git_commit:
                    allowed_origin = os.environ.get(P26_EQUIVALENT_RESUME_ENV, "")
                    if (
                        task.task_key != P26_TASK_KEY
                        or not allowed_origin
                        or allowed_origin != original_commit
                    ):
                        raise MainlineSupervisorError(
                            "running execution git commit differs from the current clean tree"
                        )
                    runtime_migration = self._record_p26_runtime_migration(
                        task=task,
                        execution_id=execution_id,
                        execution_git_commit=original_commit,
                        runtime_git_commit=runtime_git_commit,
                    )
                    git_commit = original_commit
            else:
                execution_id = self._execution_id(
                    task=task,
                    capability=capability,
                    git_commit=git_commit,
                )
                self._record_started_event(
                    task=task,
                    capability=capability,
                    execution_id=execution_id,
                    manifest_digest=running_manifest_digest,
                    git_commit=git_commit,
                )
        else:
            execution_id = self._execution_id(
                task=task,
                capability=capability,
                git_commit=git_commit,
            )
            existing = self._completed_event(execution_id)
            if existing is not None:
                return self._finalize_completed_execution(
                    manifest=manifest,
                    task=task,
                    event=existing,
                    git_commit=git_commit,
                )
            running_payload = self._transition_manifest(
                manifest,
                task_key=task.task_key,
                status=TaskStatus.RUNNING,
                classification=CompletionClassification.INTEGRATED,
            )
            running_import = self.repository.import_manifest(
                control_plane_key=self.control_plane_key,
                payload=running_payload,
                source="research-evidence-supervisor-running",
            )
            running_manifest = self.repository.load_manifest(
                control_plane_key=self.control_plane_key
            )
            running_manifest_digest = running_import.manifest_digest
            self._record_started_event(
                task=task,
                capability=capability,
                execution_id=execution_id,
                manifest_digest=running_manifest_digest,
                git_commit=git_commit,
            )
        running_snapshot = self.repository.control_plane.resolve(running_manifest)
        running_status = self._build_lane_status(
            running_manifest,
            snapshot=running_snapshot,
            dispatch_performed=True,
        )
        progress_projection_path = _progress_projection_path(task.task_key)
        self._write_state(
            {
                "schema_version": "dehps-research-evidence-supervisor-state.v1",
                "status": "RUNNING",
                "control_plane_key": self.control_plane_key,
                "task_key": task.task_key,
                "task_digest": task.artifact_digest,
                "execution_id": execution_id,
                "capability": capability,
                "manifest_digest": running_manifest_digest,
                "snapshot_digest": running_snapshot.snapshot_digest,
                "dispatch_performed": True,
                "git_commit": git_commit,
                "runtime_git_commit": runtime_git_commit,
                **(
                    {"runtime_migration_digest": runtime_migration["artifact_digest"]}
                    if runtime_migration is not None
                    else {}
                ),
                **(
                    {"incident_recovery_digest": incident_recovery["artifact_digest"]}
                    if incident_recovery is not None
                    else {}
                ),
                "heartbeat_at": self.now().isoformat(),
                **(
                    {"progress_projection_path": str(progress_projection_path)}
                    if progress_projection_path is not None
                    else {}
                ),
            }
        )
        self._write_lane_status(running_status)
        completed_recorded = False
        try:
            result = self.capabilities[capability].execute(
                control_plane_key=self.control_plane_key,
                task=task,
                execution_id=execution_id,
                git_commit=git_commit,
            )
            for registration in result.registrations:
                self.repository.register_mainline_artifact(registration=registration)
            completed_at = self.now().isoformat()
            completed = MainlineExecutionEvent(
                execution_id=execution_id,
                control_plane_key=self.control_plane_key,
                manifest_digest=running_manifest_digest,
                task_key=task.task_key,
                task_digest=task.artifact_digest,
                capability=capability,
                event_type="completed",
                sequence=terminal_sequence,
                recorded_at=completed_at,
                payload=tuple(
                    sorted(
                        {
                            "execution_artifact_digest": result.execution_artifact[
                                "artifact_digest"
                            ],
                            "execution_artifact_path": str(
                                result.execution_artifact_path.relative_to(
                                    self.root_dir
                                )
                            ),
                            "actual_fold_count": result.execution_artifact[
                                "actual_fold_count"
                            ],
                            "registered_artifact_count": len(result.registrations),
                            "git_commit": git_commit,
                            "completion_facts": list(result.completion_facts),
                            "additional_completed_task_keys": list(
                                result.additional_completed_task_keys
                            ),
                            **{
                                key: result.execution_artifact[key]
                                for key in (
                                    "calibration_run_manifest_digest",
                                    "calibration_run_artifact_digest",
                                    "completion_artifact_digest",
                                    "truth_artifact_digests",
                                    "truth_artifact_count",
                                    "eligible_for_p2_5_input",
                                    "eligible_for_power_evidence",
                                    "resampling_kernel_digest",
                                    "resampling_run_digest",
                                    "resampling_completion_digest",
                                    "child_replicate_digests",
                                    "aggregate_digests",
                                    "replicate_count",
                                    "aggregate_count",
                                    "eligible_for_formal_inference",
                                    "measurement_validation_manifest_digest",
                                    "measurement_update_policy_digest",
                                    "identifiability_preflight_manifest_digest",
                                    "identifiability_preflight_report_digest",
                                    "superseded_run_archive_digest",
                                    "execution_plan_digest",
                                    "automatic_gate_digest",
                                    "mde_summary_digest",
                                    "decision",
                                    "decision_fact",
                                    "failed_requirements",
                                    "scenario_count",
                                    "p2_6_partial_statistical_results_inspected",
                                    "old_p2_6_execution_resumable",
                                    "old_p2_6_partial_statistical_results_inspected",
                                    "measurement_repair_manifest_digest",
                                    "repaired_measurement_validation_manifest_digest",
                                    "development_selection_artifact_digest",
                                    "identifiability_confirmation_digest",
                                    "outer_fold_fit_count_before",
                                    "outer_fold_fit_count_after",
                                    "estimator_and_calibrator_fit_count",
                                    "learned_probe_fit_count",
                                    "learned_probe_refit_boundary_count",
                                    "learned_probe_refit_interval_folds",
                                    "empirical_baseline_update_count",
                                    "probe_preparation_count",
                                    "superseded_every_fold_fit_count",
                                    "inner_model_selection_per_outer_fold",
                                    "formal_power_target_count",
                                    "joint_only_negative_control_count",
                                    "feasibility_sentinel_count",
                                    "replay_status",
                                    "bootstrap_replicate_count",
                                    "permutation_replicate_count",
                                    "negative_control_id",
                                    "negative_control_cell_count",
                                    "negative_control_replicates_per_cell",
                                    "negative_control_replicate_count",
                                    "decision_policy_mde_at_61_bits_per_issue",
                                    "false_positive_by_scale",
                                    "power_by_cell",
                                    "estimator_quality_by_cell",
                                    "marginal_static_health_design_source_contract_digest",
                                    "marginal_static_health_design_source_set_digest",
                                    "marginal_static_health_workload_digest",
                                    "marginal_static_health_inference_digest",
                                    "marginal_static_health_design_completion_digest",
                                    "marginal_static_health_execution_source_contract_digest",
                                    "marginal_static_health_execution_source_set_digest",
                                    "marginal_static_health_completion_index_digest",
                                    "marginal_static_health_result_digest",
                                    "marginal_static_health_execution_completion_digest",
                                    "marginal_static_health_decision_source_contract_digest",
                                    "marginal_static_health_decision_source_set_digest",
                                    "health_execution_artifact_digest",
                                    "health_result_digest",
                                    "health_completion_digest",
                                    "marginal_static_health_decision_artifact_digest",
                                    "failed_cell_ids",
                                    "failed_cell_count",
                                    "eligible_for_historical_measurement",
                                    "marginal_static_repair_design_source_contract_digest",
                                    "marginal_static_repair_design_source_set_digest",
                                    "health_decision_execution_id",
                                    "health_decision_execution_artifact_digest",
                                    "health_decision_artifact_digest",
                                    "marginal_static_repair_analytic_feasibility_digest",
                                    "marginal_static_repair_design_artifact_digest",
                                    "marginal_static_repair_design_completion_digest",
                                    "marginal_static_repair_preregistration_source_contract_digest",
                                    "marginal_static_repair_preregistration_source_set_digest",
                                    "research_addendum_key",
                                    "research_addendum_request_id",
                                    "research_addendum_execution_id",
                                    "repair_design_execution_id",
                                    "repair_design_execution_artifact_digest",
                                    "repair_analytic_feasibility_digest",
                                    "repair_design_artifact_digest",
                                    "repair_design_completion_digest",
                                    "marginal_static_repair_health_workload_seed_digest",
                                    "marginal_static_repair_health_inference_gate_digest",
                                    "marginal_static_repair_health_preregistration_digest",
                                    "marginal_static_repair_health_preregistration_completion_digest",
                                    "marginal_static_repair_health_execution_source_contract_digest",
                                    "marginal_static_repair_health_execution_source_set_digest",
                                    "engineering_execution_id",
                                    "repair_preregistration_execution_id",
                                    "repair_preregistration_execution_artifact_digest",
                                    "marginal_static_repair_health_completion_index_digest",
                                    "marginal_static_repair_health_feasibility_digest",
                                    "marginal_static_repair_health_result_digest",
                                    "marginal_static_repair_health_execution_completion_digest",
                                    "repair_health_preliminary_measurement_health",
                                    "repair_health_authoritative_decision",
                                    "marginal_static_repair_health_decision_source_contract_digest",
                                    "marginal_static_repair_health_decision_source_set_digest",
                                    "repair_health_execution_artifact_digest",
                                    "marginal_static_repair_v2_design_source_contract_digest",
                                    "marginal_static_repair_v2_design_source_set_digest",
                                    "repair_health_decision_execution_id",
                                    "repair_health_decision_execution_digest",
                                    "repair_health_decision_digest",
                                    "presample_feasibility_digest",
                                    "repair_v2_design_digest",
                                    "repair_v2_design_completion_digest",
                                    "reference_scores_per_block",
                                    "evaluation_replicates_per_cell",
                                    "future_total_replicates",
                                    "future_generated_issues",
                                    "familywise_false_repair_union_bound",
                                    "marginal_static_repair_v2_preregistration_source_contract_digest",
                                    "marginal_static_repair_v2_preregistration_source_set_digest",
                                    "repair_v2_design_execution_id",
                                    "repair_v2_design_execution_digest",
                                    "repair_v2_presample_feasibility_digest",
                                    "repair_v2_workload_seed_digest",
                                    "repair_v2_inference_gate_digest",
                                    "repair_v2_preregistration_digest",
                                    "repair_v2_preregistration_completion_digest",
                                    "future_reference_children",
                                    "future_evaluation_children",
                                    "future_total_children",
                                    "future_shard_count",
                                    "future_shard_size",
                                    "future_outer_evaluation_issues",
                                    "future_completion_index_loads",
                                    "completed_matching_child_action",
                                    "new_child_dispatch",
                                    "repair_health_result_digest",
                                    "repair_health_completion_digest",
                                    "marginal_static_repair_health_decision_artifact_digest",
                                    "authoritative_decision",
                                    "failed_control_cell_ids",
                                    "failed_control_topology",
                                    "failed_control_cell_count",
                                    "instrument_limit_cell_count",
                                    "calibration_replicates",
                                    "evaluation_replicates",
                                    "checkpoint_mode",
                                    "round_42_statistical_results_read",
                                    "planned_calibration_replicates",
                                    "planned_evaluation_replicates",
                                    "max_rejecting_exceedance_count",
                                    "nested_bootstrap_replicates_per_formal_replicate",
                                    "independent_calibration_seed_domain",
                                    "independent_evaluation_seed_domain",
                                    "calibration_evaluation_seed_overlap",
                                    "formal_execution_authorized",
                                    "automatic_pass_from_preregistration",
                                    "forward_61_gate_admissible",
                                    "forward_61_classification",
                                    "independent_root_seed_domain",
                                    "independent_bootstrap_seed_domain",
                                    "round_42_seed_reuse",
                                    "automatic_pass_from_reanalysis",
                                    "same_seed_tuning",
                                    "posthoc_threshold_change",
                                    "synthetic_replicates",
                                    "checkpoint_reads",
                                    "compact_index_reads",
                                    "sentinel_replicates_recomputed",
                                    "duplicate_validation",
                                    "statistical_results_read",
                                    "repair_required",
                                    "promotion_gate_opened",
                                    "planned_total_replicates",
                                    "planned_total_generated_issues",
                                    "planned_total_outer_evaluation_issues",
                                    "planned_execution_shards",
                                    "execution_shard_size",
                                    "bootstrap_replicates_per_interval",
                                    "primary_block_size",
                                    "sensitivity_block_sizes",
                                    "legacy_replicates",
                                    "legacy_outer_issue_predictions",
                                    "legacy_probe_fits_reused",
                                    "legacy_results_reused",
                                    "bootstrap_replicates_executed",
                                    "completion_index_loads",
                                    "runtime_migration_digests",
                                    "runtime_git_commits",
                                    "incident_recovery_digests",
                                    "measurement_contract_v2_digest",
                                    "estimand_contract_digest",
                                    "mechanism_role_contract_digest",
                                    "gate_compiler_contract_digest",
                                    "design_execution_id",
                                    "design_execution_artifact_digest",
                                    "measurement_contract_replay_digest",
                                    "gate_compiler_replay_digest",
                                    "design_replay_execution_id",
                                    "design_replay_execution_artifact_digest",
                                    "preflight_source_contract_digest",
                                    "preflight_source_set_digest",
                                    "branch_preflight_design_digests",
                                    "cross_branch_preflight_design_digest",
                                    "preflight_design_completion_digest",
                                    "preflight_execution_count",
                                    "preflight_result_count",
                                    "fixture_freeze_source_contract_digest",
                                    "fixture_freeze_source_set_digest",
                                    "preflight_design_execution_id",
                                    "preflight_design_execution_artifact_digest",
                                    "solver_fixture_contract_digest",
                                    "orthogonal_control_fixture_contract_digest",
                                    "legacy_role_resolution_fixture_contract_digest",
                                    "fixture_freeze_completion_digest",
                                    "fixture_contract_count",
                                    "preflight_execution_source_contract_digest",
                                    "preflight_execution_source_set_digest",
                                    "fixture_execution_id",
                                    "fixture_execution_artifact_digest",
                                    "solver_preflight_result_digest",
                                    "orthogonal_endpoint_result_digest",
                                    "legacy_role_preflight_result_digest",
                                    "branch_preflight_result_digests",
                                    "preflight_execution_completion_digest",
                                    "preflight_execution_status",
                                    "branch_preflight_statuses",
                                    "solver_preflight_status",
                                    "orthogonal_endpoint_status",
                                    "legacy_role_resolution_status",
                                    "all_branches_pass",
                                    "all_branches_pass_fact",
                                    "orthogonal_endpoint_count",
                                    "legacy_state_result_count",
                                    "monte_carlo_replicates",
                                    "marginal_static_source_contract_digest",
                                    "marginal_static_source_set_digest",
                                    "preflight_execution_id",
                                    "preflight_execution_artifact_digest",
                                    "marginal_branch_design_digest",
                                    "marginal_branch_health_digest",
                                    "legacy_marginal_decision_digest",
                                    "legacy_decision_replay_digest",
                                    "marginal_static_measurement_contract_digest",
                                    "marginal_static_contract_completion_digest",
                                    "branch_id",
                                    "estimator_id",
                                    "identifiability_preflight_status",
                                    "legacy_measurement_health",
                                    "legacy_repair_overridden",
                                    "accepted_model_artifact_digest",
                                    "sampled_synthetic_execution_status",
                                    "historical_execution_status",
                                    "synthetic_replicates",
                                    "marginal_static_fixture_source_contract_digest",
                                    "marginal_static_fixture_source_set_digest",
                                    "marginal_contract_execution_id",
                                    "marginal_contract_execution_artifact_digest",
                                    "branch_fixture_completion_digest",
                                    "marginal_static_fixture_digests",
                                    "marginal_static_fixture_bundle_digest",
                                    "marginal_static_fixture_completion_digest",
                                    "fixture_count",
                                    "positive_fixture_count",
                                    "negative_fixture_count",
                                    "runtime_state",
                                    "database_reads_during_replicate",
                                    "database_writes_during_replicate",
                                    "csv_materialized",
                                    "duplicate_raw_replay",
                                    "routine_physical_checkpoint_scan",
                                    "sampled_workload_status",
                                    "generated_issues",
                                    "outer_evaluation_issues",
                                    "completed_replicates_before_run",
                                    "completed_replicates_during_run",
                                    "execution_runtime_seconds",
                                    "worker_count",
                                    "p2_6_1_execution_id",
                                    "p2_6_1_execution_artifact_digest",
                                    "raw_replay_artifact_digest",
                                    "p2_7_execution_id",
                                    "p2_7_execution_artifact_digest",
                                    "gate_replay_artifact_digest",
                                    "binding_contract_digest",
                                    "marginal_decision_artifact_digest",
                                    "branch_decision_replay_artifact_digest",
                                    "measurement_health",
                                    "historical_evidence",
                                    "promotion_gate_opened",
                                    "production_candidate_created",
                                    "m4_state_changed",
                                    "formal_branch_runs_executed",
                                    "historical_outcomes_read",
                                    "p2_6_1_partial_statistical_results_read",
                                    "p2_6_3_statistical_results_read",
                                    "p2_6_3_task_digest",
                                    "production_action",
                                    "benchmark_plan_artifact_digest",
                                    "runtime_observation_artifact_digest",
                                    "runtime_benchmark_attempt_artifact_digest",
                                    "source_integrity_attestation_artifact_digest",
                                    "golden_source_integrity_attestation_artifact_digest",
                                    "runtime_executor_fingerprint_digest_before",
                                    "runtime_executor_fingerprint_digest_after",
                                    "equivalence_attestation_artifact_digest",
                                    "golden_reference_execution_artifact_digest",
                                    "golden_reference_plan_artifact_digest",
                                    "golden_reference_fixture_artifact_digest",
                                    "golden_reference_replay_artifact_digest",
                                    "immutable_golden_fixture_is_oracle",
                                    "acceleration_boundary_independent",
                                    "acceleration_boundary_independence_scope",
                                    "oracle_construction_process_isolated",
                                    "oracle_construction_fully_implementation_independent",
                                    "exact_replay_verified",
                                    "reference_evaluator_is_oracle",
                                    "exact_golden_replay_verified",
                                    "audited_fold_count",
                                    "correctness_replay_fold_count",
                                    "total_execution_fold_count",
                                    "correctness_boundary_snapshot_count",
                                    "frozen_reference_fold_count",
                                    "benchmark_attempt_id",
                                    "benchmark_attempt_path",
                                    "measured_workdir_path",
                                    "correctness_replay_workdir_path",
                                    "journal_reused",
                                    "fresh_workdir",
                                    "shared_frozen_source_modified",
                                    "backend_source_modified",
                                    "acceleration_changed_paths",
                                    "backend_optimization_applied",
                                    "statistical_semantics_modified",
                                    "engineering_progress_before",
                                    "engineering_progress_after",
                                    "evidence_progress_before",
                                    "evidence_progress_after",
                                    "marginal_static_historical_design_source_contract_digest",
                                    "marginal_static_historical_design_source_set_digest",
                                    "historical_dataset_boundary_digest",
                                    "historical_walk_forward_design_digest",
                                    "historical_inference_design_digest",
                                    "historical_design_completion_digest",
                                    "historical_issue_count",
                                    "initial_training_issue_count",
                                    "planned_evaluation_fold_count",
                                    "planned_bootstrap_replicates",
                                    "formal_historical_folds_executed",
                                    "database_queries_during_capability",
                                    "historical_red_outcomes_read",
                                    "statistical_results_read",
                                )
                                if key in result.execution_artifact
                            },
                        }.items()
                    )
                ),
            )
            self.repository.record_mainline_execution_event(event=completed)
            completed_recorded = True
            return self._finalize_completed_execution(
                manifest=running_manifest,
                task=task,
                event={
                    "execution_id": execution_id,
                    "recorded_at": completed_at,
                    "payload": [list(item) for item in completed.payload],
                },
                git_commit=git_commit,
            )
        except Exception as exc:
            if completed_recorded:
                raise
            runtime_commit_marker = (
                self.root_dir
                / "runtime/research-os/mainline/tasks"
                / task.task_key
                / execution_id
                / "execution.json"
            )
            if (
                task.task_key == M4_P29_RUNTIME_AUDIT_TASK_KEY
                and runtime_commit_marker.is_file()
            ):
                # execution.json is the capability commit boundary.  A crash
                # or database failure after it exists must remain resumable;
                # the next turn validates the marker and reconstructs the
                # exact registrations without rerunning timed work.
                payload = {
                    "schema_version": ("dehps-research-evidence-supervisor-state.v1"),
                    "status": "RECOVERY_REQUIRED",
                    "control_plane_key": self.control_plane_key,
                    "task_key": task.task_key,
                    "execution_id": execution_id,
                    "commit_marker_path": str(
                        runtime_commit_marker.relative_to(self.root_dir)
                    ),
                    "error": str(exc),
                    "dispatch_performed": True,
                    "git_commit": git_commit,
                    "heartbeat_at": self.now().isoformat(),
                }
                self._write_state(payload)
                raise
            failed = MainlineExecutionEvent(
                execution_id=execution_id,
                control_plane_key=self.control_plane_key,
                manifest_digest=running_manifest_digest,
                task_key=task.task_key,
                task_digest=task.artifact_digest,
                capability=capability,
                event_type="failed",
                sequence=terminal_sequence,
                recorded_at=self.now().isoformat(),
                payload=(("error", str(exc)), ("git_commit", git_commit)),
            )
            self.repository.record_mainline_execution_event(event=failed)
            failed_manifest = self._transition_manifest(
                running_manifest,
                task_key=task.task_key,
                status=TaskStatus.FAILED,
                classification=CompletionClassification.INTEGRATED,
            )
            self.repository.import_manifest(
                control_plane_key=self.control_plane_key,
                payload=failed_manifest,
                source="research-evidence-supervisor-failed",
            )
            payload = {
                "schema_version": "dehps-research-evidence-supervisor-state.v1",
                "status": "FAILED",
                "control_plane_key": self.control_plane_key,
                "task_key": task.task_key,
                "execution_id": execution_id,
                "error": str(exc),
                "dispatch_performed": True,
                "git_commit": git_commit,
                "heartbeat_at": self.now().isoformat(),
            }
            self._write_state(payload)
            raise

    def _execution_id(
        self,
        *,
        task: Task,
        capability: str,
        git_commit: str,
    ) -> str:
        return stable_hash(
            {
                "schema": MAINLINE_EXECUTION_SCHEMA,
                "control_plane_key": self.control_plane_key,
                "task_digest": task.artifact_digest,
                "capability": capability,
                "input_artifact_digests": task.input_artifact_digests,
                "git_commit": git_commit,
            }
        )

    def _latest_completed_summary(
        self,
        snapshot: Any,
    ) -> dict[str, Any] | None:
        return self._latest_completed_summary_for_tasks(
            snapshot,
            (
                P27_TASK_KEY,
                P26_TASK_KEY,
                P26_REPAIR_TASK_KEY,
                P26_PREFLIGHT_TASK_KEY,
                P25_TASK_KEY,
                P24_TASK_KEY,
                P23_TASK_KEY,
            ),
        )

    def _latest_completed_v2_summary(
        self,
        snapshot: Any,
    ) -> dict[str, Any] | None:
        return self._latest_completed_summary_for_tasks(
            snapshot,
            (
                MARGINAL_STATIC_HISTORICAL_DESIGN_TASK_KEY,
                MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_TASK_KEY,
                MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_TASK_KEY,
                MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_TASK_KEY,
                MARGINAL_STATIC_REPAIR_V2_DESIGN_TASK_KEY,
                MARGINAL_STATIC_REPAIR_HEALTH_DECISION_TASK_KEY,
                MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_TASK_KEY,
                MARGINAL_STATIC_REPAIR_PREREGISTRATION_TASK_KEY,
                MARGINAL_STATIC_REPAIR_DESIGN_TASK_KEY,
                MARGINAL_STATIC_HEALTH_DECISION_TASK_KEY,
                MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY,
                MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY,
                MARGINAL_STATIC_FIXTURE_FREEZE_TASK_KEY,
                MARGINAL_STATIC_CONTRACT_FREEZE_TASK_KEY,
                PREFLIGHT_EXECUTION_TASK_KEY,
                FIXTURE_FREEZE_TASK_KEY,
                PREFLIGHT_DESIGN_TASK_KEY,
                M4_V2_MARGINAL_DECISION_REPLAY_TASK_KEY,
                M4_V2_MARGINAL_BINDING_TASK_KEY,
                M4_V2_P27_GATE_REPLAY_TASK_KEY,
                M4_V2_P261_RAW_REPLAY_TASK_KEY,
                M4_V2_DESIGN_REPLAY_TASK_KEY,
                M4_V2_DESIGN_TASK_KEY,
            ),
        )

    def _latest_completed_summary_for_tasks(
        self,
        snapshot: Any,
        task_keys: tuple[str, ...],
    ) -> dict[str, Any] | None:
        resolutions = {item.task_key: item.status for item in snapshot.resolutions}
        for candidate in task_keys:
            if resolutions.get(candidate) is not TaskStatus.COMPLETED:
                continue
            if candidate == MARGINAL_STATIC_HISTORICAL_DESIGN_TASK_KEY:
                event, artifact, _ = _load_single_completed_execution(
                    repository=self.repository,
                    root_dir=self.root_dir,
                    control_plane_key=self.control_plane_key,
                    task_key=candidate,
                )
                return {
                    **artifact,
                    **_event_payload(event),
                    "execution_task_key": candidate,
                }
            if candidate in {
                M4_P29_GOLDEN_REFERENCE_TASK_KEY,
                M4_P29_RUNTIME_AUDIT_TASK_KEY,
            }:
                event, _, _ = _load_single_completed_execution(
                    repository=self.repository,
                    root_dir=self.root_dir,
                    control_plane_key=self.control_plane_key,
                    task_key=candidate,
                )
                return {
                    **_event_payload(event),
                    "execution_task_key": candidate,
                }
            events = self.repository.list_mainline_execution_events(
                control_plane_key=self.control_plane_key,
                task_key=candidate,
            )
            completed = [
                event for event in events if event.get("event_type") == "completed"
            ]
            if len(completed) == 1:
                return {
                    **_event_payload(completed[0]),
                    "execution_task_key": candidate,
                }
        return None

    def _record_started_event(
        self,
        *,
        task: Task,
        capability: str,
        execution_id: str,
        manifest_digest: str,
        git_commit: str,
    ) -> None:
        started = MainlineExecutionEvent(
            execution_id=execution_id,
            control_plane_key=self.control_plane_key,
            manifest_digest=manifest_digest,
            task_key=task.task_key,
            task_digest=task.artifact_digest,
            capability=capability,
            event_type="started",
            sequence=0,
            recorded_at=self.now().isoformat(),
            payload=(
                ("input_artifact_digests", list(task.input_artifact_digests)),
                ("git_commit", git_commit),
            ),
        )
        if not self.repository.record_mainline_execution_event(event=started):
            raise MainlineSupervisorError(
                f"could not persist unique started event: {execution_id}"
            )

    def _finalize_completed_execution(
        self,
        *,
        manifest: ControlPlaneManifest,
        task: Task,
        event: Mapping[str, Any],
        git_commit: str,
    ) -> dict[str, Any]:
        requested_execution_id = str(event.get("execution_id") or "")
        persisted_event, persisted_execution, _ = _load_single_completed_execution(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=self.control_plane_key,
            task_key=task.task_key,
            require_manifest_complete=False,
        )
        current_manifest = self.repository.load_manifest(
            control_plane_key=self.control_plane_key
        )
        execution_id = str(persisted_execution["execution_id"])
        if (
            requested_execution_id != execution_id
            or persisted_execution.get("git_commit") != git_commit
            or manifest.artifact_digest != current_manifest.artifact_digest
        ):
            raise MainlineSupervisorError(
                f"completed execution cannot be finalized: {task.task_key}"
            )
        event = persisted_event
        summary = {
            **_event_payload(event),
            "execution_task_key": task.task_key,
        }
        completion_fact = mainline_completion_fact(
            task=task,
            execution_id=execution_id,
        )
        extra_facts = tuple(str(value) for value in summary.get("completion_facts", ()))
        additional_completed = tuple(
            str(value) for value in summary.get("additional_completed_task_keys", ())
        )
        completed_manifest = self._transition_manifest(
            manifest,
            task_key=task.task_key,
            status=TaskStatus.COMPLETED,
            classification=CompletionClassification.COMPLETE,
            completion_fact=completion_fact,
            completion_facts=extra_facts,
            additional_completed_task_keys=additional_completed,
        )
        completed_import = self.repository.import_manifest(
            control_plane_key=self.control_plane_key,
            payload=completed_manifest,
            source="research-evidence-supervisor-completed",
        )
        final_manifest = self.repository.load_manifest(
            control_plane_key=self.control_plane_key
        )
        final_snapshot = self.repository.control_plane.resolve(final_manifest)
        status = self._build_lane_status(
            final_manifest,
            snapshot=final_snapshot,
            dispatch_performed=True,
            completed_summary=summary,
        )
        completed_at = str(event.get("recorded_at") or self.now().isoformat())
        payload = {
            "schema_version": "dehps-research-evidence-supervisor-state.v1",
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "control_plane_key": self.control_plane_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "execution_id": execution_id,
            "execution_artifact_digest": summary["execution_artifact_digest"],
            "actual_fold_count": summary["actual_fold_count"],
            "registered_artifact_count": summary["registered_artifact_count"],
            "manifest_digest": completed_import.manifest_digest,
            "snapshot_digest": final_snapshot.snapshot_digest,
            "next_ready_task": status["next_ready_task"],
            "engineering_progress_percent": status["progress"]["engineering_percent"],
            "evidence_progress_percent": status["progress"]["evidence_percent"],
            "dispatch_performed": True,
            "git_commit": git_commit,
            "heartbeat_at": completed_at,
        }
        for key in (
            "calibration_run_manifest_digest",
            "calibration_run_artifact_digest",
            "completion_artifact_digest",
            "truth_artifact_digests",
            "truth_artifact_count",
            "eligible_for_p2_5_input",
            "eligible_for_power_evidence",
            "resampling_kernel_digest",
            "resampling_run_digest",
            "resampling_completion_digest",
            "child_replicate_digests",
            "aggregate_digests",
            "replicate_count",
            "aggregate_count",
            "eligible_for_formal_inference",
            "measurement_validation_manifest_digest",
            "identifiability_preflight_manifest_digest",
            "identifiability_preflight_report_digest",
            "superseded_run_archive_digest",
            "execution_plan_digest",
            "automatic_gate_digest",
            "mde_summary_digest",
            "decision",
            "decision_fact",
            "failed_requirements",
            "scenario_count",
            "p2_6_partial_statistical_results_inspected",
            "old_p2_6_execution_resumable",
            "old_p2_6_partial_statistical_results_inspected",
            "measurement_repair_manifest_digest",
            "repaired_measurement_validation_manifest_digest",
            "development_selection_artifact_digest",
            "identifiability_confirmation_digest",
            "outer_fold_fit_count_before",
            "outer_fold_fit_count_after",
            "inner_model_selection_per_outer_fold",
            "formal_power_target_count",
            "joint_only_negative_control_count",
            "feasibility_sentinel_count",
            "replay_status",
            "bootstrap_replicate_count",
            "permutation_replicate_count",
            "negative_control_id",
            "negative_control_cell_count",
            "negative_control_replicates_per_cell",
            "negative_control_replicate_count",
            "decision_policy_mde_at_61_bits_per_issue",
            "false_positive_by_scale",
            "power_by_cell",
            "estimator_quality_by_cell",
            "marginal_static_health_design_source_contract_digest",
            "marginal_static_health_design_source_set_digest",
            "marginal_static_health_workload_digest",
            "marginal_static_health_inference_digest",
            "marginal_static_health_design_completion_digest",
            "planned_total_replicates",
            "planned_total_generated_issues",
            "planned_total_outer_evaluation_issues",
            "planned_execution_shards",
            "execution_shard_size",
            "bootstrap_replicates_per_interval",
            "primary_block_size",
            "sensitivity_block_sizes",
            "legacy_replicates",
            "legacy_outer_issue_predictions",
            "legacy_probe_fits_reused",
            "legacy_results_reused",
            "bootstrap_replicates_executed",
            "completion_index_loads",
            "runtime_migration_digests",
            "runtime_git_commits",
            "incident_recovery_digests",
            "measurement_contract_v2_digest",
            "estimand_contract_digest",
            "mechanism_role_contract_digest",
            "gate_compiler_contract_digest",
            "design_execution_id",
            "design_execution_artifact_digest",
            "measurement_contract_replay_digest",
            "gate_compiler_replay_digest",
            "design_replay_execution_id",
            "design_replay_execution_artifact_digest",
            "preflight_source_contract_digest",
            "preflight_source_set_digest",
            "branch_preflight_design_digests",
            "cross_branch_preflight_design_digest",
            "preflight_design_completion_digest",
            "preflight_execution_count",
            "preflight_result_count",
            "fixture_freeze_source_contract_digest",
            "fixture_freeze_source_set_digest",
            "preflight_design_execution_id",
            "preflight_design_execution_artifact_digest",
            "solver_fixture_contract_digest",
            "orthogonal_control_fixture_contract_digest",
            "legacy_role_resolution_fixture_contract_digest",
            "fixture_freeze_completion_digest",
            "fixture_contract_count",
            "preflight_execution_source_contract_digest",
            "preflight_execution_source_set_digest",
            "fixture_execution_id",
            "fixture_execution_artifact_digest",
            "solver_preflight_result_digest",
            "orthogonal_endpoint_result_digest",
            "legacy_role_preflight_result_digest",
            "branch_preflight_result_digests",
            "preflight_execution_completion_digest",
            "preflight_execution_status",
            "branch_preflight_statuses",
            "solver_preflight_status",
            "orthogonal_endpoint_status",
            "legacy_role_resolution_status",
            "all_branches_pass",
            "all_branches_pass_fact",
            "orthogonal_endpoint_count",
            "legacy_state_result_count",
            "monte_carlo_replicates",
            "marginal_static_source_contract_digest",
            "marginal_static_source_set_digest",
            "preflight_execution_id",
            "preflight_execution_artifact_digest",
            "marginal_branch_design_digest",
            "marginal_branch_health_digest",
            "legacy_marginal_decision_digest",
            "legacy_decision_replay_digest",
            "marginal_static_measurement_contract_digest",
            "marginal_static_contract_completion_digest",
            "branch_id",
            "estimator_id",
            "identifiability_preflight_status",
            "legacy_measurement_health",
            "legacy_repair_overridden",
            "accepted_model_artifact_digest",
            "sampled_synthetic_execution_status",
            "historical_execution_status",
            "synthetic_replicates",
            "marginal_static_fixture_source_contract_digest",
            "marginal_static_fixture_source_set_digest",
            "marginal_contract_execution_id",
            "marginal_contract_execution_artifact_digest",
            "branch_fixture_completion_digest",
            "marginal_static_fixture_digests",
            "marginal_static_fixture_bundle_digest",
            "marginal_static_fixture_completion_digest",
            "fixture_count",
            "positive_fixture_count",
            "negative_fixture_count",
            "runtime_state",
            "database_reads_during_replicate",
            "database_writes_during_replicate",
            "csv_materialized",
            "duplicate_raw_replay",
            "routine_physical_checkpoint_scan",
            "sampled_workload_status",
            "generated_issues",
            "p2_6_1_execution_id",
            "p2_6_1_execution_artifact_digest",
            "raw_replay_artifact_digest",
            "p2_7_execution_id",
            "p2_7_execution_artifact_digest",
            "gate_replay_artifact_digest",
            "binding_contract_digest",
            "marginal_decision_artifact_digest",
            "branch_decision_replay_artifact_digest",
            "measurement_health",
            "historical_evidence",
            "promotion_gate_opened",
            "production_candidate_created",
            "m4_state_changed",
            "formal_branch_runs_executed",
            "historical_outcomes_read",
            "p2_6_1_partial_statistical_results_read",
            "p2_6_3_statistical_results_read",
            "p2_6_3_task_digest",
            "production_action",
            "benchmark_plan_artifact_digest",
            "runtime_observation_artifact_digest",
            "runtime_benchmark_attempt_artifact_digest",
            "source_integrity_attestation_artifact_digest",
            "golden_source_integrity_attestation_artifact_digest",
            "runtime_executor_fingerprint_digest_before",
            "runtime_executor_fingerprint_digest_after",
            "equivalence_attestation_artifact_digest",
            "golden_reference_execution_artifact_digest",
            "golden_reference_plan_artifact_digest",
            "golden_reference_fixture_artifact_digest",
            "golden_reference_replay_artifact_digest",
            "immutable_golden_fixture_is_oracle",
            "acceleration_boundary_independent",
            "acceleration_boundary_independence_scope",
            "oracle_construction_process_isolated",
            "oracle_construction_fully_implementation_independent",
            "exact_replay_verified",
            "reference_evaluator_is_oracle",
            "exact_golden_replay_verified",
            "audited_fold_count",
            "correctness_replay_fold_count",
            "total_execution_fold_count",
            "correctness_boundary_snapshot_count",
            "frozen_reference_fold_count",
            "benchmark_attempt_id",
            "benchmark_attempt_path",
            "measured_workdir_path",
            "correctness_replay_workdir_path",
            "journal_reused",
            "fresh_workdir",
            "shared_frozen_source_modified",
            "backend_source_modified",
            "acceleration_changed_paths",
            "backend_optimization_applied",
            "statistical_semantics_modified",
            "engineering_progress_before",
            "engineering_progress_after",
            "evidence_progress_before",
            "evidence_progress_after",
            "marginal_static_historical_design_source_contract_digest",
            "marginal_static_historical_design_source_set_digest",
            "historical_dataset_boundary_digest",
            "historical_walk_forward_design_digest",
            "historical_inference_design_digest",
            "historical_design_completion_digest",
            "historical_issue_count",
            "initial_training_issue_count",
            "planned_evaluation_fold_count",
            "planned_bootstrap_replicates",
            "formal_historical_folds_executed",
            "database_queries_during_capability",
            "historical_red_outcomes_read",
            "statistical_results_read",
        ):
            if key in summary:
                payload[key] = summary[key]
        self._write_state(payload)
        self._write_lane_status(status)
        return payload

    def _record_p26_runtime_migration(
        self,
        *,
        task: Task,
        execution_id: str,
        execution_git_commit: str,
        runtime_git_commit: str,
    ) -> Mapping[str, Any]:
        report_relative = os.environ.get(
            P26_EQUIVALENT_RESUME_REPORT_ENV,
            P26_EQUIVALENT_RESUME_REPORT,
        )
        report_path = self.root_dir / report_relative
        if not report_path.is_file():
            raise MainlineSupervisorError(
                "P2.6 equivalent resume evidence report is missing"
            )
        try:
            normalized_report_path = str(report_path.relative_to(self.root_dir))
        except ValueError as exc:
            raise MainlineSupervisorError(
                "P2.6 equivalent resume evidence report must be inside the repository"
            ) from exc
        report_digest = sha256(report_path.read_bytes()).hexdigest()
        payload: dict[str, Any] = {
            "schema_version": "dehps-p2-6-runtime-migration.v1",
            "artifact_type": "measurement_validation_runtime_migration",
            "artifact_digest": "",
            "execution_id": execution_id,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "execution_git_commit": execution_git_commit,
            "runtime_git_commit": runtime_git_commit,
            "equivalence_evidence_path": normalized_report_path,
            "equivalence_evidence_sha256": report_digest,
            "compatibility_claim": (
                "byte_identical_result_artifact_and_checkpoint_replay"
            ),
            "statistical_contract_changed": False,
            "workload_changed": False,
            "parent_digests": [
                task.artifact_digest,
                report_digest,
            ],
        }
        identity = dict(payload)
        identity.pop("artifact_digest")
        payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.p2-6.runtime-migration.v1",
        )
        path = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
            / "runtime-migrations"
            / payload["artifact_digest"]
            / "migration.json"
        )
        _persist_immutable(path, payload)
        return payload

    @staticmethod
    def _validated_p26_failed_recovery_event(
        *,
        task: Task,
        events: Sequence[Mapping[str, Any]],
        token: str,
    ) -> Mapping[str, Any] | None:
        failed = [item for item in events if item.get("event_type") == "failed"]
        if not failed:
            return None
        if (
            task.task_key != P26_TASK_KEY
            or task.artifact_digest != M4_P261_FROZEN_TASK_DIGEST
            or token != P26_FAILED_RECOVERY_EVENT_DIGEST
            or len(failed) != 1
        ):
            raise MainlineSupervisorError(
                "P2.6 failed recovery authorization does not match the incident"
            )
        event = failed[0]
        record = _event_record(event)
        if (
            str(event.get("event_digest") or "") != P26_FAILED_RECOVERY_EVENT_DIGEST
            or record.execution_id != P26_FAILED_RECOVERY_EXECUTION_ID
            or record.control_plane_key != M4_CONTROL_PLANE_KEY
            or record.manifest_digest != P26_FAILED_RECOVERY_RUNNING_MANIFEST_DIGEST
            or record.task_key != P26_TASK_KEY
            or record.task_digest != M4_P261_FROZEN_TASK_DIGEST
            or record.capability != P26_LEGACY_CAPABILITY
            or record.event_type != "failed"
            or record.sequence != 1
            or _event_payload(event)
            != {
                "error": P26_FAILED_RECOVERY_ERROR,
                "git_commit": "e6dedaf9c835672a5e17007653ee6e8fe55b67d9",
            }
        ):
            raise MainlineSupervisorError(
                "P2.6 failed recovery event provenance changed"
            )
        return event

    def _record_p26_failed_recovery(
        self,
        *,
        task: Task,
        execution_id: str,
        failed_event: Mapping[str, Any],
        runtime_git_commit: str,
    ) -> Mapping[str, Any]:
        report_relative = os.environ.get(P26_FAILED_RECOVERY_REPORT_ENV, "")
        relative_report_path = Path(report_relative)
        if (
            not report_relative
            or relative_report_path.is_absolute()
            or ".." in relative_report_path.parts
        ):
            raise MainlineSupervisorError(
                "P2.6 failed recovery incident report path is invalid"
            )
        report_path = (self.root_dir / relative_report_path).resolve()
        if not report_path.is_file():
            raise MainlineSupervisorError(
                "P2.6 failed recovery incident report is missing"
            )
        try:
            normalized_report_path = str(
                report_path.relative_to(self.root_dir.resolve())
            )
        except ValueError as exc:
            raise MainlineSupervisorError(
                "P2.6 failed recovery report must be inside the repository"
            ) from exc

        measurement_manifest = load_repaired_measurement_validation_manifest(
            self.root_dir / "configs/research-os/"
            "m4-information-theory-p2-6-1-measurement-validation-v1.json"
        )
        truth_digests = tuple(
            str(item["artifact_digest"])
            for item in measurement_manifest.payload["truth_artifacts"]
        )
        truths = locate_repaired_truth_artifacts(
            self.root_dir,
            required_digests=truth_digests,
            repair_manifest_digest=MEASUREMENT_REPAIR_MANIFEST_DIGEST,
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        required_paths = (
            task_dir / "artifacts/coordinator-state.json",
            task_dir / "artifacts/checkpoint-journals",
            task_dir / "artifacts/replicates",
        )
        missing = [path for path in required_paths if not path.exists()]
        if missing:
            raise MainlineSupervisorError(
                "P2.6 failed recovery runtime preflight missing: "
                + ", ".join(str(path.relative_to(self.root_dir)) for path in missing)
            )
        coordinator = _load_object(required_paths[0])
        if (
            coordinator.get("schema_version")
            != "dehps-m4-p2-analysis-coordinator-state.v1"
            or coordinator.get("parent_execution_id") != execution_id
            or coordinator.get("measurement_validation_manifest_digest")
            != measurement_manifest.artifact_digest
            or coordinator.get("total_replicates") != 31_000
            or coordinator.get("status") != "RUNNING"
            or coordinator.get("failed_replicates") != 0
            or coordinator.get("result_selection_used") is not False
        ):
            raise MainlineSupervisorError(
                "P2.6 failed recovery coordinator identity changed"
            )
        if not any(required_paths[1].rglob("*.jsonl")) or not any(
            required_paths[2].rglob("*.json")
        ):
            raise MainlineSupervisorError(
                "P2.6 failed recovery preserved checkpoint prefix is empty"
            )
        if (task_dir / "execution.json").exists():
            raise MainlineSupervisorError(
                "P2.6 failed recovery found an unregistered completion marker"
            )

        report_digest = sha256(report_path.read_bytes()).hexdigest()
        payload: dict[str, Any] = {
            "schema_version": "dehps-p2-6-failed-execution-recovery.v1",
            "artifact_type": "measurement_validation_failed_execution_recovery",
            "artifact_digest": "",
            "control_plane_key": self.control_plane_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "execution_id": execution_id,
            "failed_event_digest": str(failed_event["event_digest"]),
            "failed_event_sequence": 1,
            "next_terminal_sequence": 2,
            "incident_class": "pre_dispatch_runtime_root_missing",
            "incident_report_path": normalized_report_path,
            "incident_report_sha256": report_digest,
            "runtime_git_commit": runtime_git_commit,
            "coordinator_state_present": True,
            "checkpoint_journal_root_present": True,
            "replicate_root_present": True,
            "checkpoint_journal_present": True,
            "replicate_artifact_present": True,
            "repaired_truth_count": len(truths),
            "task_identity_changed": False,
            "execution_identity_changed": False,
            "checkpoint_bytes_rewritten": False,
            "statistical_contract_changed": False,
            "statistical_results_read": False,
            "parent_digests": [
                task.artifact_digest,
                str(failed_event["event_digest"]),
                report_digest,
            ],
        }
        identity = dict(payload)
        identity.pop("artifact_digest")
        payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.p2-6.failed-execution-recovery.v1",
        )
        path = (
            task_dir
            / "incident-recoveries"
            / payload["artifact_digest"]
            / "recovery.json"
        )
        _persist_immutable(path, payload)
        return payload

    def replay(
        self, *, task_key: str, execution_id: str | None = None
    ) -> dict[str, Any]:
        if self.control_plane_key == PREDICTION_V2_CONTROL_PLANE_KEY or task_key in {
            M4_P29_GOLDEN_REFERENCE_TASK_KEY,
            M4_P29_RUNTIME_AUDIT_TASK_KEY,
        }:
            event, artifact, verified_registrations = _load_single_completed_execution(
                repository=self.repository,
                root_dir=self.root_dir,
                control_plane_key=self.control_plane_key,
                task_key=task_key,
            )
            resolved_execution_id = str(artifact["execution_id"])
            if execution_id is not None and execution_id != resolved_execution_id:
                raise MainlineSupervisorError(
                    f"mainline replay execution identity changed: {task_key}"
                )
            registrations = list(verified_registrations)
        else:
            events = self.repository.list_mainline_execution_events(
                control_plane_key=self.control_plane_key,
                task_key=task_key,
                execution_id=execution_id,
            )
            completed = [
                item for item in events if item.get("event_type") == "completed"
            ]
            if len(completed) != 1:
                raise MainlineSupervisorError(
                    f"mainline replay requires one completed execution: {task_key}"
                )
            event = completed[0]
            resolved_execution_id = str(event["execution_id"])
            summary = _event_payload(event)
            artifact_path = self.root_dir / str(summary["execution_artifact_path"])
            artifact = _load_object(artifact_path)
            expected = canonical_digest(
                {
                    key: value
                    for key, value in artifact.items()
                    if key != "artifact_digest"
                },
                domain="dehps.research-os.mainline-execution.v1",
            )
            if expected != artifact.get("artifact_digest"):
                raise MainlineSupervisorError(
                    "mainline execution artifact digest changed"
                )
            registrations = list(
                self.repository.list_mainline_artifacts(
                    control_plane_key=self.control_plane_key,
                    execution_id=resolved_execution_id,
                )
            )
            if len(registrations) != int(summary["registered_artifact_count"]):
                raise MainlineSupervisorError(
                    "mainline artifact registry count changed"
                )
            missing = [
                item["artifact_path"]
                for item in registrations
                if not (self.root_dir / str(item["artifact_path"])).is_file()
            ]
            if missing:
                raise MainlineSupervisorError(
                    "registered mainline artifacts are missing: " + ", ".join(missing)
                )
        summary = _event_payload(event)
        capability_replay: dict[str, Any] | None = None
        if task_key == PREDICTION_V2_REFERENCE_TASK_KEY:
            expected_children = build_reference_children(self.root_dir)
            registered_children = [
                item
                for item in registrations
                if item.get("artifact_type") != "research_os_mainline_execution"
            ]
            expected_by_digest = {
                str(item["artifact_digest"]): item for item in expected_children
            }
            if {
                str(item.get("artifact_digest") or "") for item in registered_children
            } != set(expected_by_digest):
                raise MainlineSupervisorError(
                    "Prediction v2 reference registered artifact set changed"
                )
            for registration in registered_children:
                stored = _load_object(
                    self.root_dir / str(registration["artifact_path"])
                )
                if stored != expected_by_digest[str(registration["artifact_digest"])]:
                    raise MainlineSupervisorError(
                        "Prediction v2 reference registered artifact content changed"
                    )
            capability_replay = {
                "status": "REPLAY_VERIFIED",
                "same_contract_identity": True,
                "same_fixture_identity": True,
                "same_pool_identity": True,
                "same_top100_identity": True,
                "same_pre_draw_report_identity": True,
                "same_post_draw_report_identity": True,
                "historical_evidence": "NOT_RUN",
                "promotion_gate_opened": False,
                "manual_input_assembly": False,
            }
        elif task_key == PREDICTION_V2_REPLAY_TASK_KEY:
            expected = build_reference_children(self.root_dir)
            expected_by_type = {str(item["artifact_type"]): item for item in expected}
            history, actual = build_reference_history()
            pre_replay = replay_prediction_v2_pre_draw(
                contract=expected_by_type["PredictionV2ShadowContract.v1"],
                history=history,
                expected_state=expected_by_type["PredictionV2StateArtifact.v1"],
                expected_pool=expected_by_type["PredictionV2ShadowPoolArtifact.v1"],
                expected_top100=expected_by_type["PredictionV2ShadowTop100Artifact.v1"],
                expected_report=expected_by_type["PredictionV2PreDrawReport.v1"],
            )
            post_replay = replay_prediction_v2_post_draw(
                pre_draw_report=expected_by_type["PredictionV2PreDrawReport.v1"],
                actual_issue="2026121",
                actual_red_numbers=actual,
                expected_report=expected_by_type["PredictionV2PostDrawReport.v1"],
            )
            expected_replay_by_digest = {
                str(item["artifact_digest"]): item for item in (pre_replay, post_replay)
            }
            registered_children = [
                item
                for item in registrations
                if item.get("artifact_type") != "research_os_mainline_execution"
            ]
            if {
                str(item.get("artifact_digest") or "") for item in registered_children
            } != set(expected_replay_by_digest):
                raise MainlineSupervisorError(
                    "Prediction v2 replay registered artifact set changed"
                )
            for registration in registered_children:
                stored = _load_object(
                    self.root_dir / str(registration["artifact_path"])
                )
                if (
                    stored
                    != expected_replay_by_digest[str(registration["artifact_digest"])]
                ):
                    raise MainlineSupervisorError(
                        "Prediction v2 replay attestation content changed"
                    )
            capability_replay = {
                "status": "REPLAY_VERIFIED",
                "same_pre_draw_identity": True,
                "same_post_draw_identity": True,
                "historical_evidence": "NOT_RUN",
                "promotion_gate_opened": False,
                "manual_input_assembly": False,
            }
        elif task_key == PREDICTION_V2_CUTOVER_TASK_KEY:
            task = next(
                item
                for item in self.repository.load_manifest(
                    control_plane_key=self.control_plane_key
                ).tasks
                if item.task_key == PREDICTION_V2_CUTOVER_TASK_KEY
            )
            contract = json.loads(task.metric_contract)
            try:
                reconstructed = build_live_activation_attestation(
                    root_dir=self.root_dir,
                    activation_path=str(contract["activation_path"]),
                    completion_path=str(contract["operator_completion_path"]),
                )
            except (KeyError, PredictionV2ActivationBindingError) as exc:
                raise MainlineSupervisorError(
                    "Prediction v2 activation replay inputs changed"
                ) from exc
            registered_children = [
                item
                for item in registrations
                if item.get("artifact_type") != "research_os_mainline_execution"
            ]
            if len(registered_children) != 1:
                raise MainlineSupervisorError(
                    "Prediction v2 activation replay child set changed"
                )
            registered = registered_children[0]
            stored = _load_object(self.root_dir / str(registered["artifact_path"]))
            if (
                stored != reconstructed
                or registered.get("artifact_digest") != reconstructed["artifact_digest"]
                or artifact.get("child_artifact_digests")
                != [reconstructed["artifact_digest"]]
            ):
                raise MainlineSupervisorError(
                    "Prediction v2 activation replay identity changed"
                )
            capability_replay = {
                "status": "REPLAY_VERIFIED",
                "same_activation_identity": True,
                "same_operator_completion_identity": True,
                "same_attestation_identity": True,
                "historical_evidence": "NOT_RUN",
                "promotion_gate_opened": False,
                "manual_input_assembly": False,
            }
        elif task_key == M4_P29_GOLDEN_REFERENCE_TASK_KEY:
            task = next(
                item
                for item in self.repository.load_manifest(
                    control_plane_key=self.control_plane_key
                ).tasks
                if item.task_key == M4_P29_GOLDEN_REFERENCE_TASK_KEY
            )
            with tempfile.TemporaryDirectory(
                prefix="dehps-golden-reference-replay-"
            ) as temporary:
                reconstructed = _build_golden_reference_bundle(
                    root_dir=self.root_dir,
                    work_dir=Path(temporary),
                )
            registered_source_integrity = _load_registered_type(
                root_dir=self.root_dir,
                registrations=list(registrations),
                artifact_type="SourceIntegrityAttestationArtifact",
            )
            reconstructed_source_integrity = build_source_integrity_attestation(
                root_dir=self.root_dir,
                runtime_plan=reconstructed.runtime_audit_plan,
                execution_id=resolved_execution_id,
                git_commit=str(artifact["git_commit"]),
                exact_fixture_replay_artifact_digest=str(
                    reconstructed.replay["artifact_digest"]
                ),
            )
            expected_work_counts = _golden_execution_work_counts(reconstructed)
            if (
                task.input_artifact_digests != reconstructed.expected_input_digests
                or artifact.get("input_artifact_digests")
                != list(reconstructed.expected_input_digests)
                or artifact.get("golden_reference_plan_artifact_digest")
                != reconstructed.plan["artifact_digest"]
                or artifact.get("golden_reference_fixture_artifact_digest")
                != reconstructed.fixture["artifact_digest"]
                or artifact.get("golden_reference_replay_artifact_digest")
                != reconstructed.replay["artifact_digest"]
                or artifact.get("immutable_golden_fixture_is_oracle") is not True
                or artifact.get("acceleration_boundary_independent") is not True
                or artifact.get("acceleration_boundary_independence_scope")
                != M4_P29_ACCELERATION_BOUNDARY_SCOPE
                or artifact.get("oracle_construction_process_isolated") is not False
                or artifact.get("oracle_construction_fully_implementation_independent")
                is not False
                or artifact.get("exact_replay_verified") is not True
                or artifact.get("historical_outcomes_read") is not False
                or artifact.get("p2_6_1_partial_statistical_results_read") is not False
                or artifact.get("p2_6_3_statistical_results_read") is not False
                or artifact.get("evidence_progress_before") != 0
                or artifact.get("evidence_progress_after") != 0
                or artifact.get("production_action") != "none"
                or any(
                    artifact.get(key) != value
                    for key, value in expected_work_counts.items()
                )
                or registered_source_integrity != reconstructed_source_integrity
                or artifact.get("source_integrity_attestation_artifact_digest")
                != registered_source_integrity["artifact_digest"]
            ):
                raise MainlineSupervisorError(
                    "golden reference physical replay execution changed"
                )
            _validate_golden_artifact_set(
                plan=reconstructed.plan,
                fixture=reconstructed.fixture,
                replay=reconstructed.replay,
                expected_source_inputs=reconstructed.expected_input_digests,
                expected_construction_source_identity=(
                    construction_source_integrity_identity(
                        reconstructed.runtime_audit_plan
                    )
                ),
                expected_golden_source_identity=golden_source_integrity_identity(
                    reconstructed.runtime_audit_plan
                ),
            )
            _verify_v2_registered_artifacts(
                root_dir=self.root_dir,
                registrations=list(registrations),
                expected_payloads=(
                    reconstructed.plan,
                    reconstructed.fixture,
                    reconstructed.replay,
                    reconstructed_source_integrity,
                    artifact,
                ),
            )
            capability_replay = {
                "schema_version": ("dehps-m4-p2-9-golden-reference-physical-replay.v1"),
                "status": "REPLAY_VERIFIED",
                "same_plan_identity": True,
                "same_fixture_identity": True,
                "same_full_replicate_payload": True,
                "same_full_fold_trace_payload": True,
                "same_boundary_snapshot_payload": True,
                "same_checkpoint_journal_bytes": True,
                "same_replay_attestation_identity": True,
                "immutable_golden_fixture_is_oracle": True,
                "acceleration_boundary_independent": True,
                "acceleration_boundary_independence_scope": (
                    M4_P29_ACCELERATION_BOUNDARY_SCOPE
                ),
                "oracle_construction_process_isolated": False,
                "oracle_construction_fully_implementation_independent": False,
                "historical_outcomes_read": False,
                "p2_6_1_partial_statistical_results_read": False,
                "p2_6_3_statistical_results_read": False,
                "manual_input_assembly": False,
            }
        elif task_key == M4_P29_RUNTIME_AUDIT_TASK_KEY:
            (
                golden_execution,
                _,
                golden_plan,
                golden_fixture,
                golden_replay,
                golden_source_integrity,
            ) = _load_verified_golden_parent(
                repository=self.repository,
                root_dir=self.root_dir,
                control_plane_key=self.control_plane_key,
            )
            source_plan = load_runtime_audit_plan(
                self.root_dir / RUNTIME_AUDIT_PLAN_PATH
            )
            verified_construction_source_identity = preflight_source_integrity(
                root_dir=self.root_dir,
                runtime_plan=source_plan,
            )
            if (
                construction_source_integrity_identity(source_plan)
                != verified_construction_source_identity
            ):
                raise MainlineSupervisorError(
                    "runtime audit replay source preflight changed"
                )
            try:
                compatible_golden_source_identity = require_golden_source_compatibility(
                    registered_golden_contract=golden_plan[
                        "golden_source_integrity_contract"
                    ],
                    registered_golden_identity=golden_plan[
                        "golden_source_integrity_identity"
                    ],
                    new_full_source_contract=source_plan["source_integrity_contract"],
                )
            except RuntimeError as exc:
                raise MainlineSupervisorError(
                    f"runtime audit replay golden source changed: {exc}"
                ) from exc
            (
                replay_source_plan,
                replay_manifest,
                replay_synthetic,
                replay_truths,
                _,
            ) = _golden_reference_sources(root_dir=self.root_dir)
            if replay_source_plan != source_plan:
                raise MainlineSupervisorError(
                    "runtime audit replay source plan changed"
                )
            replay_replicate = golden_full_replicate(
                manifest=replay_manifest,
                synthetic=replay_synthetic,
            )
            periodic_refit_contract = load_periodic_refit_contract(
                self.root_dir
                / "configs/research-os/m4-information-theory-p2-6-3-periodic-refit-v1.json"
            )
            with tempfile.TemporaryDirectory(
                prefix="dehps-runtime-correctness-replay-"
            ) as temporary:
                replay_correctness = _observed_reference_evaluation(
                    root_dir=self.root_dir,
                    output_dir=Path(temporary),
                    manifest=replay_manifest,
                    synthetic=replay_synthetic,
                    truths=replay_truths,
                    replicate=replay_replicate,
                    periodic_refit_contract=periodic_refit_contract,
                    capture_trace=True,
                )
            replay_boundaries = _build_observed_boundary_snapshots(
                manifest=replay_manifest,
                synthetic=replay_synthetic,
                truths=replay_truths,
            )
            replay_observed_fixture = build_golden_fixture_artifact(
                plan_digest=str(golden_plan["artifact_digest"]),
                replicate=replay_replicate,
                evaluation=replay_correctness,
                boundary_snapshots=replay_boundaries,
                parent_digests=tuple(
                    str(value) for value in golden_fixture["parent_digests"]
                ),
                executor_fingerprint_digest=str(
                    golden_plan["executor_fingerprint_digest"]
                ),
                golden_source_integrity_identity=(compatible_golden_source_identity),
            )
            replay_golden_attestation = build_exact_golden_attestation(
                plan_digest=str(golden_plan["artifact_digest"]),
                reference_payload=golden_fixture,
                observed_payload=replay_observed_fixture,
                reference_journal_bytes=str(
                    golden_fixture["checkpoint_journal_utf8"]
                ).encode("utf-8"),
                observed_journal_bytes=(replay_correctness.checkpoint_journal_bytes),
            )
            if replay_golden_attestation != golden_replay:
                raise MainlineSupervisorError(
                    "runtime audit current correctness replay changed"
                )
            benchmark_plan = build_benchmark_plan_artifact(source_plan)
            registered_plan = _load_registered_type(
                root_dir=self.root_dir,
                registrations=list(registrations),
                artifact_type="BenchmarkPlanArtifact",
            )
            observation = _load_registered_type(
                root_dir=self.root_dir,
                registrations=list(registrations),
                artifact_type="RuntimeObservationArtifact",
            )
            benchmark_attempt = _load_registered_type(
                root_dir=self.root_dir,
                registrations=list(registrations),
                artifact_type="RuntimeBenchmarkAttemptArtifact",
            )
            source_integrity = _load_registered_type(
                root_dir=self.root_dir,
                registrations=list(registrations),
                artifact_type="SourceIntegrityAttestationArtifact",
            )
            registered_equivalence = _load_registered_type(
                root_dir=self.root_dir,
                registrations=list(registrations),
                artifact_type="EquivalenceAttestationArtifact",
            )
            _validate_runtime_observation(
                observation,
                benchmark_plan=benchmark_plan,
                execution_id=resolved_execution_id,
                git_commit=str(artifact["git_commit"]),
                executor_fingerprint_digest=str(
                    golden_plan["executor_fingerprint_digest"]
                ),
                benchmark_attempt_id=str(benchmark_attempt["benchmark_attempt_id"]),
                measured_result_float64_tree_digest=str(
                    benchmark_attempt["measured_result_float64_tree_digest"]
                ),
                measured_checkpoint_journal_sha256=str(
                    benchmark_attempt["measured_checkpoint_journal_sha256"]
                ),
            )
            validate_runtime_benchmark_attempt_artifact(
                benchmark_attempt,
                benchmark_plan_digest=str(benchmark_plan["artifact_digest"]),
                observation=observation,
                execution_id=resolved_execution_id,
                git_commit=str(artifact["git_commit"]),
            )
            measured_journal_bytes = _validate_runtime_benchmark_attempt_files(
                root_dir=self.root_dir,
                control_plane_key=self.control_plane_key,
                task_key=M4_P29_RUNTIME_AUDIT_TASK_KEY,
                execution_id=resolved_execution_id,
                attempt=benchmark_attempt,
            )
            reconstructed_source_integrity = build_source_integrity_attestation(
                root_dir=self.root_dir,
                runtime_plan=source_plan,
                execution_id=resolved_execution_id,
                git_commit=str(artifact["git_commit"]),
                exact_fixture_replay_artifact_digest=str(
                    golden_replay["artifact_digest"]
                ),
                golden_reference_execution_artifact_digest=str(
                    golden_execution["artifact_digest"]
                ),
                golden_source_identity=compatible_golden_source_identity,
            )
            validate_source_integrity_attestation(
                source_integrity,
                runtime_plan=source_plan,
                execution_id=resolved_execution_id,
                git_commit=str(artifact["git_commit"]),
                exact_fixture_replay_artifact_digest=str(
                    golden_replay["artifact_digest"]
                ),
                golden_reference_execution_artifact_digest=str(
                    golden_execution["artifact_digest"]
                ),
                golden_source_identity=compatible_golden_source_identity,
            )
            golden_result_digest = float64_tree_digest(
                golden_fixture["replicate_result"],
                domain="dehps.m4.p2-9.measured-result-float64-tree.v1",
            )
            if (
                reconstructed_source_integrity != source_integrity
                or benchmark_attempt["measured_result_float64_tree_digest"]
                != golden_result_digest
                or measured_journal_bytes
                != str(golden_fixture["checkpoint_journal_utf8"]).encode("utf-8")
            ):
                raise MainlineSupervisorError(
                    "runtime audit measured attempt physical evidence changed"
                )
            if (
                registered_plan != benchmark_plan
                or artifact.get("benchmark_plan_artifact_digest")
                != benchmark_plan["artifact_digest"]
                or artifact.get("runtime_observation_artifact_digest")
                != observation["artifact_digest"]
                or artifact.get("runtime_benchmark_attempt_artifact_digest")
                != benchmark_attempt["artifact_digest"]
                or artifact.get("source_integrity_attestation_artifact_digest")
                != source_integrity["artifact_digest"]
                or artifact.get("golden_source_integrity_attestation_artifact_digest")
                != golden_source_integrity["artifact_digest"]
                or artifact.get("runtime_executor_fingerprint_digest_before")
                != golden_plan["executor_fingerprint_digest"]
                or artifact.get("runtime_executor_fingerprint_digest_after")
                != golden_plan["executor_fingerprint_digest"]
                or artifact.get("actual_fold_count") != 61
                or artifact.get("audited_fold_count") != 61
                or artifact.get("correctness_replay_fold_count") != 61
                or artifact.get("total_execution_fold_count") != 122
                or artifact.get("correctness_boundary_snapshot_count") != 45
                or artifact.get("frozen_reference_fold_count") != 61
                or artifact.get("benchmark_attempt_id")
                != benchmark_attempt["benchmark_attempt_id"]
                or artifact.get("benchmark_attempt_path")
                != benchmark_attempt["benchmark_attempt_path"]
                or artifact.get("measured_workdir_path")
                != benchmark_attempt["measured_workdir_path"]
                or artifact.get("correctness_replay_workdir_path")
                != benchmark_attempt["correctness_replay_workdir_path"]
                or artifact.get("journal_reused") is not False
                or artifact.get("fresh_workdir") is not True
            ):
                raise MainlineSupervisorError(
                    "runtime audit registered observation contract changed"
                )
            reconstructed_equivalence = _build_runtime_golden_equivalence(
                benchmark_plan=benchmark_plan,
                golden_execution=golden_execution,
                golden_plan=golden_plan,
                golden_fixture=golden_fixture,
                golden_replay=golden_replay,
                observed_fixture=replay_observed_fixture,
                audited_payload=dict(benchmark_attempt["measured_result_payload"]),
                benchmark_attempt=benchmark_attempt,
                source_integrity=source_integrity,
                golden_source_integrity=golden_source_integrity,
            )
            if reconstructed_equivalence != registered_equivalence:
                raise MainlineSupervisorError(
                    "runtime audit golden equivalence replay changed"
                )
            _verify_v2_registered_artifacts(
                root_dir=self.root_dir,
                registrations=list(registrations),
                expected_payloads=(
                    benchmark_plan,
                    observation,
                    benchmark_attempt,
                    reconstructed_equivalence,
                    source_integrity,
                    artifact,
                ),
            )
            if (
                artifact.get("golden_reference_execution_artifact_digest")
                != golden_execution["artifact_digest"]
                or artifact.get("golden_reference_plan_artifact_digest")
                != golden_plan["artifact_digest"]
                or artifact.get("golden_reference_fixture_artifact_digest")
                != golden_fixture["artifact_digest"]
                or artifact.get("golden_reference_replay_artifact_digest")
                != golden_replay["artifact_digest"]
                or artifact.get("golden_source_integrity_attestation_artifact_digest")
                != golden_source_integrity["artifact_digest"]
                or artifact.get("equivalence_attestation_artifact_digest")
                != reconstructed_equivalence["artifact_digest"]
                or artifact.get("shared_frozen_source_modified") is not False
                or artifact.get("backend_source_modified")
                is not source_integrity["backend_source_modified"]
                or artifact.get("acceleration_changed_paths")
                != source_integrity["acceleration_changed_paths"]
                or artifact.get("backend_optimization_applied") is not False
                or artifact.get("statistical_semantics_modified") is not False
                or artifact.get("reference_evaluator_is_oracle") is not False
                or artifact.get("immutable_golden_fixture_is_oracle") is not True
                or artifact.get("acceleration_boundary_independent") is not True
                or artifact.get("acceleration_boundary_independence_scope")
                != M4_P29_ACCELERATION_BOUNDARY_SCOPE
                or artifact.get("oracle_construction_process_isolated") is not False
                or artifact.get("oracle_construction_fully_implementation_independent")
                is not False
                or artifact.get("exact_golden_replay_verified") is not True
            ):
                raise MainlineSupervisorError(
                    "runtime audit execution golden lineage changed"
                )
            capability_replay = {
                "schema_version": ("dehps-m4-p2-9-runtime-audit-physical-replay.v1"),
                "status": "REPLAY_VERIFIED",
                "same_registered_golden_parent_content": True,
                "current_correctness_replay_matches_registered_golden": True,
                "acceleration_boundary_independence_scope": (
                    M4_P29_ACCELERATION_BOUNDARY_SCOPE
                ),
                "oracle_construction_process_isolated": False,
                "same_benchmark_plan_identity": True,
                "same_runtime_benchmark_attempt_identity": True,
                "same_source_integrity_attestation_identity": True,
                "same_equivalence_attestation_identity": True,
                "measured_attempt_physical_evidence_verified": True,
                "runtime_observation_identity_verified": True,
                "timing_values_equal_required": False,
                "historical_outcomes_read": False,
                "p2_6_1_partial_statistical_results_read": False,
                "p2_6_3_statistical_results_read": False,
                "manual_input_assembly": False,
            }
        elif task_key == P263_SLOT_ELIGIBILITY_TASK_KEY:
            registered_children = [
                item
                for item in registrations
                if item.get("artifact_type") != "research_os_mainline_execution"
            ]
            if len(registered_children) != 1:
                raise MainlineSupervisorError(
                    "P2.6.3 slot eligibility registered child set changed"
                )
            eligibility = _load_object(
                self.root_dir / str(registered_children[0]["artifact_path"])
            )
            validate_p263_slot_eligibility_artifact(eligibility)
            current_manifest = self.repository.load_manifest(
                control_plane_key=self.control_plane_key
            )
            event_task_keys = (
                M4_P263_COMPATIBILITY_TASK_KEY,
                M4_P29_GOLDEN_REFERENCE_TASK_KEY,
                M4_P29_P263_FAILED_RUNTIME_AUDIT_TASK_KEY,
                M4_P29_RUNTIME_AUDIT_TASK_KEY,
                P263_SLOT_ELIGIBILITY_TASK_KEY,
                M4_V2_DESIGN_TASK_KEY,
                M4_V2_DESIGN_REPLAY_TASK_KEY,
                "m4-v2-branch-identifiability-preflight-design",
                "m4-p3-strict-historical-walk-forward",
            )
            event_metadata = self.repository.list_mainline_execution_event_metadata(
                control_plane_key=self.control_plane_key,
                task_keys=event_task_keys,
            )
            prerequisite_registrations = {
                str(item["execution_id"]): self.repository.list_mainline_artifacts(
                    control_plane_key=self.control_plane_key,
                    execution_id=str(item["execution_id"]),
                )
                for item in eligibility["completed_tasks"]
            }
            capability_replay = replay_p263_slot_eligibility_artifact(
                payload=eligibility,
                manifest=current_manifest,
                events=event_metadata,
                registrations_by_execution=prerequisite_registrations,
            )
            if (
                artifact.get("slot_eligibility_artifact_digest")
                != eligibility["artifact_digest"]
                or artifact.get("eligibility_basis_digest")
                != eligibility["eligibility_basis_digest"]
                or artifact.get("statistical_results_read") is not False
                or artifact.get("prediction_v2_promotion_allowed") is not False
                or artifact.get("promotion_gate_opened") is not False
            ):
                raise MainlineSupervisorError(
                    "P2.6.3 slot eligibility execution lineage changed"
                )
            _verify_v2_registered_artifacts(
                root_dir=self.root_dir,
                registrations=registrations,
                expected_payloads=(eligibility, artifact),
            )
        elif task_key == M4_V2_DESIGN_TASK_KEY:
            contract = load_measurement_contract_v2(
                self.root_dir / MEASUREMENT_CONTRACT_V2_PATH
            )
            reconstructed = build_design_artifacts(
                contract,
                execution_id=resolved_execution_id,
                git_commit=str(artifact["git_commit"]),
            )
            if (
                reconstructed.estimand_contract["artifact_digest"]
                != artifact["estimand_contract_digest"]
                or reconstructed.mechanism_role_contract["artifact_digest"]
                != artifact["mechanism_role_contract_digest"]
                or reconstructed.gate_compiler_contract["artifact_digest"]
                != artifact["gate_compiler_contract_digest"]
                or reconstructed.completion["artifact_digest"]
                != artifact["completion_artifact_digest"]
            ):
                raise MainlineSupervisorError(
                    "M4 Measurement Contract v2 deterministic replay changed"
                )
            _verify_v2_registered_artifacts(
                root_dir=self.root_dir,
                registrations=registrations,
                expected_payloads=(
                    *reconstructed.artifacts,
                    artifact,
                ),
            )
            capability_replay = {
                "schema_version": ("dehps-m4-measurement-v2-design-replay.v1"),
                "status": "REPLAY_VERIFIED",
                "measurement_contract_v2_digest": contract.artifact_digest,
                "estimand_contract_digest": reconstructed.estimand_contract[
                    "artifact_digest"
                ],
                "mechanism_role_contract_digest": (
                    reconstructed.mechanism_role_contract["artifact_digest"]
                ),
                "gate_compiler_contract_digest": (
                    reconstructed.gate_compiler_contract["artifact_digest"]
                ),
                "completion_artifact_digest": reconstructed.completion[
                    "artifact_digest"
                ],
                "formal_branch_runs_executed": 0,
                "historical_outcomes_read": False,
                "manual_input_assembly": False,
            }
        elif task_key == M4_V2_DESIGN_REPLAY_TASK_KEY:
            parent_events = self.repository.list_mainline_execution_events(
                control_plane_key=self.control_plane_key,
                task_key=M4_V2_DESIGN_TASK_KEY,
            )
            parent_completed = [
                item
                for item in parent_events
                if item.get("event_type") == "completed"
                and item.get("execution_id") == artifact.get("design_execution_id")
            ]
            if len(parent_completed) != 1:
                raise MainlineSupervisorError(
                    "M4 v2 design replay cannot resolve its design parent"
                )
            parent_summary = _event_payload(parent_completed[0])
            parent_path = self.root_dir / str(parent_summary["execution_artifact_path"])
            parent_execution = _load_object(parent_path)
            parent_registrations = list(
                self.repository.list_mainline_artifacts(
                    control_plane_key=self.control_plane_key,
                    execution_id=str(parent_execution["execution_id"]),
                )
            )
            contract = load_measurement_contract_v2(
                self.root_dir / MEASUREMENT_CONTRACT_V2_PATH
            )
            reconstructed_design = build_design_artifacts(
                contract,
                execution_id=str(parent_execution["execution_id"]),
                git_commit=str(parent_execution["git_commit"]),
            )
            _verify_v2_registered_artifacts(
                root_dir=self.root_dir,
                registrations=parent_registrations,
                expected_payloads=(
                    *reconstructed_design.artifacts,
                    parent_execution,
                ),
            )
            fixture = load_gate_replay_fixture(self.root_dir / GATE_REPLAY_FIXTURE_PATH)
            reconstructed_replay = build_design_replay_artifacts(
                contract,
                fixture=fixture,
                design_execution=parent_execution,
                design_child_digests=[
                    str(item["artifact_digest"])
                    for item in parent_registrations
                    if item.get("artifact_type") != "research_os_mainline_execution"
                ],
                registration_payloads=parent_registrations,
            )
            if reconstructed_replay.measurement_contract_replay[
                "artifact_digest"
            ] != artifact.get(
                "measurement_contract_replay_digest"
            ) or reconstructed_replay.gate_compiler_replay[
                "artifact_digest"
            ] != artifact.get("gate_compiler_replay_digest"):
                raise MainlineSupervisorError(
                    "M4 Measurement Contract v2 replay attestation changed"
                )
            _verify_v2_registered_artifacts(
                root_dir=self.root_dir,
                registrations=registrations,
                expected_payloads=(*reconstructed_replay.artifacts, artifact),
            )
            capability_replay = {
                "schema_version": (
                    "dehps-m4-measurement-v2-design-replay-attestation.v1"
                ),
                "status": "REPLAY_VERIFIED",
                "design_execution_id": parent_execution["execution_id"],
                "measurement_contract_replay_digest": (
                    reconstructed_replay.measurement_contract_replay["artifact_digest"]
                ),
                "gate_compiler_replay_digest": (
                    reconstructed_replay.gate_compiler_replay["artifact_digest"]
                ),
                "same_registered_content": True,
                "same_gate_fixture_output": True,
                "formal_branch_runs_executed": 0,
                "historical_outcomes_read": False,
                "manual_input_assembly": False,
            }
        elif task_key == PREFLIGHT_DESIGN_TASK_KEY:
            source_contract = load_preflight_source_contract(
                self.root_dir / PREFLIGHT_SOURCE_CONTRACT_PATH
            )
            verify_preflight_source_bytes(
                root_dir=self.root_dir,
                contract=source_contract,
            )
            _, design_execution, _ = _load_single_completed_execution(
                repository=self.repository,
                root_dir=self.root_dir,
                control_plane_key=self.control_plane_key,
                task_key=M4_V2_DESIGN_TASK_KEY,
            )
            _, design_replay_execution, design_replay_registrations = (
                _load_single_completed_execution(
                    repository=self.repository,
                    root_dir=self.root_dir,
                    control_plane_key=self.control_plane_key,
                    task_key=M4_V2_DESIGN_REPLAY_TASK_KEY,
                )
            )
            gate_replay = _load_registered_type(
                root_dir=self.root_dir,
                registrations=design_replay_registrations,
                artifact_type="GateCompilerReplayArtifact",
            )
            contract = load_measurement_contract_v2(
                self.root_dir / MEASUREMENT_CONTRACT_V2_PATH
            )
            reconstructed = build_branch_preflight_design_artifacts(
                contract,
                design_execution_artifact_digest=str(
                    design_execution["artifact_digest"]
                ),
                design_replay_execution_artifact_digest=str(
                    design_replay_execution["artifact_digest"]
                ),
                gate_compiler_replay_digest=str(gate_replay["artifact_digest"]),
                execution_id=resolved_execution_id,
                git_commit=str(artifact["git_commit"]),
            )
            if (
                artifact.get("preflight_source_contract_digest")
                != source_contract["artifact_digest"]
                or artifact.get("preflight_source_set_digest")
                != source_contract["source_set_digest"]
                or artifact.get("design_execution_artifact_digest")
                != design_execution["artifact_digest"]
                or artifact.get("design_replay_execution_artifact_digest")
                != design_replay_execution["artifact_digest"]
                or artifact.get("branch_preflight_design_digests")
                != [item["artifact_digest"] for item in reconstructed.branch_contracts]
                or artifact.get("cross_branch_preflight_design_digest")
                != reconstructed.cross_branch_contract["artifact_digest"]
                or artifact.get("preflight_design_completion_digest")
                != reconstructed.completion["artifact_digest"]
                or artifact.get("formal_branch_runs_executed") != 0
                or artifact.get("preflight_result_count") != 0
                or artifact.get("historical_outcomes_read") is not False
                or artifact.get("p2_6_3_statistical_results_read") is not False
                or artifact.get("evidence_created") is not False
            ):
                raise MainlineSupervisorError(
                    "M4 v2 branch preflight design replay identity changed"
                )
            _verify_v2_registered_artifacts(
                root_dir=self.root_dir,
                registrations=registrations,
                expected_payloads=(*reconstructed.artifacts, artifact),
            )
            capability_replay = {
                "schema_version": ("dehps-m4-v2-branch-preflight-design-replay.v1"),
                "status": "REPLAY_VERIFIED",
                "branch_design_count": len(reconstructed.branch_contracts),
                "cross_branch_preflight_design_digest": (
                    reconstructed.cross_branch_contract["artifact_digest"]
                ),
                "preflight_design_completion_digest": reconstructed.completion[
                    "artifact_digest"
                ],
                "same_registered_content": True,
                "formal_branch_runs_executed": 0,
                "preflight_result_count": 0,
                "historical_outcomes_read": False,
                "statistical_results_read": False,
                "evidence_created": False,
                "manual_input_assembly": False,
            }
        elif task_key == FIXTURE_FREEZE_TASK_KEY:
            source_contract = load_fixture_freeze_source_contract(
                self.root_dir / FIXTURE_FREEZE_SOURCE_CONTRACT_PATH
            )
            verify_fixture_freeze_source_bytes(
                root_dir=self.root_dir,
                contract=source_contract,
            )
            _, preflight_execution, preflight_registrations = (
                _load_single_completed_execution(
                    repository=self.repository,
                    root_dir=self.root_dir,
                    control_plane_key=self.control_plane_key,
                    task_key=PREFLIGHT_DESIGN_TASK_KEY,
                )
            )
            preflight_completion = _load_registered_type(
                root_dir=self.root_dir,
                registrations=preflight_registrations,
                artifact_type="m4_v2_branch_preflight_design_completion",
            )
            cross_branch = _load_registered_type(
                root_dir=self.root_dir,
                registrations=preflight_registrations,
                artifact_type="m4_v2_cross_branch_preflight_design",
            )
            reconstructed = build_fixture_freeze_artifacts(
                source_contract=source_contract,
                preflight_design_execution_artifact_digest=str(
                    preflight_execution["artifact_digest"]
                ),
                preflight_design_completion_digest=str(
                    preflight_completion["artifact_digest"]
                ),
                cross_branch_preflight_design_digest=str(
                    cross_branch["artifact_digest"]
                ),
                execution_id=resolved_execution_id,
                git_commit=str(artifact["git_commit"]),
            )
            if (
                artifact.get("fixture_freeze_source_contract_digest")
                != source_contract["artifact_digest"]
                or artifact.get("fixture_freeze_source_set_digest")
                != source_contract["source_set_digest"]
                or artifact.get("preflight_design_execution_artifact_digest")
                != preflight_execution["artifact_digest"]
                or artifact.get("preflight_design_completion_digest")
                != preflight_completion["artifact_digest"]
                or artifact.get("cross_branch_preflight_design_digest")
                != cross_branch["artifact_digest"]
                or artifact.get("solver_fixture_contract_digest")
                != reconstructed.solver_contract["artifact_digest"]
                or artifact.get("orthogonal_control_fixture_contract_digest")
                != reconstructed.orthogonal_control_contract["artifact_digest"]
                or artifact.get("legacy_role_resolution_fixture_contract_digest")
                != reconstructed.legacy_role_resolution_contract["artifact_digest"]
                or artifact.get("fixture_freeze_completion_digest")
                != reconstructed.completion["artifact_digest"]
                or artifact.get("fixture_contract_count") != 3
                or artifact.get("formal_branch_runs_executed") != 0
                or artifact.get("preflight_result_count") != 0
                or artifact.get("historical_outcomes_read") is not False
                or artifact.get("p2_6_3_statistical_results_read") is not False
                or artifact.get("evidence_created") is not False
            ):
                raise MainlineSupervisorError(
                    "M4 v2 branch fixture freeze replay identity changed"
                )
            _verify_v2_registered_artifacts(
                root_dir=self.root_dir,
                registrations=registrations,
                expected_payloads=(*reconstructed.artifacts, artifact),
            )
            capability_replay = {
                "schema_version": ("dehps-m4-v2-branch-fixture-freeze-replay.v1"),
                "status": "REPLAY_VERIFIED",
                "fixture_contract_count": 3,
                "solver_fixture_contract_digest": reconstructed.solver_contract[
                    "artifact_digest"
                ],
                "orthogonal_control_fixture_contract_digest": (
                    reconstructed.orthogonal_control_contract["artifact_digest"]
                ),
                "legacy_role_resolution_fixture_contract_digest": (
                    reconstructed.legacy_role_resolution_contract["artifact_digest"]
                ),
                "fixture_freeze_completion_digest": reconstructed.completion[
                    "artifact_digest"
                ],
                "same_registered_content": True,
                "formal_branch_runs_executed": 0,
                "preflight_result_count": 0,
                "historical_outcomes_read": False,
                "statistical_results_read": False,
                "evidence_created": False,
                "manual_input_assembly": False,
            }
        elif task_key == PREFLIGHT_EXECUTION_TASK_KEY:
            source_contract = load_preflight_execution_source_contract(
                self.root_dir / PREFLIGHT_EXECUTION_SOURCE_CONTRACT_PATH
            )
            verify_preflight_execution_source_bytes(
                root_dir=self.root_dir,
                contract=source_contract,
            )
            _, fixture_execution, fixture_registrations = (
                _load_single_completed_execution(
                    repository=self.repository,
                    root_dir=self.root_dir,
                    control_plane_key=self.control_plane_key,
                    task_key=FIXTURE_FREEZE_TASK_KEY,
                )
            )
            solver_fixture = _load_registered_type(
                root_dir=self.root_dir,
                registrations=fixture_registrations,
                artifact_type="m4_v2_joint_maxent_fixture_contract",
            )
            orthogonal_fixture = _load_registered_type(
                root_dir=self.root_dir,
                registrations=fixture_registrations,
                artifact_type="m4_v2_orthogonal_control_fixture_contract",
            )
            legacy_fixture = _load_registered_type(
                root_dir=self.root_dir,
                registrations=fixture_registrations,
                artifact_type="m4_v2_legacy_role_resolution_fixture_contract",
            )
            fixture_completion = _load_registered_type(
                root_dir=self.root_dir,
                registrations=fixture_registrations,
                artifact_type="m4_v2_branch_fixture_freeze_completion",
            )
            _, _, design_registrations = _load_single_completed_execution(
                repository=self.repository,
                root_dir=self.root_dir,
                control_plane_key=self.control_plane_key,
                task_key=PREFLIGHT_DESIGN_TASK_KEY,
            )
            branch_designs = tuple(
                sorted(
                    _load_registered_type_group(
                        root_dir=self.root_dir,
                        registrations=design_registrations,
                        artifact_type=("m4_v2_branch_identifiability_preflight_design"),
                    ),
                    key=lambda item: int(item["branch_order_index"]),
                )
            )
            cross_branch_design = _load_registered_type(
                root_dir=self.root_dir,
                registrations=design_registrations,
                artifact_type="m4_v2_cross_branch_preflight_design",
            )
            reconstructed = build_preflight_execution_artifacts(
                source_contract=source_contract,
                fixture_execution_artifact_digest=str(
                    fixture_execution["artifact_digest"]
                ),
                solver_fixture=solver_fixture,
                orthogonal_fixture=orthogonal_fixture,
                legacy_fixture=legacy_fixture,
                fixture_completion=fixture_completion,
                branch_designs=branch_designs,
                cross_branch_design=cross_branch_design,
                execution_id=resolved_execution_id,
                git_commit=str(artifact["git_commit"]),
            )
            branch_statuses = {
                str(item["branch_id"]): str(item["status"])
                for item in reconstructed.branch_results
            }
            if (
                artifact.get("preflight_execution_source_contract_digest")
                != source_contract["artifact_digest"]
                or artifact.get("preflight_execution_source_set_digest")
                != source_contract["source_set_digest"]
                or artifact.get("fixture_execution_artifact_digest")
                != fixture_execution["artifact_digest"]
                or artifact.get("solver_fixture_contract_digest")
                != solver_fixture["artifact_digest"]
                or artifact.get("orthogonal_control_fixture_contract_digest")
                != orthogonal_fixture["artifact_digest"]
                or artifact.get("legacy_role_resolution_fixture_contract_digest")
                != legacy_fixture["artifact_digest"]
                or artifact.get("fixture_freeze_completion_digest")
                != fixture_completion["artifact_digest"]
                or artifact.get("branch_preflight_design_digests")
                != [item["artifact_digest"] for item in branch_designs]
                or artifact.get("cross_branch_preflight_design_digest")
                != cross_branch_design["artifact_digest"]
                or artifact.get("solver_preflight_result_digest")
                != reconstructed.solver_result["artifact_digest"]
                or artifact.get("orthogonal_endpoint_result_digest")
                != reconstructed.orthogonal_result["artifact_digest"]
                or artifact.get("legacy_role_preflight_result_digest")
                != reconstructed.legacy_result["artifact_digest"]
                or artifact.get("branch_preflight_result_digests")
                != [item["artifact_digest"] for item in reconstructed.branch_results]
                or artifact.get("preflight_execution_completion_digest")
                != reconstructed.completion["artifact_digest"]
                or artifact.get("preflight_execution_status")
                != reconstructed.completion["preflight_status"]
                or artifact.get("branch_preflight_statuses") != branch_statuses
                or artifact.get("solver_preflight_status")
                != reconstructed.solver_result["status"]
                or artifact.get("orthogonal_endpoint_status")
                != reconstructed.orthogonal_result["status"]
                or artifact.get("legacy_role_resolution_status")
                != reconstructed.legacy_result["status"]
                or artifact.get("all_branches_pass")
                is not reconstructed.all_branches_pass
                or artifact.get("all_branches_pass_fact")
                != (
                    PREFLIGHT_EXECUTION_PASS_FACT
                    if reconstructed.all_branches_pass
                    else None
                )
                or artifact.get("formal_branch_runs_executed") != 0
                or artifact.get("preflight_result_count") != 3
                or artifact.get("monte_carlo_replicates") != 0
                or artifact.get("historical_outcomes_read") is not False
                or artifact.get("p2_6_3_statistical_results_read") is not False
                or artifact.get("evidence_created") is not False
            ):
                raise MainlineSupervisorError(
                    "M4 v2 branch preflight execution replay identity changed"
                )
            _verify_v2_registered_artifacts(
                root_dir=self.root_dir,
                registrations=registrations,
                expected_payloads=(*reconstructed.artifacts, artifact),
            )
            capability_replay = {
                "schema_version": ("dehps-m4-v2-branch-preflight-execution-replay.v1"),
                "status": "REPLAY_VERIFIED",
                "preflight_execution_status": reconstructed.completion[
                    "preflight_status"
                ],
                "all_branches_pass": reconstructed.all_branches_pass,
                "branch_preflight_statuses": branch_statuses,
                "solver_preflight_status": reconstructed.solver_result["status"],
                "orthogonal_endpoint_status": reconstructed.orthogonal_result["status"],
                "legacy_role_resolution_status": reconstructed.legacy_result["status"],
                "preflight_execution_completion_digest": (
                    reconstructed.completion["artifact_digest"]
                ),
                "same_registered_content": True,
                "formal_branch_runs_executed": 0,
                "preflight_result_count": 3,
                "monte_carlo_replicates": 0,
                "historical_outcomes_read": False,
                "statistical_results_read": False,
                "evidence_created": False,
                "manual_input_assembly": False,
            }
        elif task_key == MARGINAL_STATIC_FIXTURE_FREEZE_TASK_KEY:
            source_contract = load_marginal_static_fixture_source_contract(
                self.root_dir / MARGINAL_STATIC_FIXTURE_SOURCE_CONTRACT_PATH
            )
            verify_marginal_static_fixture_source_bytes(
                root_dir=self.root_dir,
                contract=source_contract,
            )
            _, marginal_execution, marginal_registrations = (
                _load_single_completed_execution(
                    repository=self.repository,
                    root_dir=self.root_dir,
                    control_plane_key=self.control_plane_key,
                    task_key=MARGINAL_STATIC_CONTRACT_FREEZE_TASK_KEY,
                )
            )
            marginal_contract = _load_registered_type(
                root_dir=self.root_dir,
                registrations=marginal_registrations,
                artifact_type="m4_v2_marginal_static_measurement_contract",
            )
            marginal_completion = _load_registered_type(
                root_dir=self.root_dir,
                registrations=marginal_registrations,
                artifact_type=("m4_v2_marginal_static_contract_freeze_completion"),
            )
            _, _, fixture_registrations = _load_single_completed_execution(
                repository=self.repository,
                root_dir=self.root_dir,
                control_plane_key=self.control_plane_key,
                task_key=FIXTURE_FREEZE_TASK_KEY,
            )
            orthogonal_fixture = _load_registered_type(
                root_dir=self.root_dir,
                registrations=fixture_registrations,
                artifact_type="m4_v2_orthogonal_control_fixture_contract",
            )
            fixture_completion = _load_registered_type(
                root_dir=self.root_dir,
                registrations=fixture_registrations,
                artifact_type="m4_v2_branch_fixture_freeze_completion",
            )
            _, _, preflight_registrations = _load_single_completed_execution(
                repository=self.repository,
                root_dir=self.root_dir,
                control_plane_key=self.control_plane_key,
                task_key=PREFLIGHT_EXECUTION_TASK_KEY,
            )
            marginal_health = next(
                item
                for item in _load_registered_type_group(
                    root_dir=self.root_dir,
                    registrations=preflight_registrations,
                    artifact_type="m4_v2_branch_health_preflight_result",
                )
                if item.get("branch_id") == "MARGINAL_STATIC"
            )
            preflight_completion = _load_registered_type(
                root_dir=self.root_dir,
                registrations=preflight_registrations,
                artifact_type="m4_v2_branch_preflight_execution_completion",
            )
            reconstructed = build_marginal_static_fixture_artifacts(
                source_contract=source_contract,
                marginal_contract_execution_artifact_digest=str(
                    marginal_execution["artifact_digest"]
                ),
                marginal_measurement_contract=marginal_contract,
                marginal_contract_completion=marginal_completion,
                orthogonal_fixture_contract=orthogonal_fixture,
                branch_fixture_completion=fixture_completion,
                marginal_branch_health=marginal_health,
                preflight_completion=preflight_completion,
                execution_id=resolved_execution_id,
                git_commit=str(artifact["git_commit"]),
            )
            fixture_digests = [
                item["artifact_digest"] for item in reconstructed.fixtures
            ]
            if (
                artifact.get("marginal_static_fixture_source_contract_digest")
                != source_contract["artifact_digest"]
                or artifact.get("marginal_static_fixture_source_set_digest")
                != source_contract["source_set_digest"]
                or artifact.get("marginal_contract_execution_artifact_digest")
                != marginal_execution["artifact_digest"]
                or artifact.get("marginal_static_measurement_contract_digest")
                != marginal_contract["artifact_digest"]
                or artifact.get("marginal_static_contract_completion_digest")
                != marginal_completion["artifact_digest"]
                or artifact.get("orthogonal_fixture_contract_digest")
                != orthogonal_fixture["artifact_digest"]
                or artifact.get("branch_fixture_completion_digest")
                != fixture_completion["artifact_digest"]
                or artifact.get("marginal_branch_health_digest")
                != marginal_health["artifact_digest"]
                or artifact.get("preflight_execution_completion_digest")
                != preflight_completion["artifact_digest"]
                or artifact.get("marginal_static_fixture_digests") != fixture_digests
                or artifact.get("marginal_static_fixture_bundle_digest")
                != reconstructed.bundle["artifact_digest"]
                or artifact.get("marginal_static_fixture_completion_digest")
                != reconstructed.completion["artifact_digest"]
                or artifact.get("fixture_count") != 4
                or artifact.get("positive_fixture_count") != 1
                or artifact.get("negative_fixture_count") != 3
                or artifact.get("database_reads_during_replicate") != 0
                or artifact.get("database_writes_during_replicate") != 0
                or artifact.get("csv_materialized") is not False
                or artifact.get("duplicate_raw_replay") is not False
                or artifact.get("routine_physical_checkpoint_scan") is not False
                or artifact.get("sampled_workload_status") != "NOT_FROZEN"
                or artifact.get("generated_issues") != 0
                or artifact.get("synthetic_replicates") != 0
                or artifact.get("historical_outcomes_read") is not False
                or artifact.get("p2_6_3_statistical_results_read") is not False
                or artifact.get("evidence_created") is not False
            ):
                raise MainlineSupervisorError(
                    "M4 v2 marginal-static fixture replay identity changed"
                )
            _verify_v2_registered_artifacts(
                root_dir=self.root_dir,
                registrations=registrations,
                expected_payloads=(*reconstructed.artifacts, artifact),
            )
            capability_replay = {
                "schema_version": (
                    "dehps-m4-v2-marginal-static-fixture-freeze-replay.v1"
                ),
                "status": "REPLAY_VERIFIED",
                "fixture_digests": fixture_digests,
                "fixture_bundle_digest": reconstructed.bundle["artifact_digest"],
                "fixture_completion_digest": reconstructed.completion[
                    "artifact_digest"
                ],
                "fixture_count": 4,
                "positive_fixture_count": 1,
                "negative_fixture_count": 3,
                "runtime_state": (
                    "issue_count plus ordered signed_int64[33] number-event counts"
                ),
                "database_reads_during_replicate": 0,
                "database_writes_during_replicate": 0,
                "csv_materialized": False,
                "duplicate_raw_replay": False,
                "routine_physical_checkpoint_scan": False,
                "sampled_workload_status": "NOT_FROZEN",
                "same_registered_content": True,
                "generated_issues": 0,
                "synthetic_replicates": 0,
                "historical_outcomes_read": False,
                "statistical_results_read": False,
                "evidence_created": False,
                "manual_input_assembly": False,
            }
        elif task_key == MARGINAL_STATIC_REPAIR_DESIGN_TASK_KEY:
            source_contract = load_marginal_static_repair_design_source_contract(
                self.root_dir / MARGINAL_STATIC_REPAIR_DESIGN_SOURCE_CONTRACT_PATH
            )
            verify_marginal_static_repair_design_source_bytes(
                root_dir=self.root_dir,
                contract=source_contract,
            )
            _, decision_execution, decision_registrations = (
                _load_single_completed_execution(
                    repository=self.repository,
                    root_dir=self.root_dir,
                    control_plane_key=self.control_plane_key,
                    task_key=MARGINAL_STATIC_HEALTH_DECISION_TASK_KEY,
                )
            )
            decision = _load_registered_type(
                root_dir=self.root_dir,
                registrations=decision_registrations,
                artifact_type="m4_v2_marginal_static_measurement_health_decision",
            )
            registered_feasibility = _load_registered_type(
                root_dir=self.root_dir,
                registrations=registrations,
                artifact_type=("m4_v2_marginal_static_repair_analytic_feasibility"),
            )
            registered_design = _load_registered_type(
                root_dir=self.root_dir,
                registrations=registrations,
                artifact_type="m4_v2_marginal_static_measurement_repair_design",
            )
            registered_completion = _load_registered_type(
                root_dir=self.root_dir,
                registrations=registrations,
                artifact_type="m4_v2_marginal_static_repair_design_completion",
            )
            reconstructed = build_marginal_static_repair_design_artifacts(
                source_contract=source_contract,
                health_decision_execution=decision_execution,
                health_decision=decision,
                execution_id=resolved_execution_id,
                git_commit=str(artifact["git_commit"]),
            )
            if (
                registered_feasibility != reconstructed.feasibility
                or registered_design != reconstructed.repair_design
                or registered_completion != reconstructed.completion
                or artifact.get("marginal_static_repair_design_source_contract_digest")
                != source_contract["artifact_digest"]
                or artifact.get("marginal_static_repair_design_source_set_digest")
                != source_contract["source_set_digest"]
                or artifact.get("health_decision_execution_artifact_digest")
                != decision_execution["artifact_digest"]
                or artifact.get("health_decision_artifact_digest")
                != decision["artifact_digest"]
                or artifact.get("marginal_static_repair_analytic_feasibility_digest")
                != reconstructed.feasibility["artifact_digest"]
                or artifact.get("marginal_static_repair_design_artifact_digest")
                != reconstructed.repair_design["artifact_digest"]
                or artifact.get("marginal_static_repair_design_completion_digest")
                != reconstructed.completion["artifact_digest"]
                or artifact.get("old_measurement_health") != "REPAIR"
                or artifact.get("old_decision_preserved") != "REPAIR_MEASUREMENT_SYSTEM"
                or artifact.get("measurement_health") != "REPAIR"
                or artifact.get("decision") != "REPAIR_MEASUREMENT_SYSTEM"
                or artifact.get("decision_fact")
                != MARGINAL_STATIC_HEALTH_DECISION_REPAIR_FACT
                or artifact.get("eligible_for_historical_measurement") is not False
                or artifact.get("failed_cell_count") != 4
                or artifact.get("forward_61_gate_admissible")
                != {"0.010": False, "0.050": False}
                or artifact.get("round_42_seed_reuse") is not False
                or artifact.get("automatic_pass_from_reanalysis") is not False
                or artifact.get("same_seed_tuning") != "forbidden"
                or artifact.get("posthoc_threshold_change") != "forbidden"
                or artifact.get("generated_issues") != 0
                or artifact.get("synthetic_replicates") != 0
                or artifact.get("checkpoint_reads") != 0
                or artifact.get("compact_index_reads") != 0
                or artifact.get("sentinel_replicates_recomputed") != 0
                or artifact.get("duplicate_validation") is not False
                or artifact.get("historical_outcomes_read") is not False
                or artifact.get("statistical_results_read") is not True
                or artifact.get("evidence_created") is not False
                or artifact.get("promotion_gate_opened") is not False
                or artifact.get("downstream_consumer")
                != MARGINAL_STATIC_REPAIR_PREREGISTRATION_TASK_KEY
                or artifact.get("production_action") != "none"
            ):
                raise MainlineSupervisorError(
                    "M4 v2 marginal-static repair-design replay identity changed"
                )
            _verify_v2_registered_artifacts(
                root_dir=self.root_dir,
                registrations=registrations,
                expected_payloads=(*reconstructed.artifacts, artifact),
            )
            capability_replay = {
                "schema_version": (
                    "dehps-m4-v2-marginal-static-repair-design-replay.v1"
                ),
                "status": "REPLAY_VERIFIED",
                "analytic_feasibility_digest": reconstructed.feasibility[
                    "artifact_digest"
                ],
                "repair_design_digest": reconstructed.repair_design["artifact_digest"],
                "completion_digest": reconstructed.completion["artifact_digest"],
                "same_registered_content": True,
                "design_only": True,
                "generated_issues_during_replay": 0,
                "synthetic_replicates_during_replay": 0,
                "checkpoint_reads": 0,
                "compact_index_reads": 0,
                "sentinel_replicates_recomputed": 0,
                "duplicate_validation": False,
                "historical_outcomes_read": False,
                "statistical_results_read": True,
                "evidence_created": False,
                "manual_input_assembly": False,
            }
        elif task_key == MARGINAL_STATIC_REPAIR_PREREGISTRATION_TASK_KEY:
            source_contract = (
                load_marginal_static_repair_preregistration_source_contract(
                    self.root_dir
                    / MARGINAL_STATIC_REPAIR_PREREGISTRATION_SOURCE_CONTRACT_PATH
                )
            )
            verify_marginal_static_repair_preregistration_source_bytes(
                root_dir=self.root_dir,
                contract=source_contract,
            )
            _, repair_execution, repair_registrations = (
                _load_single_completed_execution(
                    repository=self.repository,
                    root_dir=self.root_dir,
                    control_plane_key=self.control_plane_key,
                    task_key=MARGINAL_STATIC_REPAIR_DESIGN_TASK_KEY,
                )
            )
            feasibility = _load_registered_type(
                root_dir=self.root_dir,
                registrations=repair_registrations,
                artifact_type=("m4_v2_marginal_static_repair_analytic_feasibility"),
            )
            repair_design = _load_registered_type(
                root_dir=self.root_dir,
                registrations=repair_registrations,
                artifact_type=("m4_v2_marginal_static_measurement_repair_design"),
            )
            repair_completion = _load_registered_type(
                root_dir=self.root_dir,
                registrations=repair_registrations,
                artifact_type=("m4_v2_marginal_static_repair_design_completion"),
            )
            registered_workload = _load_registered_type(
                root_dir=self.root_dir,
                registrations=registrations,
                artifact_type=("m4_v2_marginal_static_repair_health_workload_seeds"),
            )
            registered_inference = _load_registered_type(
                root_dir=self.root_dir,
                registrations=registrations,
                artifact_type=("m4_v2_marginal_static_repair_health_inference_gates"),
            )
            registered_preregistration = _load_registered_type(
                root_dir=self.root_dir,
                registrations=registrations,
                artifact_type=("m4_v2_marginal_static_repair_health_preregistration"),
            )
            registered_completion = _load_registered_type(
                root_dir=self.root_dir,
                registrations=registrations,
                artifact_type=(
                    "m4_v2_marginal_static_repair_health_preregistration_completion"
                ),
            )
            reconstructed = build_marginal_static_repair_preregistration_artifacts(
                source_contract=source_contract,
                repair_design_execution=repair_execution,
                analytic_feasibility=feasibility,
                repair_design=repair_design,
                repair_design_completion=repair_completion,
                execution_id=resolved_execution_id,
                git_commit=str(artifact["git_commit"]),
            )
            if (
                registered_workload != reconstructed.workload_and_seeds
                or registered_inference != reconstructed.inference_and_gates
                or registered_preregistration != reconstructed.preregistration
                or registered_completion != reconstructed.completion
                or artifact.get(
                    "marginal_static_repair_preregistration_source_contract_digest"
                )
                != source_contract["artifact_digest"]
                or artifact.get(
                    "marginal_static_repair_preregistration_source_set_digest"
                )
                != source_contract["source_set_digest"]
                or artifact.get("repair_design_execution_artifact_digest")
                != repair_execution["artifact_digest"]
                or artifact.get("repair_analytic_feasibility_digest")
                != feasibility["artifact_digest"]
                or artifact.get("repair_design_artifact_digest")
                != repair_design["artifact_digest"]
                or artifact.get("repair_design_completion_digest")
                != repair_completion["artifact_digest"]
                or artifact.get("marginal_static_repair_health_workload_seed_digest")
                != reconstructed.workload_and_seeds["artifact_digest"]
                or artifact.get("marginal_static_repair_health_inference_gate_digest")
                != reconstructed.inference_and_gates["artifact_digest"]
                or artifact.get("marginal_static_repair_health_preregistration_digest")
                != reconstructed.preregistration["artifact_digest"]
                or artifact.get(
                    "marginal_static_repair_health_preregistration_completion_digest"
                )
                != reconstructed.completion["artifact_digest"]
                or artifact.get("old_measurement_health") != "REPAIR"
                or artifact.get("old_decision_preserved") != "REPAIR_MEASUREMENT_SYSTEM"
                or artifact.get("measurement_health") != "REPAIR"
                or artifact.get("decision") != repair_execution["decision"]
                or artifact.get("decision_fact") != repair_execution["decision_fact"]
                or artifact.get("failed_cell_ids")
                != repair_execution["failed_cell_ids"]
                or artifact.get("failed_cell_count")
                != repair_execution["failed_cell_count"]
                or artifact.get("repair_required") is not True
                or artifact.get("eligible_for_historical_measurement") is not False
                or artifact.get("planned_calibration_replicates")
                != CALIBRATION_REPLICATES
                or artifact.get("planned_evaluation_replicates")
                != EVALUATION_REPLICATES
                or artifact.get("planned_total_replicates") != TOTAL_REPLICATES
                or artifact.get("planned_total_generated_issues")
                != TOTAL_GENERATED_ISSUES
                or artifact.get("planned_total_outer_evaluation_issues")
                != TOTAL_OUTER_EVALUATION_ISSUES
                or artifact.get("planned_execution_shards") != EXECUTION_SHARDS
                or artifact.get("execution_shard_size") != EXECUTION_SHARD_SIZE
                or artifact.get("max_rejecting_exceedance_count") != 24
                or artifact.get("nested_bootstrap_replicates_per_formal_replicate") != 0
                or artifact.get("round_42_seed_reuse") is not False
                or artifact.get("calibration_evaluation_seed_overlap") is not False
                or artifact.get("formal_execution_authorized") is not False
                or artifact.get("automatic_pass_from_preregistration") is not False
                or artifact.get("generated_issues") != 0
                or artifact.get("synthetic_replicates") != 0
                or artifact.get("bootstrap_replicates_executed") != 0
                or artifact.get("checkpoint_reads") != 0
                or artifact.get("compact_index_reads") != 0
                or artifact.get("sentinel_replicates_recomputed") != 0
                or artifact.get("duplicate_validation") is not False
                or artifact.get("historical_outcomes_read") is not False
                or artifact.get("statistical_results_read") is not False
                or artifact.get("evidence_created") is not False
                or artifact.get("promotion_gate_opened") is not False
                or artifact.get("downstream_consumer")
                != MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_TASK_KEY
                or artifact.get("production_action") != "none"
            ):
                raise MainlineSupervisorError(
                    "M4 v2 marginal-static repair preregistration replay "
                    "identity changed"
                )
            _verify_v2_registered_artifacts(
                root_dir=self.root_dir,
                registrations=registrations,
                expected_payloads=(*reconstructed.artifacts, artifact),
            )
            capability_replay = {
                "schema_version": (
                    "dehps-m4-v2-marginal-static-repair-preregistration-replay.v1"
                ),
                "status": "REPLAY_VERIFIED",
                "workload_and_seed_digest": reconstructed.workload_and_seeds[
                    "artifact_digest"
                ],
                "inference_and_gate_digest": reconstructed.inference_and_gates[
                    "artifact_digest"
                ],
                "preregistration_digest": reconstructed.preregistration[
                    "artifact_digest"
                ],
                "completion_digest": reconstructed.completion["artifact_digest"],
                "same_registered_content": True,
                "preregistration_only": True,
                "formal_replicates_executed": 0,
                "generated_issues_during_replay": 0,
                "bootstrap_replicates_executed": 0,
                "checkpoint_reads": 0,
                "compact_index_reads": 0,
                "sentinel_replicates_recomputed": 0,
                "duplicate_validation": False,
                "historical_outcomes_read": False,
                "statistical_results_read": False,
                "evidence_created": False,
                "manual_input_assembly": False,
            }
        elif task_key == MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_TASK_KEY:
            source_contract = (
                load_marginal_static_repair_health_execution_source_contract(
                    self.root_dir
                    / MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_SOURCE_CONTRACT_PATH
                )
            )
            verify_marginal_static_repair_health_execution_source_bytes(
                root_dir=self.root_dir,
                contract=source_contract,
            )
            _, preregistration_execution, preregistration_registrations = (
                _load_single_completed_execution(
                    repository=self.repository,
                    root_dir=self.root_dir,
                    control_plane_key=self.control_plane_key,
                    task_key=MARGINAL_STATIC_REPAIR_PREREGISTRATION_TASK_KEY,
                )
            )
            workload = _load_registered_type(
                root_dir=self.root_dir,
                registrations=preregistration_registrations,
                artifact_type=("m4_v2_marginal_static_repair_health_workload_seeds"),
            )
            inference = _load_registered_type(
                root_dir=self.root_dir,
                registrations=preregistration_registrations,
                artifact_type=("m4_v2_marginal_static_repair_health_inference_gates"),
            )
            preregistration = _load_registered_type(
                root_dir=self.root_dir,
                registrations=preregistration_registrations,
                artifact_type=("m4_v2_marginal_static_repair_health_preregistration"),
            )
            preregistration_completion = _load_registered_type(
                root_dir=self.root_dir,
                registrations=preregistration_registrations,
                artifact_type=(
                    "m4_v2_marginal_static_repair_health_preregistration_completion"
                ),
            )
            registered_index = _load_registered_type(
                root_dir=self.root_dir,
                registrations=registrations,
                artifact_type=("m4_v2_marginal_static_repair_health_completion_index"),
            )
            registered_feasibility = _load_registered_type(
                root_dir=self.root_dir,
                registrations=registrations,
                artifact_type="m4_v2_marginal_static_repair_health_feasibility",
            )
            registered_health = _load_registered_type(
                root_dir=self.root_dir,
                registrations=registrations,
                artifact_type=(
                    "m4_v2_marginal_static_repaired_measurement_health_result"
                ),
            )
            registered_completion = _load_registered_type(
                root_dir=self.root_dir,
                registrations=registrations,
                artifact_type=(
                    "m4_v2_marginal_static_repair_health_execution_completion"
                ),
            )
            reconstructed = rebuild_repair_health_artifacts_from_index(
                root_dir=self.root_dir,
                source_contract=source_contract,
                index_artifact=registered_index,
                workload_digest=str(workload["artifact_digest"]),
                inference_digest=str(inference["artifact_digest"]),
                preregistration_digest=str(preregistration["artifact_digest"]),
                execution_id=resolved_execution_id,
                git_commit=str(artifact["git_commit"]),
            )
            rebuilt_index, rebuilt_feasibility, rebuilt_health, rebuilt_completion = (
                reconstructed
            )
            expected_inputs = [
                str(source_contract["artifact_digest"]),
                str(preregistration_execution["artifact_digest"]),
                str(workload["artifact_digest"]),
                str(inference["artifact_digest"]),
                str(preregistration["artifact_digest"]),
                str(preregistration_completion["artifact_digest"]),
            ]
            if (
                registered_index != rebuilt_index
                or registered_feasibility != rebuilt_feasibility
                or registered_health != rebuilt_health
                or registered_completion != rebuilt_completion
                or artifact.get("input_artifact_digests") != expected_inputs
                or artifact.get(
                    "marginal_static_repair_health_execution_source_contract_digest"
                )
                != source_contract["artifact_digest"]
                or artifact.get(
                    "marginal_static_repair_health_execution_source_set_digest"
                )
                != source_contract["source_set_digest"]
                or artifact.get("repair_preregistration_execution_artifact_digest")
                != preregistration_execution["artifact_digest"]
                or artifact.get("marginal_static_repair_health_completion_index_digest")
                != rebuilt_index["artifact_digest"]
                or artifact.get("marginal_static_repair_health_feasibility_digest")
                != rebuilt_feasibility["artifact_digest"]
                or artifact.get("marginal_static_repair_health_result_digest")
                != rebuilt_health["artifact_digest"]
                or artifact.get(
                    "marginal_static_repair_health_execution_completion_digest"
                )
                != rebuilt_completion["artifact_digest"]
                or artifact.get("old_measurement_health") != "REPAIR"
                or artifact.get("old_decision_preserved") != "REPAIR_MEASUREMENT_SYSTEM"
                or artifact.get("measurement_health") != "REPAIR"
                or artifact.get("repair_health_preliminary_measurement_health")
                != rebuilt_health["preliminary_measurement_health"]
                or artifact.get("repair_health_authoritative_decision") is not None
                or artifact.get("eligible_for_historical_measurement") is not False
                or artifact.get("repair_required") is not True
                or artifact.get("replicate_count") != TOTAL_REPLICATES
                or artifact.get("calibration_replicates") != CALIBRATION_REPLICATES
                or artifact.get("evaluation_replicates") != EVALUATION_REPLICATES
                or artifact.get("generated_issues") != TOTAL_GENERATED_ISSUES
                or artifact.get("outer_evaluation_issues")
                != TOTAL_OUTER_EVALUATION_ISSUES
                or artifact.get("planned_execution_shards") != EXECUTION_SHARDS
                or artifact.get("execution_shard_size") != EXECUTION_SHARD_SIZE
                or artifact.get("nested_bootstrap_replicates_per_formal_replicate") != 0
                or artifact.get("checkpoint_mode")
                != "compact_index_direct_resume_without_scan"
                or artifact.get("completion_index_loads") != 1
                or artifact.get("sentinel_replicates_recomputed") != 0
                or artifact.get("duplicate_raw_replay") is not False
                or artifact.get("duplicate_validation") is not False
                or artifact.get("routine_physical_checkpoint_scan") is not False
                or artifact.get("round_42_seed_reuse") is not False
                or artifact.get("round_42_statistical_results_read") is not False
                or artifact.get("historical_outcomes_read") is not False
                or artifact.get("statistical_results_read") is not False
                or artifact.get("evidence_created") is not False
                or artifact.get("promotion_gate_opened") is not False
                or artifact.get("completion_fact")
                != MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_COMPLETION_FACT
                or artifact.get("downstream_consumer")
                != MARGINAL_STATIC_REPAIR_HEALTH_DECISION_TASK_KEY
                or artifact.get("production_action") != "none"
                or artifact.get("replay_status") != "COMPACT_INDEX_AGGREGATE_ONLY"
            ):
                raise MainlineSupervisorError(
                    "M4 v2 marginal-static repair health replay identity changed"
                )
            _verify_v2_registered_artifacts(
                root_dir=self.root_dir,
                registrations=registrations,
                expected_payloads=(*reconstructed, artifact),
            )
            capability_replay = {
                "schema_version": (
                    "dehps-m4-v2-marginal-static-repair-health-execution-replay.v1"
                ),
                "status": "REPLAY_VERIFIED",
                "completion_index_digest": rebuilt_index["artifact_digest"],
                "feasibility_digest": rebuilt_feasibility["artifact_digest"],
                "health_result_digest": rebuilt_health["artifact_digest"],
                "completion_digest": rebuilt_completion["artifact_digest"],
                "preliminary_measurement_health": rebuilt_health[
                    "preliminary_measurement_health"
                ],
                "authoritative_decision": None,
                "same_registered_content": True,
                "raw_replicates_regenerated": 0,
                "compact_index_reads": 1,
                "sentinel_replicates_recomputed": 0,
                "duplicate_validation": False,
                "historical_outcomes_read": False,
                "round_42_statistical_results_read": False,
                "evidence_created": False,
                "manual_input_assembly": False,
            }
        elif task_key == MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_TASK_KEY:
            source_contract = (
                load_marginal_static_repair_v2_health_execution_source_contract(
                    self.root_dir
                    / MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_SOURCE_CONTRACT_PATH
                )
            )
            verify_marginal_static_repair_v2_health_execution_source_bytes(
                root_dir=self.root_dir,
                contract=source_contract,
            )
            _, preregistration_execution, preregistration_registrations = (
                _load_single_completed_execution(
                    repository=self.repository,
                    root_dir=self.root_dir,
                    control_plane_key=self.control_plane_key,
                    task_key=MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_TASK_KEY,
                )
            )
            workload = _load_registered_type(
                root_dir=self.root_dir,
                registrations=preregistration_registrations,
                artifact_type=("m4_v2_marginal_static_repair_v2_health_workload_seeds"),
            )
            inference = _load_registered_type(
                root_dir=self.root_dir,
                registrations=preregistration_registrations,
                artifact_type=(
                    "m4_v2_marginal_static_repair_v2_health_inference_gates"
                ),
            )
            preregistration = _load_registered_type(
                root_dir=self.root_dir,
                registrations=preregistration_registrations,
                artifact_type=(
                    "m4_v2_marginal_static_repair_v2_health_preregistration"
                ),
            )
            preregistration_completion = _load_registered_type(
                root_dir=self.root_dir,
                registrations=preregistration_registrations,
                artifact_type=(
                    "m4_v2_marginal_static_repair_v2_health_preregistration_completion"
                ),
            )
            registered_index = _load_registered_type(
                root_dir=self.root_dir,
                registrations=registrations,
                artifact_type=(
                    "m4_v2_marginal_static_repair_v2_health_completion_index"
                ),
            )
            registered_health = _load_registered_type(
                root_dir=self.root_dir,
                registrations=registrations,
                artifact_type=(
                    "m4_v2_marginal_static_repair_v2_measurement_health_result"
                ),
            )
            registered_completion = _load_registered_type(
                root_dir=self.root_dir,
                registrations=registrations,
                artifact_type=(
                    "m4_v2_marginal_static_repair_v2_health_execution_completion"
                ),
            )
            rebuilt_index, rebuilt_health, rebuilt_completion = (
                rebuild_repair_v2_health_artifacts_from_index(
                    root_dir=self.root_dir,
                    index_artifact=registered_index,
                    workload_digest=str(workload["artifact_digest"]),
                    inference_digest=str(inference["artifact_digest"]),
                    preregistration_digest=str(preregistration["artifact_digest"]),
                    execution_id=resolved_execution_id,
                    git_commit=str(artifact["git_commit"]),
                )
            )
            if (
                registered_index != rebuilt_index
                or registered_health != rebuilt_health
                or registered_completion != rebuilt_completion
                or artifact.get(
                    "marginal_static_repair_v2_health_execution_source_contract_digest"
                )
                != source_contract["artifact_digest"]
                or artifact.get(
                    "marginal_static_repair_v2_health_execution_source_set_digest"
                )
                != source_contract["source_set_digest"]
                or artifact.get("repair_v2_preregistration_execution_digest")
                != preregistration_execution["artifact_digest"]
                or artifact.get("repair_v2_workload_seed_digest")
                != workload["artifact_digest"]
                or artifact.get("repair_v2_inference_gate_digest")
                != inference["artifact_digest"]
                or artifact.get("repair_v2_preregistration_digest")
                != preregistration["artifact_digest"]
                or artifact.get("repair_v2_preregistration_completion_digest")
                != preregistration_completion["artifact_digest"]
                or artifact.get("repair_v2_health_completion_index_digest")
                != rebuilt_index["artifact_digest"]
                or artifact.get("repair_v2_health_result_digest")
                != rebuilt_health["artifact_digest"]
                or artifact.get("repair_v2_health_execution_completion_digest")
                != rebuilt_completion["artifact_digest"]
                or artifact.get("repair_v2_preliminary_measurement_health")
                != rebuilt_health["preliminary_measurement_health"]
                or artifact.get("repair_v2_authoritative_decision") is not None
                or artifact.get("reference_children") != REPAIR_V2_REFERENCE_CHILDREN
                or artifact.get("evaluation_children") != REPAIR_V2_EVALUATION_CHILDREN
                or artifact.get("total_children") != REPAIR_V2_TOTAL_CHILDREN
                or artifact.get("generated_issues") != REPAIR_V2_GENERATED_ISSUES
                or artifact.get("outer_evaluation_issues")
                != REPAIR_V2_OUTER_EVALUATION_ISSUES
                or artifact.get("process_pool_jobs") != REPAIR_V2_SHARD_COUNT
                or artifact.get("planned_execution_shards") != REPAIR_V2_SHARD_COUNT
                or artifact.get("execution_shard_size") != REPAIR_V2_SHARD_SIZE
                or artifact.get("checkpoint_mode")
                != "compact_index_load_once_no_revalidation"
                or artifact.get("completion_index_loads") != 1
                or artifact.get("completed_matching_child_action")
                != "skip_without_generation_or_revalidation"
                or artifact.get("new_child_dispatch") != "at_most_once_per_execution"
                or artifact.get("slow_scalar_oracle_in_formal_child") is not False
                or artifact.get("independent_vectorized_identity_reduction") is not True
                or artifact.get("raw_replicates_regenerated") != 0
                or artifact.get("sentinel_replicates_recomputed") != 0
                or artifact.get("duplicate_validation") is not False
                or artifact.get("database_reads_during_child") != 0
                or artifact.get("database_writes_during_child") != 0
                or artifact.get("historical_outcomes_read") is not False
                or artifact.get("evidence_created") is not False
                or artifact.get("promotion_gate_opened") is not False
                or artifact.get("completion_fact")
                != MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_COMPLETION_FACT
                or artifact.get("downstream_consumer")
                != MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_TASK_KEY
                or artifact.get("production_action") != "none"
                or artifact.get("replay_status") != "REGISTERED_AGGREGATE_ONLY"
            ):
                raise MainlineSupervisorError(
                    "M4 v2 marginal-static repair-v2 health replay identity changed"
                )
            _verify_v2_registered_artifacts(
                root_dir=self.root_dir,
                registrations=registrations,
                expected_payloads=(
                    rebuilt_index,
                    rebuilt_health,
                    rebuilt_completion,
                    artifact,
                ),
            )
            capability_replay = {
                "schema_version": (
                    "dehps-m4-v2-marginal-static-repair-v2-health-execution-replay.v1"
                ),
                "status": "REPLAY_VERIFIED",
                "completion_index_digest": rebuilt_index["artifact_digest"],
                "health_result_digest": rebuilt_health["artifact_digest"],
                "completion_digest": rebuilt_completion["artifact_digest"],
                "preliminary_measurement_health": rebuilt_health[
                    "preliminary_measurement_health"
                ],
                "authoritative_decision": None,
                "same_registered_content": True,
                "registered_aggregate_only": True,
                "raw_replicates_regenerated": 0,
                "generated_children_during_replay": 0,
                "compact_index_reads": 1,
                "sentinel_replicates_recomputed": 0,
                "duplicate_validation": False,
                "historical_outcomes_read": False,
                "evidence_created": False,
                "manual_input_assembly": False,
            }
        elif task_key == MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_TASK_KEY:
            source_contract = (
                load_marginal_static_repair_v2_health_decision_source_contract(
                    self.root_dir
                    / MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_SOURCE_CONTRACT_PATH
                )
            )
            verify_marginal_static_repair_v2_health_decision_source_bytes(
                root_dir=self.root_dir,
                contract=source_contract,
            )
            _, health_execution, health_registrations = (
                _load_single_completed_execution(
                    repository=self.repository,
                    root_dir=self.root_dir,
                    control_plane_key=self.control_plane_key,
                    task_key=MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_TASK_KEY,
                )
            )
            health_result = _load_registered_type(
                root_dir=self.root_dir,
                registrations=health_registrations,
                artifact_type=(
                    "m4_v2_marginal_static_repair_v2_measurement_health_result"
                ),
            )
            health_completion = _load_registered_type(
                root_dir=self.root_dir,
                registrations=health_registrations,
                artifact_type=(
                    "m4_v2_marginal_static_repair_v2_health_execution_completion"
                ),
            )
            registered_decision = _load_registered_type(
                root_dir=self.root_dir,
                registrations=registrations,
                artifact_type=(
                    "m4_v2_marginal_static_measurement_repair_v2_health_decision"
                ),
            )
            reconstructed = build_marginal_static_repair_v2_health_decision(
                source_contract=source_contract,
                health_execution=health_execution,
                health_result=health_result,
                health_completion=health_completion,
            )
            if (
                registered_decision != reconstructed
                or artifact.get(
                    "marginal_static_repair_v2_health_decision_source_contract_digest"
                )
                != source_contract["artifact_digest"]
                or artifact.get(
                    "marginal_static_repair_v2_health_decision_source_set_digest"
                )
                != source_contract["source_set_digest"]
                or artifact.get("repair_v2_health_execution_artifact_digest")
                != health_execution["artifact_digest"]
                or artifact.get("repair_v2_health_result_digest")
                != health_result["artifact_digest"]
                or artifact.get("repair_v2_health_completion_digest")
                != health_completion["artifact_digest"]
                or artifact.get(
                    "marginal_static_repair_v2_health_decision_artifact_digest"
                )
                != reconstructed["artifact_digest"]
                or artifact.get("authoritative_decision")
                != reconstructed["authoritative_decision"]
                or artifact.get("decision") != reconstructed["decision"]
                or artifact.get("decision_fact") != reconstructed["decision_fact"]
                or artifact.get("measurement_health") != "PASS"
                or artifact.get("failed_required_gate_cell_ids") != []
                or artifact.get("failed_required_gate_cell_count") != 0
                or artifact.get("required_gate_cell_ids")
                != reconstructed["required_gate_cell_ids"]
                or artifact.get("required_gate_cell_count") != 10
                or artifact.get("admissible_local_cell_ids")
                != reconstructed["admissible_local_cell_ids"]
                or artifact.get("admissible_local_cell_count") != 2
                or artifact.get("sensitivity_limit_cell_ids")
                != reconstructed["sensitivity_limit_cell_ids"]
                or artifact.get("sensitivity_limit_topology")
                != reconstructed["sensitivity_limit_topology"]
                or artifact.get("sensitivity_limit_cell_count") != 4
                or artifact.get("eligible_for_historical_measurement") is not True
                or artifact.get("eligible_for_historical_measurement_design")
                is not True
                or artifact.get("historical_measurement_execution_authorized")
                is not False
                or artifact.get("statistical_results_read") is not True
                or artifact.get("generated_issues") != 0
                or artifact.get("compact_index_reads") != 0
                or artifact.get("raw_replicates_regenerated") != 0
                or artifact.get("sentinel_replicates_recomputed") != 0
                or artifact.get("duplicate_validation") is not False
                or artifact.get("historical_outcomes_read") is not False
                or artifact.get("evidence_created") is not False
                or artifact.get("promotion_gate_opened") is not False
                or artifact.get("repair_required") is not False
                or artifact.get("downstream_consumer") != reconstructed["next_consumer"]
                or artifact.get("production_action") != "none"
            ):
                raise MainlineSupervisorError(
                    "M4 v2 marginal-static repair-v2 health decision replay "
                    "identity changed"
                )
            _verify_v2_registered_artifacts(
                root_dir=self.root_dir,
                registrations=registrations,
                expected_payloads=(reconstructed, artifact),
            )
            capability_replay = {
                "schema_version": (
                    "dehps-m4-v2-marginal-static-repair-v2-health-decision-replay.v1"
                ),
                "status": "REPLAY_VERIFIED",
                "decision_artifact_digest": reconstructed["artifact_digest"],
                "measurement_health": reconstructed["measurement_health"],
                "authoritative_decision": reconstructed["authoritative_decision"],
                "decision": reconstructed["decision"],
                "decision_fact": reconstructed["decision_fact"],
                "required_gate_cell_count": reconstructed["required_gate_cell_count"],
                "sensitivity_limit_cell_ids": reconstructed[
                    "sensitivity_limit_cell_ids"
                ],
                "sensitivity_limit_cell_count": reconstructed[
                    "sensitivity_limit_cell_count"
                ],
                "same_registered_content": True,
                "decision_only": True,
                "generated_issues_during_replay": 0,
                "compact_index_reads": 0,
                "raw_replicates_regenerated": 0,
                "sentinel_replicates_recomputed": 0,
                "duplicate_validation": False,
                "historical_outcomes_read": False,
                "statistical_results_read": True,
                "evidence_created": False,
                "manual_input_assembly": False,
            }
        elif task_key == MARGINAL_STATIC_HISTORICAL_DESIGN_TASK_KEY:
            source_contract = load_marginal_static_historical_design_source_contract(
                self.root_dir / MARGINAL_STATIC_HISTORICAL_DESIGN_SOURCE_CONTRACT_PATH
            )
            verify_marginal_static_historical_design_source_bytes(
                root_dir=self.root_dir,
                contract=source_contract,
            )
            _, health_decision_execution, health_decision_registrations = (
                _load_single_completed_execution(
                    repository=self.repository,
                    root_dir=self.root_dir,
                    control_plane_key=self.control_plane_key,
                    task_key=MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_TASK_KEY,
                )
            )
            health_decision = _load_registered_type(
                root_dir=self.root_dir,
                registrations=health_decision_registrations,
                artifact_type=(
                    "m4_v2_marginal_static_measurement_repair_v2_health_decision"
                ),
            )
            _, marginal_execution, marginal_registrations = (
                _load_single_completed_execution(
                    repository=self.repository,
                    root_dir=self.root_dir,
                    control_plane_key=self.control_plane_key,
                    task_key=HISTORICAL_MARGINAL_STATIC_CONTRACT_TASK_KEY,
                )
            )
            marginal_contract = _load_registered_type(
                root_dir=self.root_dir,
                registrations=marginal_registrations,
                artifact_type="m4_v2_marginal_static_measurement_contract",
            )
            _, measurement_execution, measurement_registrations = (
                _load_single_completed_execution(
                    repository=self.repository,
                    root_dir=self.root_dir,
                    control_plane_key=self.control_plane_key,
                    task_key=HISTORICAL_MEASUREMENT_CONTRACT_DESIGN_TASK_KEY,
                )
            )
            gate_compiler = _load_registered_type(
                root_dir=self.root_dir,
                registrations=measurement_registrations,
                artifact_type="measurement_v2_gate_compiler_contract",
            )
            frozen_preregistration = _load_object(
                self.root_dir / MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_PATH
            )
            reconstructed = build_marginal_static_historical_design_artifacts(
                source_contract=source_contract,
                repair_v2_health_decision_execution=health_decision_execution,
                repair_v2_health_decision=health_decision,
                marginal_static_contract_execution=marginal_execution,
                marginal_static_measurement_contract=marginal_contract,
                measurement_contract_design_execution=measurement_execution,
                gate_compiler_contract=gate_compiler,
                frozen_preregistration=frozen_preregistration,
                execution_id=resolved_execution_id,
                git_commit=str(artifact["git_commit"]),
            )
            registered_boundary = _load_registered_type(
                root_dir=self.root_dir,
                registrations=registrations,
                artifact_type=("m4_v2_marginal_static_historical_dataset_boundary"),
            )
            registered_walk_forward = _load_registered_type(
                root_dir=self.root_dir,
                registrations=registrations,
                artifact_type=("m4_v2_marginal_static_historical_walk_forward_design"),
            )
            registered_inference = _load_registered_type(
                root_dir=self.root_dir,
                registrations=registrations,
                artifact_type=("m4_v2_marginal_static_historical_inference_design"),
            )
            registered_completion = _load_registered_type(
                root_dir=self.root_dir,
                registrations=registrations,
                artifact_type=(
                    "m4_v2_marginal_static_historical_measurement_design_completion"
                ),
            )
            if (
                registered_boundary != reconstructed.dataset_boundary
                or registered_walk_forward != reconstructed.walk_forward_design
                or registered_inference != reconstructed.inference_design
                or registered_completion != reconstructed.completion
                or artifact.get(
                    "marginal_static_historical_design_source_contract_digest"
                )
                != source_contract["artifact_digest"]
                or artifact.get("marginal_static_historical_design_source_set_digest")
                != source_contract["source_set_digest"]
                or artifact.get("research_request_id") != 362
                or artifact.get("research_execution_id") != 283
                or artifact.get("engineering_request_id") != 363
                or artifact.get("engineering_execution_id") != 284
                or artifact.get("repair_v2_health_decision_execution_digest")
                != health_decision_execution["artifact_digest"]
                or artifact.get("repair_v2_health_decision_digest")
                != health_decision["artifact_digest"]
                or artifact.get("marginal_static_contract_execution_digest")
                != marginal_execution["artifact_digest"]
                or artifact.get("marginal_static_measurement_contract_digest")
                != marginal_contract["artifact_digest"]
                or artifact.get("measurement_contract_design_execution_digest")
                != measurement_execution["artifact_digest"]
                or artifact.get("gate_compiler_contract_digest")
                != gate_compiler["artifact_digest"]
                or artifact.get("frozen_preregistration_digest")
                != frozen_preregistration["artifact_digest"]
                or artifact.get("historical_dataset_boundary_digest")
                != reconstructed.dataset_boundary["artifact_digest"]
                or artifact.get("historical_walk_forward_design_digest")
                != reconstructed.walk_forward_design["artifact_digest"]
                or artifact.get("historical_inference_design_digest")
                != reconstructed.inference_design["artifact_digest"]
                or artifact.get("historical_design_completion_digest")
                != reconstructed.completion["artifact_digest"]
                or artifact.get("historical_issue_count") != 3481
                or artifact.get("initial_training_issue_count") != 900
                or artifact.get("planned_evaluation_fold_count") != 2581
                or artifact.get("planned_bootstrap_replicates") != 2000
                or artifact.get("formal_historical_folds_executed") != 0
                or artifact.get("bootstrap_replicates_executed") != 0
                or artifact.get("database_queries_during_capability") != 0
                or artifact.get("historical_red_outcomes_read") is not False
                or artifact.get("historical_outcomes_read") is not False
                or artifact.get("statistical_results_read") is not False
                or artifact.get("evidence_created") is not False
                or artifact.get("evidence_progress_before") != 25
                or artifact.get("evidence_progress_after") != 25
                or artifact.get("historical_evidence") != "NOT_RUN"
                or artifact.get("historical_execution_status") != "NOT_AUTHORIZED"
                or artifact.get("accepted_model_artifact_digest") is not None
                or artifact.get("promotion_gate_opened") is not False
                or artifact.get("actual_fold_count") != 0
                or artifact.get("registered_artifact_count") != 5
                or artifact.get("completion_fact")
                != MARGINAL_STATIC_HISTORICAL_DESIGN_COMPLETION_FACT
                or artifact.get("downstream_consumer")
                != MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_KEY
                or artifact.get("production_action") != "none"
                or artifact.get("replay_status") != "DETERMINISTIC_DESIGN_ONLY"
            ):
                raise MainlineSupervisorError(
                    "M4 v2 marginal-static historical design replay identity changed"
                )
            _verify_v2_registered_artifacts(
                root_dir=self.root_dir,
                registrations=registrations,
                expected_payloads=(*reconstructed.artifacts, artifact),
            )
            capability_replay = {
                "schema_version": (
                    "dehps-m4-v2-marginal-static-historical-design-replay.v1"
                ),
                "status": "REPLAY_VERIFIED",
                "dataset_boundary_digest": reconstructed.dataset_boundary[
                    "artifact_digest"
                ],
                "walk_forward_design_digest": reconstructed.walk_forward_design[
                    "artifact_digest"
                ],
                "inference_design_digest": reconstructed.inference_design[
                    "artifact_digest"
                ],
                "completion_digest": reconstructed.completion["artifact_digest"],
                "same_registered_content": True,
                "design_only": True,
                "formal_historical_folds_executed": 0,
                "bootstrap_replicates_executed": 0,
                "database_queries_during_replay": 0,
                "historical_red_outcomes_read": False,
                "statistical_results_read": False,
                "evidence_created": False,
                "accepted_model_artifact_digest": None,
                "promotion_gate_opened": False,
                "manual_input_assembly": False,
            }
        elif task_key == MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_TASK_KEY:
            source_contract = (
                load_marginal_static_repair_v2_preregistration_source_contract(
                    self.root_dir
                    / MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_SOURCE_CONTRACT_PATH
                )
            )
            verify_marginal_static_repair_v2_preregistration_source_bytes(
                root_dir=self.root_dir,
                contract=source_contract,
            )
            _, design_execution, design_registrations = (
                _load_single_completed_execution(
                    repository=self.repository,
                    root_dir=self.root_dir,
                    control_plane_key=self.control_plane_key,
                    task_key=MARGINAL_STATIC_REPAIR_V2_DESIGN_TASK_KEY,
                )
            )
            presample_feasibility = _load_registered_type(
                root_dir=self.root_dir,
                registrations=design_registrations,
                artifact_type=("m4_v2_marginal_static_repair_v2_presample_feasibility"),
            )
            repair_v2_design = _load_registered_type(
                root_dir=self.root_dir,
                registrations=design_registrations,
                artifact_type="m4_v2_marginal_static_measurement_repair_v2_design",
            )
            design_completion = _load_registered_type(
                root_dir=self.root_dir,
                registrations=design_registrations,
                artifact_type="m4_v2_marginal_static_repair_v2_design_completion",
            )
            registered_workload = _load_registered_type(
                root_dir=self.root_dir,
                registrations=registrations,
                artifact_type=("m4_v2_marginal_static_repair_v2_health_workload_seeds"),
            )
            registered_inference = _load_registered_type(
                root_dir=self.root_dir,
                registrations=registrations,
                artifact_type=(
                    "m4_v2_marginal_static_repair_v2_health_inference_gates"
                ),
            )
            registered_preregistration = _load_registered_type(
                root_dir=self.root_dir,
                registrations=registrations,
                artifact_type=(
                    "m4_v2_marginal_static_repair_v2_health_preregistration"
                ),
            )
            registered_completion = _load_registered_type(
                root_dir=self.root_dir,
                registrations=registrations,
                artifact_type=(
                    "m4_v2_marginal_static_repair_v2_health_preregistration_completion"
                ),
            )
            reconstructed = build_marginal_static_repair_v2_preregistration_artifacts(
                source_contract=source_contract,
                design_execution=design_execution,
                presample_feasibility=presample_feasibility,
                repair_v2_design=repair_v2_design,
                design_completion=design_completion,
                execution_id=resolved_execution_id,
                git_commit=str(artifact["git_commit"]),
            )
            frozen = source_contract["frozen_contract"]
            workload = frozen["workload"]
            resume = frozen["resume_and_uniqueness"]
            if (
                registered_workload != reconstructed.workload_and_seeds
                or registered_inference != reconstructed.inference_and_gates
                or registered_preregistration != reconstructed.preregistration
                or registered_completion != reconstructed.completion
                or artifact.get(
                    "marginal_static_repair_v2_preregistration_source_contract_digest"
                )
                != source_contract["artifact_digest"]
                or artifact.get(
                    "marginal_static_repair_v2_preregistration_source_set_digest"
                )
                != source_contract["source_set_digest"]
                or artifact.get("repair_v2_design_execution_digest")
                != design_execution["artifact_digest"]
                or artifact.get("repair_v2_presample_feasibility_digest")
                != presample_feasibility["artifact_digest"]
                or artifact.get("repair_v2_design_digest")
                != repair_v2_design["artifact_digest"]
                or artifact.get("repair_v2_design_completion_digest")
                != design_completion["artifact_digest"]
                or artifact.get("repair_v2_workload_seed_digest")
                != reconstructed.workload_and_seeds["artifact_digest"]
                or artifact.get("repair_v2_inference_gate_digest")
                != reconstructed.inference_and_gates["artifact_digest"]
                or artifact.get("repair_v2_preregistration_digest")
                != reconstructed.preregistration["artifact_digest"]
                or artifact.get("repair_v2_preregistration_completion_digest")
                != reconstructed.completion["artifact_digest"]
                or artifact.get("future_reference_children")
                != workload["reference_children"]
                or artifact.get("future_evaluation_children")
                != workload["evaluation_children"]
                or artifact.get("future_total_children") != workload["total_children"]
                or artifact.get("future_shard_count") != workload["shard_count"]
                or artifact.get("future_shard_size") != workload["shard_size"]
                or artifact.get("future_generated_issues")
                != workload["planned_generated_issues"]
                or artifact.get("future_outer_evaluation_issues")
                != workload["planned_outer_evaluation_issues"]
                or artifact.get("future_completion_index_loads")
                != resume["completion_index_loads"]
                or artifact.get("completed_matching_child_action")
                != "skip_without_generation_or_revalidation"
                or artifact.get("new_child_dispatch") != "at_most_once_per_execution"
                or artifact.get("formal_replicates_executed") != 0
                or artifact.get("generated_issues") != 0
                or artifact.get("checkpoint_reads") != 0
                or artifact.get("compact_index_reads") != 0
                or artifact.get("raw_replicates_regenerated") != 0
                or artifact.get("sentinel_replicates_recomputed") != 0
                or artifact.get("duplicate_validation") is not False
                or artifact.get("historical_outcomes_read") is not False
                or artifact.get("statistical_results_read") is not False
                or artifact.get("evidence_created") is not False
                or artifact.get("promotion_gate_opened") is not False
                or artifact.get("completion_fact")
                != MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_COMPLETION_FACT
                or artifact.get("downstream_consumer")
                != MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_TASK_KEY
                or artifact.get("production_action") != "none"
            ):
                raise MainlineSupervisorError(
                    "M4 v2 marginal-static repair-v2 preregistration replay "
                    "identity changed"
                )
            _verify_v2_registered_artifacts(
                root_dir=self.root_dir,
                registrations=registrations,
                expected_payloads=(*reconstructed.artifacts, artifact),
            )
            capability_replay = {
                "schema_version": (
                    "dehps-m4-v2-marginal-static-repair-v2-preregistration-replay.v1"
                ),
                "status": "REPLAY_VERIFIED",
                "workload_and_seed_digest": reconstructed.workload_and_seeds[
                    "artifact_digest"
                ],
                "inference_and_gate_digest": reconstructed.inference_and_gates[
                    "artifact_digest"
                ],
                "preregistration_digest": reconstructed.preregistration[
                    "artifact_digest"
                ],
                "completion_digest": reconstructed.completion["artifact_digest"],
                "same_registered_content": True,
                "preregistration_only": True,
                "formal_replicates_executed": 0,
                "generated_issues_during_replay": 0,
                "checkpoint_reads": 0,
                "compact_index_reads": 0,
                "raw_replicates_regenerated": 0,
                "sentinel_replicates_recomputed": 0,
                "duplicate_validation": False,
                "historical_outcomes_read": False,
                "statistical_results_read": False,
                "evidence_created": False,
                "manual_input_assembly": False,
            }
        elif task_key == MARGINAL_STATIC_REPAIR_V2_DESIGN_TASK_KEY:
            source_contract = load_marginal_static_repair_v2_design_source_contract(
                self.root_dir / MARGINAL_STATIC_REPAIR_V2_DESIGN_SOURCE_CONTRACT_PATH
            )
            verify_marginal_static_repair_v2_design_source_bytes(
                root_dir=self.root_dir,
                contract=source_contract,
            )
            _, decision_execution, decision_registrations = (
                _load_single_completed_execution(
                    repository=self.repository,
                    root_dir=self.root_dir,
                    control_plane_key=self.control_plane_key,
                    task_key=REPAIR_HEALTH_DECISION_TASK_KEY,
                )
            )
            decision = _load_registered_type(
                root_dir=self.root_dir,
                registrations=decision_registrations,
                artifact_type=(
                    "m4_v2_marginal_static_measurement_repair_health_decision"
                ),
            )
            registered_feasibility = _load_registered_type(
                root_dir=self.root_dir,
                registrations=registrations,
                artifact_type=("m4_v2_marginal_static_repair_v2_presample_feasibility"),
            )
            registered_design = _load_registered_type(
                root_dir=self.root_dir,
                registrations=registrations,
                artifact_type="m4_v2_marginal_static_measurement_repair_v2_design",
            )
            registered_completion = _load_registered_type(
                root_dir=self.root_dir,
                registrations=registrations,
                artifact_type=("m4_v2_marginal_static_repair_v2_design_completion"),
            )
            reconstructed = build_marginal_static_repair_v2_design_artifacts(
                source_contract=source_contract,
                repair_health_decision_execution=decision_execution,
                repair_health_decision=decision,
                execution_id=resolved_execution_id,
                git_commit=str(artifact["git_commit"]),
            )
            workload = source_contract["frozen_contract"]["future_workload"]
            proof = source_contract["frozen_contract"]["presample_sample_size_proof"]
            if (
                registered_feasibility != reconstructed.presample_feasibility
                or registered_design != reconstructed.repair_v2_design
                or registered_completion != reconstructed.completion
                or artifact.get(
                    "marginal_static_repair_v2_design_source_contract_digest"
                )
                != source_contract["artifact_digest"]
                or artifact.get("marginal_static_repair_v2_design_source_set_digest")
                != source_contract["source_set_digest"]
                or artifact.get("repair_health_decision_execution_digest")
                != decision_execution["artifact_digest"]
                or artifact.get("repair_health_decision_digest")
                != decision["artifact_digest"]
                or artifact.get("presample_feasibility_digest")
                != reconstructed.presample_feasibility["artifact_digest"]
                or artifact.get("repair_v2_design_digest")
                != reconstructed.repair_v2_design["artifact_digest"]
                or artifact.get("repair_v2_design_completion_digest")
                != reconstructed.completion["artifact_digest"]
                or artifact.get("old_measurement_health") != "REPAIR"
                or artifact.get("old_decision_preserved") != "REPAIR_MEASUREMENT_SYSTEM"
                or artifact.get("measurement_health") != "REPAIR"
                or artifact.get("decision") != "REPAIR_MEASUREMENT_SYSTEM"
                or artifact.get("failed_control_cell_count") != 3
                or artifact.get("reference_scores_per_block") != 19
                or artifact.get("evaluation_replicates_per_cell") != 1024
                or artifact.get("future_total_replicates")
                != workload["total_replicates"]
                or artifact.get("future_generated_issues")
                != workload["planned_generated_issues"]
                or artifact.get("familywise_false_repair_union_bound")
                != proof["six_control_union_bound"]
                or artifact.get("formal_replicates_executed") != 0
                or artifact.get("generated_issues") != 0
                or artifact.get("checkpoint_reads") != 0
                or artifact.get("compact_index_reads") != 0
                or artifact.get("raw_replicates_regenerated") != 0
                or artifact.get("sentinel_replicates_recomputed") != 0
                or artifact.get("duplicate_validation") is not False
                or artifact.get("historical_outcomes_read") is not False
                or artifact.get("statistical_results_read") is not True
                or artifact.get("evidence_created") is not False
                or artifact.get("promotion_gate_opened") is not False
                or artifact.get("completion_fact")
                != MARGINAL_STATIC_REPAIR_V2_DESIGN_COMPLETION_FACT
                or artifact.get("downstream_consumer")
                != MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_TASK_KEY
                or artifact.get("production_action") != "none"
            ):
                raise MainlineSupervisorError(
                    "M4 v2 marginal-static repair-v2 design replay identity changed"
                )
            _verify_v2_registered_artifacts(
                root_dir=self.root_dir,
                registrations=registrations,
                expected_payloads=(*reconstructed.artifacts, artifact),
            )
            capability_replay = {
                "schema_version": (
                    "dehps-m4-v2-marginal-static-repair-v2-design-replay.v1"
                ),
                "status": "REPLAY_VERIFIED",
                "presample_feasibility_digest": reconstructed.presample_feasibility[
                    "artifact_digest"
                ],
                "repair_v2_design_digest": reconstructed.repair_v2_design[
                    "artifact_digest"
                ],
                "completion_digest": reconstructed.completion["artifact_digest"],
                "same_registered_content": True,
                "design_only": True,
                "formal_replicates_executed": 0,
                "generated_issues_during_replay": 0,
                "checkpoint_reads": 0,
                "compact_index_reads": 0,
                "raw_replicates_regenerated": 0,
                "sentinel_replicates_recomputed": 0,
                "duplicate_validation": False,
                "historical_outcomes_read": False,
                "statistical_results_read": True,
                "evidence_created": False,
                "manual_input_assembly": False,
            }
        elif task_key == MARGINAL_STATIC_REPAIR_HEALTH_DECISION_TASK_KEY:
            source_contract = (
                load_marginal_static_repair_health_decision_source_contract(
                    self.root_dir
                    / MARGINAL_STATIC_REPAIR_HEALTH_DECISION_SOURCE_CONTRACT_PATH
                )
            )
            verify_marginal_static_repair_health_decision_source_bytes(
                root_dir=self.root_dir,
                contract=source_contract,
            )
            _, health_execution, health_registrations = (
                _load_single_completed_execution(
                    repository=self.repository,
                    root_dir=self.root_dir,
                    control_plane_key=self.control_plane_key,
                    task_key=MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_TASK_KEY,
                )
            )
            health_result = _load_registered_type(
                root_dir=self.root_dir,
                registrations=health_registrations,
                artifact_type=(
                    "m4_v2_marginal_static_repaired_measurement_health_result"
                ),
            )
            health_completion = _load_registered_type(
                root_dir=self.root_dir,
                registrations=health_registrations,
                artifact_type=(
                    "m4_v2_marginal_static_repair_health_execution_completion"
                ),
            )
            registered_decision = _load_registered_type(
                root_dir=self.root_dir,
                registrations=registrations,
                artifact_type=(
                    "m4_v2_marginal_static_measurement_repair_health_decision"
                ),
            )
            reconstructed = build_marginal_static_repair_health_decision(
                source_contract=source_contract,
                health_execution=health_execution,
                health_result=health_result,
                health_completion=health_completion,
            )
            if (
                registered_decision != reconstructed
                or artifact.get(
                    "marginal_static_repair_health_decision_source_contract_digest"
                )
                != source_contract["artifact_digest"]
                or artifact.get(
                    "marginal_static_repair_health_decision_source_set_digest"
                )
                != source_contract["source_set_digest"]
                or artifact.get("repair_health_execution_artifact_digest")
                != health_execution["artifact_digest"]
                or artifact.get("repair_health_result_digest")
                != health_result["artifact_digest"]
                or artifact.get("repair_health_completion_digest")
                != health_completion["artifact_digest"]
                or artifact.get(
                    "marginal_static_repair_health_decision_artifact_digest"
                )
                != reconstructed["artifact_digest"]
                or artifact.get("authoritative_decision")
                != reconstructed["authoritative_decision"]
                or artifact.get("decision") != reconstructed["decision"]
                or artifact.get("decision_fact") != reconstructed["decision_fact"]
                or artifact.get("measurement_health") != "REPAIR"
                or artifact.get("failed_control_cell_ids")
                != reconstructed["failed_control_cell_ids"]
                or artifact.get("failed_control_topology")
                != reconstructed["failed_control_topology"]
                or artifact.get("failed_control_cell_count") != 3
                or artifact.get("instrument_limit_cell_count") != 0
                or artifact.get("eligible_for_historical_measurement") is not False
                or artifact.get("statistical_results_read") is not True
                or artifact.get("generated_issues") != 0
                or artifact.get("compact_index_reads") != 0
                or artifact.get("raw_replicates_regenerated") != 0
                or artifact.get("sentinel_replicates_recomputed") != 0
                or artifact.get("duplicate_validation") is not False
                or artifact.get("historical_outcomes_read") is not False
                or artifact.get("evidence_created") is not False
                or artifact.get("promotion_gate_opened") is not False
                or artifact.get("repair_required") is not True
                or artifact.get("downstream_consumer")
                != MARGINAL_STATIC_REPAIR_V2_DESIGN_TASK_KEY
                or artifact.get("production_action") != "none"
            ):
                raise MainlineSupervisorError(
                    "M4 v2 marginal-static repair health decision replay "
                    "identity changed"
                )
            _verify_v2_registered_artifacts(
                root_dir=self.root_dir,
                registrations=registrations,
                expected_payloads=(reconstructed, artifact),
            )
            capability_replay = {
                "schema_version": (
                    "dehps-m4-v2-marginal-static-repair-health-decision-replay.v1"
                ),
                "status": "REPLAY_VERIFIED",
                "decision_artifact_digest": reconstructed["artifact_digest"],
                "measurement_health": reconstructed["measurement_health"],
                "authoritative_decision": reconstructed["authoritative_decision"],
                "decision": reconstructed["decision"],
                "decision_fact": reconstructed["decision_fact"],
                "failed_control_cell_ids": reconstructed["failed_control_cell_ids"],
                "failed_control_cell_count": reconstructed["failed_control_cell_count"],
                "same_registered_content": True,
                "decision_only": True,
                "generated_issues_during_replay": 0,
                "compact_index_reads": 0,
                "raw_replicates_regenerated": 0,
                "sentinel_replicates_recomputed": 0,
                "duplicate_validation": False,
                "historical_outcomes_read": False,
                "statistical_results_read": True,
                "evidence_created": False,
                "manual_input_assembly": False,
            }
        elif task_key == MARGINAL_STATIC_HEALTH_DECISION_TASK_KEY:
            source_contract = load_marginal_static_health_decision_source_contract(
                self.root_dir / MARGINAL_STATIC_HEALTH_DECISION_SOURCE_CONTRACT_PATH
            )
            verify_marginal_static_health_decision_source_bytes(
                root_dir=self.root_dir,
                contract=source_contract,
            )
            _, health_execution, health_registrations = (
                _load_single_completed_execution(
                    repository=self.repository,
                    root_dir=self.root_dir,
                    control_plane_key=self.control_plane_key,
                    task_key=MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY,
                )
            )
            health_result = _load_registered_type(
                root_dir=self.root_dir,
                registrations=health_registrations,
                artifact_type="m4_v2_marginal_static_measurement_health_result",
            )
            health_completion = _load_registered_type(
                root_dir=self.root_dir,
                registrations=health_registrations,
                artifact_type="m4_v2_marginal_static_health_execution_completion",
            )
            registered_decision = _load_registered_type(
                root_dir=self.root_dir,
                registrations=registrations,
                artifact_type=("m4_v2_marginal_static_measurement_health_decision"),
            )
            reconstructed = build_marginal_static_health_decision(
                source_contract=source_contract,
                health_execution=health_execution,
                health_result=health_result,
                health_completion=health_completion,
            )
            if (
                registered_decision != reconstructed
                or artifact.get(
                    "marginal_static_health_decision_source_contract_digest"
                )
                != source_contract["artifact_digest"]
                or artifact.get("marginal_static_health_decision_source_set_digest")
                != source_contract["source_set_digest"]
                or artifact.get("health_execution_artifact_digest")
                != health_execution["artifact_digest"]
                or artifact.get("health_result_digest")
                != health_result["artifact_digest"]
                or artifact.get("health_completion_digest")
                != health_completion["artifact_digest"]
                or artifact.get("marginal_static_health_decision_artifact_digest")
                != reconstructed["artifact_digest"]
                or artifact.get("decision") != reconstructed["decision"]
                or artifact.get("decision_fact") != reconstructed["decision_fact"]
                or artifact.get("measurement_health") != "REPAIR"
                or artifact.get("failed_cell_ids") != reconstructed["failed_cell_ids"]
                or artifact.get("failed_cell_count") != 4
                or artifact.get("eligible_for_historical_measurement") is not False
                or artifact.get("statistical_results_read") is not True
                or artifact.get("generated_issues") != 0
                or artifact.get("compact_index_reads") != 0
                or artifact.get("sentinel_replicates_recomputed") != 0
                or artifact.get("duplicate_validation") is not False
                or artifact.get("historical_outcomes_read") is not False
                or artifact.get("evidence_created") is not False
                or artifact.get("promotion_gate_opened") is not False
                or artifact.get("repair_required") is not True
                or artifact.get("downstream_consumer")
                != MARGINAL_STATIC_REPAIR_DESIGN_TASK_KEY
                or artifact.get("production_action") != "none"
            ):
                raise MainlineSupervisorError(
                    "M4 v2 marginal-static health decision replay identity changed"
                )
            _verify_v2_registered_artifacts(
                root_dir=self.root_dir,
                registrations=registrations,
                expected_payloads=(reconstructed, artifact),
            )
            capability_replay = {
                "schema_version": (
                    "dehps-m4-v2-marginal-static-health-decision-replay.v1"
                ),
                "status": "REPLAY_VERIFIED",
                "decision_artifact_digest": reconstructed["artifact_digest"],
                "measurement_health": reconstructed["measurement_health"],
                "decision": reconstructed["decision"],
                "decision_fact": reconstructed["decision_fact"],
                "failed_cell_ids": reconstructed["failed_cell_ids"],
                "failed_cell_count": reconstructed["failed_cell_count"],
                "same_registered_content": True,
                "decision_only": True,
                "generated_issues_during_replay": 0,
                "compact_index_reads": 0,
                "sentinel_replicates_recomputed": 0,
                "duplicate_validation": False,
                "historical_outcomes_read": False,
                "statistical_results_read": True,
                "evidence_created": False,
                "manual_input_assembly": False,
            }
        elif task_key == MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY:
            source_contract = load_marginal_static_health_execution_source_contract(
                self.root_dir / MARGINAL_STATIC_HEALTH_EXECUTION_SOURCE_CONTRACT_PATH
            )
            verify_marginal_static_health_execution_source_bytes(
                root_dir=self.root_dir,
                contract=source_contract,
            )
            _, design_execution, design_registrations = (
                _load_single_completed_execution(
                    repository=self.repository,
                    root_dir=self.root_dir,
                    control_plane_key=self.control_plane_key,
                    task_key=MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY,
                )
            )
            workload = _load_registered_type(
                root_dir=self.root_dir,
                registrations=design_registrations,
                artifact_type="m4_v2_marginal_static_health_workload",
            )
            inference = _load_registered_type(
                root_dir=self.root_dir,
                registrations=design_registrations,
                artifact_type="m4_v2_marginal_static_health_inference",
            )
            design_completion = _load_registered_type(
                root_dir=self.root_dir,
                registrations=design_registrations,
                artifact_type="m4_v2_marginal_static_health_design_completion",
            )
            index_artifact = _load_registered_type(
                root_dir=self.root_dir,
                registrations=registrations,
                artifact_type="m4_v2_marginal_static_health_completion_index",
            )
            health_result = _load_registered_type(
                root_dir=self.root_dir,
                registrations=registrations,
                artifact_type="m4_v2_marginal_static_measurement_health_result",
            )
            health_completion = _load_registered_type(
                root_dir=self.root_dir,
                registrations=registrations,
                artifact_type="m4_v2_marginal_static_health_execution_completion",
            )
            rebuilt_index, rebuilt_health, rebuilt_completion = (
                rebuild_health_artifacts_from_index(
                    root_dir=self.root_dir,
                    index_artifact=index_artifact,
                    workload_digest=str(workload["artifact_digest"]),
                    inference_digest=str(inference["artifact_digest"]),
                    execution_id=resolved_execution_id,
                    git_commit=str(artifact["git_commit"]),
                )
            )
            specs = build_replicate_specs(
                workload=workload["workload"],
                source_contract_digest=str(source_contract["artifact_digest"]),
            )
            sentinel = run_replicate(specs[0])
            index_path = self.root_dir / str(index_artifact["index_path"])
            first_entry = json.loads(
                index_path.read_text(encoding="utf-8").splitlines()[0]
            )
            if (
                first_entry.get("summary") != sentinel
                or index_artifact != rebuilt_index
                or health_result != rebuilt_health
                or health_completion != rebuilt_completion
                or artifact.get(
                    "marginal_static_health_execution_source_contract_digest"
                )
                != source_contract["artifact_digest"]
                or artifact.get("marginal_static_health_execution_source_set_digest")
                != source_contract["source_set_digest"]
                or artifact.get("design_execution_artifact_digest")
                != design_execution["artifact_digest"]
                or artifact.get("marginal_static_health_workload_digest")
                != workload["artifact_digest"]
                or artifact.get("marginal_static_health_inference_digest")
                != inference["artifact_digest"]
                or artifact.get("marginal_static_health_design_completion_digest")
                != design_completion["artifact_digest"]
                or artifact.get("marginal_static_health_completion_index_digest")
                != rebuilt_index["artifact_digest"]
                or artifact.get("marginal_static_health_result_digest")
                != rebuilt_health["artifact_digest"]
                or artifact.get("marginal_static_health_execution_completion_digest")
                != rebuilt_completion["artifact_digest"]
                or artifact.get("replicate_count") != 7168
                or artifact.get("generated_issues") != 15920128
                or artifact.get("outer_evaluation_issues") != 9468928
                or artifact.get("completion_index_loads") != 1
                or artifact.get("database_reads_during_replicate") != 0
                or artifact.get("database_writes_during_replicate") != 0
                or artifact.get("csv_materialized") is not False
                or artifact.get("duplicate_raw_replay") is not False
                or artifact.get("routine_physical_checkpoint_scan") is not False
                or artifact.get("historical_outcomes_read") is not False
                or artifact.get("statistical_results_read") is not False
                or artifact.get("evidence_created") is not False
                or artifact.get("completion_fact")
                != MARGINAL_STATIC_HEALTH_EXECUTION_COMPLETION_FACT
                or artifact.get("downstream_consumer")
                != MARGINAL_STATIC_HEALTH_DECISION_TASK_KEY
            ):
                raise MainlineSupervisorError(
                    "M4 v2 marginal-static health execution replay identity changed"
                )
            _verify_v2_registered_artifacts(
                root_dir=self.root_dir,
                registrations=registrations,
                expected_payloads=(
                    rebuilt_index,
                    rebuilt_health,
                    rebuilt_completion,
                    artifact,
                ),
            )
            capability_replay = {
                "schema_version": (
                    "dehps-m4-v2-marginal-static-health-execution-replay.v1"
                ),
                "status": "REPLAY_VERIFIED",
                "completion_index_digest": rebuilt_index["artifact_digest"],
                "health_result_digest": rebuilt_health["artifact_digest"],
                "completion_digest": rebuilt_completion["artifact_digest"],
                "measurement_health": rebuilt_health["measurement_health"],
                "aggregate_rebuilt_from_compact_index": True,
                "sentinel_replicates_recomputed": 1,
                "same_registered_content": True,
                "replicate_count": 7168,
                "generated_issues_during_replay": 961,
                "historical_outcomes_read": False,
                "statistical_results_read": False,
                "evidence_created": False,
                "duplicate_raw_replay": False,
                "routine_physical_checkpoint_scan": False,
                "manual_input_assembly": False,
            }
        elif task_key == MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY:
            source_contract = load_marginal_static_health_design_source_contract(
                self.root_dir / MARGINAL_STATIC_HEALTH_DESIGN_SOURCE_CONTRACT_PATH
            )
            verify_marginal_static_health_design_source_bytes(
                root_dir=self.root_dir,
                contract=source_contract,
            )
            _, fixture_execution, fixture_registrations = (
                _load_single_completed_execution(
                    repository=self.repository,
                    root_dir=self.root_dir,
                    control_plane_key=self.control_plane_key,
                    task_key=MARGINAL_STATIC_FIXTURE_FREEZE_TASK_KEY,
                )
            )
            fixture_contracts = _ordered_marginal_static_fixture_contracts(
                _load_registered_type_group(
                    root_dir=self.root_dir,
                    registrations=fixture_registrations,
                    artifact_type="m4_v2_marginal_static_measurement_fixture",
                )
            )
            fixture_bundle = _load_registered_type(
                root_dir=self.root_dir,
                registrations=fixture_registrations,
                artifact_type="m4_v2_marginal_static_fixture_bundle",
            )
            fixture_completion = _load_registered_type(
                root_dir=self.root_dir,
                registrations=fixture_registrations,
                artifact_type=("m4_v2_marginal_static_fixture_freeze_completion"),
            )
            reconstructed = build_marginal_static_health_design_artifacts(
                source_contract=source_contract,
                fixture_execution_artifact_digest=str(
                    fixture_execution["artifact_digest"]
                ),
                fixture_contracts=fixture_contracts,
                fixture_bundle=fixture_bundle,
                fixture_completion=fixture_completion,
                execution_id=resolved_execution_id,
                git_commit=str(artifact["git_commit"]),
            )
            fixture_digests = [item["artifact_digest"] for item in fixture_contracts]
            if (
                artifact.get("marginal_static_health_design_source_contract_digest")
                != source_contract["artifact_digest"]
                or artifact.get("marginal_static_health_design_source_set_digest")
                != source_contract["source_set_digest"]
                or artifact.get("fixture_execution_artifact_digest")
                != fixture_execution["artifact_digest"]
                or artifact.get("marginal_static_fixture_digests") != fixture_digests
                or artifact.get("marginal_static_fixture_bundle_digest")
                != fixture_bundle["artifact_digest"]
                or artifact.get("marginal_static_fixture_completion_digest")
                != fixture_completion["artifact_digest"]
                or artifact.get("marginal_static_health_workload_digest")
                != reconstructed.workload["artifact_digest"]
                or artifact.get("marginal_static_health_inference_digest")
                != reconstructed.inference["artifact_digest"]
                or artifact.get("marginal_static_health_design_completion_digest")
                != reconstructed.completion["artifact_digest"]
                or artifact.get("planned_total_replicates") != 7168
                or artifact.get("planned_total_generated_issues") != 15920128
                or artifact.get("planned_total_outer_evaluation_issues") != 9468928
                or artifact.get("planned_execution_shards") != 112
                or artifact.get("execution_shard_size") != 64
                or artifact.get("bootstrap_replicates_per_interval") != 511
                or artifact.get("primary_block_size") != 5
                or artifact.get("sensitivity_block_sizes") != [3, 8, 13]
                or artifact.get("legacy_probe_fits_reused") is not False
                or artifact.get("legacy_results_reused") is not False
                or artifact.get("sampled_workload_status") != "FROZEN_NOT_EXECUTED"
                or artifact.get("database_reads_during_replicate") != 0
                or artifact.get("database_writes_during_replicate") != 0
                or artifact.get("csv_materialized") is not False
                or artifact.get("duplicate_raw_replay") is not False
                or artifact.get("routine_physical_checkpoint_scan") is not False
                or artifact.get("generated_issues") != 0
                or artifact.get("synthetic_replicates") != 0
                or artifact.get("bootstrap_replicates_executed") != 0
                or artifact.get("historical_outcomes_read") is not False
                or artifact.get("p2_6_3_statistical_results_read") is not False
                or artifact.get("evidence_created") is not False
            ):
                raise MainlineSupervisorError(
                    "M4 v2 marginal-static health-design replay identity changed"
                )
            _verify_v2_registered_artifacts(
                root_dir=self.root_dir,
                registrations=registrations,
                expected_payloads=(*reconstructed.artifacts, artifact),
            )
            capability_replay = {
                "schema_version": (
                    "dehps-m4-v2-marginal-static-health-design-replay.v1"
                ),
                "status": "REPLAY_VERIFIED",
                "workload_digest": reconstructed.workload["artifact_digest"],
                "inference_digest": reconstructed.inference["artifact_digest"],
                "completion_digest": reconstructed.completion["artifact_digest"],
                "planned_total_replicates": 7168,
                "planned_total_generated_issues": 15920128,
                "planned_total_outer_evaluation_issues": 9468928,
                "planned_execution_shards": 112,
                "same_registered_content": True,
                "generated_issues": 0,
                "synthetic_replicates": 0,
                "bootstrap_replicates_executed": 0,
                "historical_outcomes_read": False,
                "statistical_results_read": False,
                "evidence_created": False,
                "duplicate_raw_replay": False,
                "routine_physical_checkpoint_scan": False,
                "manual_input_assembly": False,
            }
        elif task_key == MARGINAL_STATIC_CONTRACT_FREEZE_TASK_KEY:
            source_contract = load_marginal_static_source_contract(
                self.root_dir / MARGINAL_STATIC_SOURCE_CONTRACT_PATH
            )
            verify_marginal_static_source_bytes(
                root_dir=self.root_dir,
                contract=source_contract,
            )
            _, preflight_execution, preflight_registrations = (
                _load_single_completed_execution(
                    repository=self.repository,
                    root_dir=self.root_dir,
                    control_plane_key=self.control_plane_key,
                    task_key=PREFLIGHT_EXECUTION_TASK_KEY,
                )
            )
            branch_health = next(
                item
                for item in _load_registered_type_group(
                    root_dir=self.root_dir,
                    registrations=preflight_registrations,
                    artifact_type="m4_v2_branch_health_preflight_result",
                )
                if item.get("branch_id") == "MARGINAL_STATIC"
            )
            preflight_completion = _load_registered_type(
                root_dir=self.root_dir,
                registrations=preflight_registrations,
                artifact_type="m4_v2_branch_preflight_execution_completion",
            )
            _, _, design_registrations = _load_single_completed_execution(
                repository=self.repository,
                root_dir=self.root_dir,
                control_plane_key=self.control_plane_key,
                task_key=PREFLIGHT_DESIGN_TASK_KEY,
            )
            marginal_design = next(
                item
                for item in _load_registered_type_group(
                    root_dir=self.root_dir,
                    registrations=design_registrations,
                    artifact_type=("m4_v2_branch_identifiability_preflight_design"),
                )
                if item.get("branch_id") == "MARGINAL_STATIC"
            )
            _, _, binding_registrations = _load_single_completed_execution(
                repository=self.repository,
                root_dir=self.root_dir,
                control_plane_key=self.control_plane_key,
                task_key=M4_V2_MARGINAL_BINDING_TASK_KEY,
            )
            legacy_decision = _load_registered_type(
                root_dir=self.root_dir,
                registrations=binding_registrations,
                artifact_type="marginal_measurement_acceptance_decision",
            )
            _, _, replay_registrations = _load_single_completed_execution(
                repository=self.repository,
                root_dir=self.root_dir,
                control_plane_key=self.control_plane_key,
                task_key=M4_V2_MARGINAL_DECISION_REPLAY_TASK_KEY,
            )
            legacy_replay = _load_registered_type(
                root_dir=self.root_dir,
                registrations=replay_registrations,
                artifact_type="branch_decision_replay_attestation",
            )
            reconstructed = build_marginal_static_contract_artifacts(
                source_contract=source_contract,
                measurement_contract_v2_digest=MEASUREMENT_CONTRACT_V2_DIGEST,
                marginal_branch_design=marginal_design,
                preflight_execution_artifact_digest=str(
                    preflight_execution["artifact_digest"]
                ),
                marginal_branch_health=branch_health,
                preflight_completion=preflight_completion,
                legacy_marginal_decision=legacy_decision,
                legacy_decision_replay=legacy_replay,
                execution_id=resolved_execution_id,
                git_commit=str(artifact["git_commit"]),
            )
            if (
                artifact.get("marginal_static_source_contract_digest")
                != source_contract["artifact_digest"]
                or artifact.get("marginal_static_source_set_digest")
                != source_contract["source_set_digest"]
                or artifact.get("preflight_execution_artifact_digest")
                != preflight_execution["artifact_digest"]
                or artifact.get("marginal_branch_design_digest")
                != marginal_design["artifact_digest"]
                or artifact.get("marginal_branch_health_digest")
                != branch_health["artifact_digest"]
                or artifact.get("preflight_execution_completion_digest")
                != preflight_completion["artifact_digest"]
                or artifact.get("legacy_marginal_decision_digest")
                != legacy_decision["artifact_digest"]
                or artifact.get("legacy_decision_replay_digest")
                != legacy_replay["artifact_digest"]
                or artifact.get("marginal_static_measurement_contract_digest")
                != reconstructed.measurement_contract["artifact_digest"]
                or artifact.get("marginal_static_contract_completion_digest")
                != reconstructed.completion["artifact_digest"]
                or artifact.get("identifiability_preflight_status") != "PASS"
                or artifact.get("legacy_measurement_health") != "REPAIR"
                or artifact.get("legacy_repair_overridden") is not False
                or artifact.get("accepted_model_artifact_digest") is not None
                or artifact.get("sampled_synthetic_execution_status")
                != "NOT_AUTHORIZED"
                or artifact.get("historical_execution_status") != "NOT_AUTHORIZED"
                or artifact.get("formal_branch_runs_executed") != 0
                or artifact.get("synthetic_replicates") != 0
                or artifact.get("historical_outcomes_read") is not False
                or artifact.get("p2_6_3_statistical_results_read") is not False
                or artifact.get("evidence_created") is not False
            ):
                raise MainlineSupervisorError(
                    "M4 v2 marginal-static contract replay identity changed"
                )
            _verify_v2_registered_artifacts(
                root_dir=self.root_dir,
                registrations=registrations,
                expected_payloads=(*reconstructed.artifacts, artifact),
            )
            capability_replay = {
                "schema_version": (
                    "dehps-m4-v2-marginal-static-contract-freeze-replay.v1"
                ),
                "status": "REPLAY_VERIFIED",
                "marginal_static_measurement_contract_digest": (
                    reconstructed.measurement_contract["artifact_digest"]
                ),
                "marginal_static_contract_completion_digest": (
                    reconstructed.completion["artifact_digest"]
                ),
                "estimator_id": "EXPANDING_LEGAL_MARGINAL_ALPHA_1",
                "identifiability_preflight_status": "PASS",
                "legacy_measurement_health": "REPAIR",
                "legacy_repair_overridden": False,
                "accepted_model_artifact_digest": None,
                "sampled_synthetic_execution_status": "NOT_AUTHORIZED",
                "historical_execution_status": "NOT_AUTHORIZED",
                "same_registered_content": True,
                "formal_branch_runs_executed": 0,
                "synthetic_replicates": 0,
                "historical_outcomes_read": False,
                "statistical_results_read": False,
                "evidence_created": False,
                "manual_input_assembly": False,
            }
        elif task_key == P26_REPAIR_TASK_KEY:
            repair = run_measurement_contract_repair(
                root_dir=self.root_dir,
                execution_id=resolved_execution_id,
                git_commit=str(artifact["git_commit"]),
            )
            if (
                repair.completion["artifact_digest"]
                != artifact["completion_artifact_digest"]
                or repair.development_selection["artifact_digest"]
                != artifact["development_selection_artifact_digest"]
                or repair.identifiability_confirmation["artifact_digest"]
                != artifact["identifiability_confirmation_digest"]
                or [item["artifact_digest"] for item in repair.truth_artifacts]
                != artifact["truth_artifact_digests"]
            ):
                raise MainlineSupervisorError(
                    "measurement repair deterministic replay changed"
                )
            capability_replay = {
                "schema_version": ("dehps-m4-p2-measurement-repair-replay.v1"),
                "status": "REPLAY_VERIFIED",
                "completion_artifact_digest": repair.completion["artifact_digest"],
                "development_selection_artifact_digest": (
                    repair.development_selection["artifact_digest"]
                ),
                "truth_artifact_count": len(repair.truth_artifacts),
                "same_contract_identity": True,
                "same_development_selection": True,
                "same_truth_identities": True,
                "manual_input_assembly": False,
            }
        elif task_key == P26_TASK_KEY:
            measurement_manifest = load_repaired_measurement_validation_manifest(
                self.root_dir / "configs/research-os/"
                "m4-information-theory-p2-6-1-measurement-validation-v1.json"
            )
            synthetic = load_synthetic_run_manifest(
                self.root_dir / "configs/research-os/"
                "m4-information-theory-p2-synthetic-run-manifest-v1.0.1.json"
            )
            update_policy = load_periodic_refit_contract(
                self.root_dir / "configs/research-os/"
                "m4-information-theory-p2-6-3-periodic-refit-v1.json"
            )
            if (
                artifact.get("measurement_update_policy_digest")
                != update_policy.artifact_digest
            ):
                raise MainlineSupervisorError("P2.6.3 replay update policy changed")
            capability_replay = verify_completion_replay(
                manifest=measurement_manifest,
                synthetic=synthetic,
                parent_execution_id=resolved_execution_id,
                output_dir=artifact_path.parent / "artifacts",
                git_commit=str(artifact["git_commit"]),
                expected_completion_digest=str(artifact["completion_artifact_digest"]),
                expected_update_policy_digest=update_policy.artifact_digest,
            )
        elif task_key == P27_TASK_KEY:
            measurement_manifest = load_repaired_measurement_validation_manifest(
                self.root_dir / "configs/research-os/"
                "m4-information-theory-p2-6-1-measurement-validation-v1.json"
            )
            synthetic = load_synthetic_run_manifest(
                self.root_dir / "configs/research-os/"
                "m4-information-theory-p2-synthetic-run-manifest-v1.0.1.json"
            )
            update_policy = load_periodic_refit_contract(
                self.root_dir / "configs/research-os/"
                "m4-information-theory-p2-6-3-periodic-refit-v1.json"
            )
            p26_candidates = [
                (path, _load_object(path))
                for path in (
                    self.root_dir / "runtime/research-os/mainline/tasks" / P26_TASK_KEY
                ).glob("*/execution.json")
            ]
            p26_matches = [
                (path, payload)
                for path, payload in p26_candidates
                if payload.get("artifact_digest")
                == artifact.get("p26_execution_artifact_digest")
            ]
            if len(p26_matches) != 1:
                raise MainlineSupervisorError(
                    "P2.7 replay cannot resolve its unique P2.6 parent"
                )
            p26_path, p26_execution = p26_matches[0]
            p26_output = p26_path.parent / "artifacts"
            completion = _load_object(
                self.root_dir / str(p26_execution["completion_artifact_path"])
            )
            completion_replay = verify_completion_replay(
                manifest=measurement_manifest,
                synthetic=synthetic,
                parent_execution_id=str(p26_execution["execution_id"]),
                output_dir=p26_output,
                git_commit=str(p26_execution["git_commit"]),
                expected_completion_digest=str(
                    p26_execution["completion_artifact_digest"]
                ),
                expected_update_policy_digest=update_policy.artifact_digest,
            )
            aggregates = [
                _load_object(path)
                for path in sorted(p26_output.glob("aggregates/*/*.json"))
            ]
            reconstructed_gate = evaluate_automatic_gate(
                manifest=measurement_manifest,
                completion=completion,
                aggregates=aggregates,
                deterministic_replay_passed=(
                    completion_replay["status"] == "REPLAY_VERIFIED"
                ),
            )
            if (
                reconstructed_gate["artifact_digest"]
                != artifact.get("automatic_gate_digest")
                or reconstructed_gate["mde_summary"]["artifact_digest"]
                != artifact.get("mde_summary_digest")
                or reconstructed_gate["decision"] != artifact.get("decision")
                or reconstructed_gate["decision_fact"] != artifact.get("decision_fact")
            ):
                raise MainlineSupervisorError(
                    "P2.7 automatic gate or MDE replay identity changed"
                )
            capability_replay = {
                "status": "REPLAY_VERIFIED",
                "completion_artifact_digest": completion["artifact_digest"],
                "automatic_gate_digest": reconstructed_gate["artifact_digest"],
                "mde_summary_digest": reconstructed_gate["mde_summary"][
                    "artifact_digest"
                ],
                "decision": reconstructed_gate["decision"],
                "decision_fact": reconstructed_gate["decision_fact"],
                "manual_input_assembly": False,
            }
        payload = {
            "schema_version": "dehps-research-evidence-supervisor-replay.v1",
            "status": "REPLAY_VERIFIED",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "control_plane_key": self.control_plane_key,
            "task_key": task_key,
            "execution_id": resolved_execution_id,
            "execution_artifact_digest": artifact["artifact_digest"],
            "actual_fold_count": artifact["actual_fold_count"],
            "registered_artifact_count": len(registrations),
            "same_execution_identity": True,
            "same_artifact_identity": True,
            "manual_input_assembly": False,
            "dispatch_performed": False,
        }
        if capability_replay is not None:
            payload["capability_replay"] = capability_replay
        self._write_state(payload)
        return payload

    def status(self) -> dict[str, Any]:
        if self.state_path.is_file():
            payload = _load_object(self.state_path)
            relative = payload.get("progress_projection_path")
            if payload.get("status") == "RUNNING" and isinstance(relative, str):
                progress_path = (self.root_dir / relative).resolve()
                if progress_path.is_relative_to(self.root_dir.resolve()) and (
                    progress_path.is_file()
                ):
                    progress = _load_object(progress_path)
                    if progress.get("execution_id") == payload.get(
                        "execution_id"
                    ) and progress.get("task_digest") == payload.get("task_digest"):
                        payload["progress"] = progress
            return payload
        return {
            "schema_version": "dehps-research-evidence-supervisor-state.v1",
            "status": "NOT_STARTED",
            "control_plane_key": self.control_plane_key,
            "dispatch_performed": False,
        }

    def run_resident(self, *, interval_seconds: float = 15.0) -> None:
        if interval_seconds < 1:
            raise ValueError("resident supervisor interval must be at least one second")
        while True:
            try:
                self.run_once()
            except (
                Exception  # noqa: BLE001 - resident service must keep reporting.
            ) as exc:
                payload = {
                    "schema_version": "dehps-research-evidence-supervisor-state.v1",
                    "status": "FAILED",
                    "control_plane_key": self.control_plane_key,
                    "error": str(exc),
                    "dispatch_performed": False,
                    "heartbeat_at": self.now().isoformat(),
                }
                self._write_state(payload)
            time.sleep(interval_seconds)

    def _completed_event(self, execution_id: str) -> dict[str, Any] | None:
        events = self.repository.list_mainline_execution_events(
            control_plane_key=self.control_plane_key,
            execution_id=execution_id,
        )
        completed = [
            event for event in events if event.get("event_type") == "completed"
        ]
        if len(completed) > 1:
            raise MainlineSupervisorError("duplicate completed execution events")
        return None if not completed else completed[0]

    @staticmethod
    def _transition_manifest(
        manifest: ControlPlaneManifest,
        *,
        task_key: str,
        status: TaskStatus,
        classification: CompletionClassification,
        completion_fact: str | None = None,
        completion_facts: tuple[str, ...] = (),
        additional_completed_task_keys: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        payload = manifest.to_dict(include_digest=False)
        found = False
        additional = set(additional_completed_task_keys)
        located_additional: set[str] = set()
        for task in payload["tasks"]:
            if task["task_key"] == task_key:
                found = True
                task["status"] = status.value
                task["completion_classification"] = classification.value
            elif task["task_key"] in additional:
                located_additional.add(str(task["task_key"]))
                task["status"] = TaskStatus.COMPLETED.value
                task["completion_classification"] = (
                    CompletionClassification.COMPLETE.value
                )
        if not found:
            raise ResearchOSValidationError(f"task not found: {task_key}")
        missing_additional = additional - located_additional
        if missing_additional:
            raise ResearchOSValidationError(
                "additional completed tasks not found: "
                + ", ".join(sorted(missing_additional))
            )
        all_facts = set(completion_facts)
        if completion_fact is not None:
            all_facts.add(completion_fact)
        if all_facts:
            facts = set(payload["facts"]["artifacts"])
            facts.update(all_facts)
            payload["facts"]["artifacts"] = sorted(facts)
        return payload

    def _write_state(self, payload: Mapping[str, Any]) -> None:
        atomic_write_text(
            self.state_path,
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        )

    def _build_lane_status(
        self,
        manifest: ControlPlaneManifest,
        *,
        snapshot: Any,
        dispatch_performed: bool,
        completed_summary: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self.control_plane_key == PREDICTION_V2_CONTROL_PLANE_KEY:
            latest = completed_summary or self._latest_completed_summary_for_tasks(
                snapshot,
                (PREDICTION_V2_REPLAY_TASK_KEY, PREDICTION_V2_REFERENCE_TASK_KEY),
            )
            status = build_prediction_v2_status(
                manifest=manifest,
                snapshot=snapshot,
                execution=latest,
                dispatch_performed=dispatch_performed,
            )
            status["progress"] = {
                "engineering_percent": 100 if status["replay_verified"] else 0,
                "evidence_percent": 0,
            }
            return status
        return build_m4_status(
            manifest,
            snapshot=snapshot,
            mainline_execution=self._latest_completed_summary(snapshot),
            measurement_v2_execution=self._latest_completed_v2_summary(snapshot),
            golden_reference_execution=self._latest_completed_summary_for_tasks(
                snapshot,
                (M4_P29_GOLDEN_REFERENCE_TASK_KEY,),
            ),
            runtime_audit_execution=self._latest_completed_summary_for_tasks(
                snapshot,
                (M4_P29_RUNTIME_AUDIT_TASK_KEY,),
            ),
            dispatch_performed=dispatch_performed,
        )

    def _write_lane_status(self, payload: Mapping[str, Any]) -> None:
        status_name = (
            "prediction-v2-shadow-status.json"
            if self.control_plane_key == PREDICTION_V2_CONTROL_PLANE_KEY
            else "m4-information-theory-status.json"
        )
        atomic_write_text(
            self.root_dir / "runtime/logs" / status_name,
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        )
