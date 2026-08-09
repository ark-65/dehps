from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import dehps.research_os.information_theory.measurement_validation.source_integrity as source_integrity_module
import dehps.research_os.supervisor as supervisor_module
import pytest
from dehps.contracts import canonical_digest
from dehps.golden_source_identity import (
    GoldenSourceIdentityError,
    golden_source_identity_from_contract,
    project_golden_source_integrity_contract,
    require_golden_source_compatibility,
)
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory.digest import config_digest
from dehps.research_os.information_theory.measurement_system_v2 import (
    NO_DETECTABLE_INFORMATION,
    P261_FROZEN_FIXTURE_PATH,
    P263_TASK_DIGEST,
    bind_p261_marginal_acceptance,
    build_branch_decision_replay_artifact,
    compile_m4_v2_routing_decision,
    load_gate_replay_fixture,
    load_measurement_compatibility_fixture,
    load_measurement_contract_v2,
    load_p261_marginal_binding_contract,
)
from dehps.research_os.information_theory.measurement_system_v2.compatibility import (
    P263_COMPLETION_ARTIFACT_DIGEST,
    P263_EXECUTION_ARTIFACT_DIGEST,
    P263_EXECUTION_ID,
    P263_POLICY_DIGEST,
)
from dehps.research_os.information_theory.measurement_system_v2.execution import (
    build_design_artifacts,
)
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.information_theory.measurement_system_v2.raw_replay_recovery import (
    FAILED_ERROR,
    FAILED_EXECUTION_ID,
    FAILED_STARTED_EVENT_DIGEST,
    FAILED_TASK_DIGEST,
    FAILED_TERMINAL_EVENT_DIGEST,
    RAW_REPLAY_TASK_KEY,
    RawReplayRecoveryError,
    build_raw_replay_recovery_manifest,
)
from dehps.research_os.information_theory.measurement_system_v2.replay import (
    build_design_replay_artifacts,
    build_p27_gate_replay_artifact,
    build_p261_raw_replay_artifact,
)
from dehps.research_os.information_theory.measurement_system_v2.runtime_audit import (
    P261_RUNTIME_AUDIT_PLAN_PATH,
    P263_INITIAL_RUNTIME_AUDIT_PLAN_PATH,
    RUNTIME_AUDIT_PLAN_PATH,
    UNAVAILABLE,
    AuditedEvaluator,
    RuntimeAuditError,
    RuntimeAuditObserver,
    _io_deltas,
    build_equivalence_attestation,
    load_runtime_audit_plan,
)
from dehps.research_os.information_theory.measurement_system_v2.terminal_guard import (
    EXPECTED_CONTROL_PLANE_KEY,
    EXPECTED_P261_EXECUTION_ID,
    EXPECTED_P261_RECOVERED_FAILED_EVENT_DIGEST,
    EXPECTED_P261_RUNNING_CONTROL_PLANE_MANIFEST_DIGEST,
    EXPECTED_P261_TASK_DIGEST,
    LEGACY_P3_TASK_KEY,
    P27_TASK_KEY,
    P261_TASK_KEY,
    CompletionGuardError,
    GuardDecision,
    evaluate_post_stop_boundary,
    evaluate_terminal_boundary,
    validate_slot_release_guard_artifact,
)
from dehps.research_os.information_theory.measurement_validation import (
    PythonReferenceEvaluation,
    golden_boundary_identity_contract,
)
from dehps.research_os.information_theory.measurement_validation.source_compatibility import (
    P263_REVIEWED_SOURCE_COMPATIBILITY_FIXTURE_PATH,
    P263_REVIEWED_SOURCE_COMPATIBILITY_PATHS,
    REVIEWED_SHARED_COMPATIBILITY_FIXTURE_PATH,
    SourceCompatibilityError,
    load_p263_reviewed_source_compatibility_fixture,
    load_reviewed_shared_compatibility_fixture,
    validate_p263_reviewed_source_compatibility_fixture,
    validate_reviewed_shared_compatibility_fixture,
)
from dehps.research_os.information_theory.measurement_validation.source_integrity import (
    APPROVED_ACCELERATION_SOURCE_PATHS,
    AUDIT_ORCHESTRATION_SOURCE_PATHS,
    BASELINE_GIT_COMMIT,
    INDEPENDENT_ORACLE_SOURCE_PATHS,
    SHARED_FROZEN_SOURCE_PATHS,
    SourceIntegrityError,
    build_source_integrity_attestation,
    construction_source_integrity_identity,
    content_sha256,
    git_blob_sha1,
    golden_source_integrity_identity,
    preflight_source_integrity,
    source_set_digest,
    validate_registered_source_integrity_attestation,
    verify_approved_source_bytes,
)
from dehps.research_os.information_theory.progress import (
    build_m4_status,
    load_m4_manifest,
    manifest_with_external_event,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import (
    ControlPlaneManifest,
    MainlineArtifactRegistration,
    TaskStatus,
)
from dehps.research_os.supervisor import (
    M4MeasurementContractV2DesignCapability,
    M4MeasurementContractV2DesignReplayCapability,
    MainlineSupervisorError,
    _golden_execution_work_counts,
    _GoldenReferenceBundle,
    _prepare_fresh_runtime_audit_attempt,
    _recover_runtime_audit_commit_marker,
    _require_exact_runtime_correctness_replay,
    _validate_golden_boundary_schedule,
)

ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = ROOT / "configs/research-os/m4-measurement-contract-v2.json"
BINDING_PATH = ROOT / "configs/research-os/m4-p2-6-1-marginal-binding-contract-v1.json"
FIXTURE_PATH = (
    ROOT / "configs/research-os/m4-measurement-contract-v2-replay-fixture-v1.json"
)
AUDIT_PATH = ROOT / RUNTIME_AUDIT_PLAN_PATH
MANIFEST_PATH = ROOT / "configs/research-os/m4-information-theory-evidence-v1.json"


def _source_entries(paths: tuple[str, ...]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for relative in paths:
        data = (ROOT / relative).read_bytes()
        entries.append(
            {
                "path": relative,
                "content_sha256": content_sha256(data),
                "git_blob_oid": git_blob_sha1(data),
            }
        )
    return entries


def _current_source_contract() -> dict:
    contract = copy.deepcopy(
        load_runtime_audit_plan(AUDIT_PATH)["source_integrity_contract"]
    )
    entries = _source_entries(AUDIT_ORCHESTRATION_SOURCE_PATHS)
    contract["audit_orchestration_source_allowlist"] = entries
    contract["audit_orchestration_source_set_digest"] = source_set_digest(
        entries,
        kind="audit-orchestration",
    )
    return contract


def test_frozen_sparse_tree_compatibility_fixture_remains_replayable() -> None:
    plan = load_runtime_audit_plan(ROOT / P261_RUNTIME_AUDIT_PLAN_PATH)
    fixture = load_reviewed_shared_compatibility_fixture(
        ROOT / REVIEWED_SHARED_COMPATIBILITY_FIXTURE_PATH
    )
    assert fixture["candidate_golden_source_integrity_identity"] == (
        golden_source_integrity_identity(plan)
    )
    assert (
        validate_reviewed_shared_compatibility_fixture(
            fixture,
            expected_artifact_digest=fixture["artifact_digest"],
            expected_candidate_golden_identity=golden_source_integrity_identity(plan),
        )
        == fixture
    )


def test_p263_source_compatibility_fixture_binds_current_plan() -> None:
    plan = load_runtime_audit_plan(AUDIT_PATH)
    fixture = load_p263_reviewed_source_compatibility_fixture(
        ROOT / P263_REVIEWED_SOURCE_COMPATIBILITY_FIXTURE_PATH
    )
    contract = plan["source_integrity_contract"]

    assert contract["reviewed_shared_compatibility_fixture_path"] == (
        P263_REVIEWED_SOURCE_COMPATIBILITY_FIXTURE_PATH.as_posix()
    )
    assert (
        contract["reviewed_shared_compatibility_fixture_digest"]
        == fixture["artifact_digest"]
    )
    assert fixture["changed_paths"] == list(P263_REVIEWED_SOURCE_COMPATIBILITY_PATHS)
    assert fixture["candidate_source_entries"] == _source_entries(
        P263_REVIEWED_SOURCE_COMPATIBILITY_PATHS
    )
    assert fixture["candidate_golden_source_integrity_identity"] == (
        golden_source_integrity_identity(plan)
    )
    assert (
        validate_p263_reviewed_source_compatibility_fixture(
            fixture,
            expected_artifact_digest=fixture["artifact_digest"],
            expected_candidate_golden_identity=golden_source_integrity_identity(plan),
        )
        == fixture
    )


def test_p263_runtime_plan_is_result_blind_and_strict_prior(tmp_path: Path) -> None:
    initial = load_runtime_audit_plan(ROOT / P263_INITIAL_RUNTIME_AUDIT_PLAN_PATH)
    plan = load_runtime_audit_plan(AUDIT_PATH)

    assert initial["semantic_version"] == "1.1.6"
    assert initial["artifact_digest"] == (
        "ccbed31f36ad9486f5489d5827c6456d1853259eaeb1ab7a61077347c7e06056"
    )
    assert plan["semantic_version"] == "1.1.7"
    assert plan["supersedes_artifact_digest"] == initial["artifact_digest"]
    assert plan["result_blind_contract"] == {
        "allowed_inputs": [
            "source_identity",
            "synthetic_input_artifact",
            "preregistered_policy",
            "strict_prior_fold_state",
        ],
        "previous_score_read": False,
        "previous_prediction_read": False,
        "previous_ranking_read": False,
        "power_result_read": False,
        "false_positive_result_read": False,
        "bias_rmse_coverage_result_read": False,
        "mde_result_read": False,
        "threshold_selected_from_results": False,
        "historical_outcomes_read": False,
    }
    assert plan["periodic_refit_temporal_contract"] == {
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

    tampered = copy.deepcopy(plan)
    tampered["result_blind_contract"]["power_result_read"] = True
    tampered["artifact_digest"] = config_digest(tampered)
    temporary = tmp_path / "tampered-runtime-plan.json"
    temporary.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(RuntimeAuditError, match="oracle policy changed"):
        load_runtime_audit_plan(temporary)


def test_reviewed_sparse_tree_compatibility_fixture_rejects_semantic_tamper() -> None:
    fixture = load_reviewed_shared_compatibility_fixture(
        ROOT / REVIEWED_SHARED_COMPATIBILITY_FIXTURE_PATH
    )
    tampered = copy.deepcopy(fixture)
    tampered["exact_replay"]["probability_bits_exact"] = False
    tampered["artifact_digest"] = canonical_digest(
        {key: value for key, value in tampered.items() if key != "artifact_digest"},
        domain="dehps.m4-information-theory.config.v1",
    )

    with pytest.raises(
        SourceCompatibilityError,
        match="shared_compatibility_replay_changed",
    ):
        validate_reviewed_shared_compatibility_fixture(tampered)


def _mutate_source_set(
    contract: dict,
    *,
    allowlist_field: str,
    digest_field: str,
    kind: str,
) -> dict:
    mutated = copy.deepcopy(contract)
    entries = mutated[allowlist_field]
    entries[0]["content_sha256"] = "a" * 64
    entries[0]["git_blob_oid"] = "b" * 40
    mutated[digest_field] = source_set_digest(entries, kind=kind)
    return mutated


def test_golden_source_identity_supports_only_acceleration_or_audit_reuse() -> None:
    source_contract = _current_source_contract()
    runtime_plan = {"source_integrity_contract": source_contract}
    construction_identity = construction_source_integrity_identity(runtime_plan)
    golden_contract = project_golden_source_integrity_contract(source_contract)
    golden_identity = golden_source_identity_from_contract(golden_contract)

    for allowlist, digest, kind in (
        (
            "approved_acceleration_source_allowlist",
            "approved_acceleration_source_set_digest",
            "approved-acceleration",
        ),
        (
            "audit_orchestration_source_allowlist",
            "audit_orchestration_source_set_digest",
            "audit-orchestration",
        ),
    ):
        changed = _mutate_source_set(
            source_contract,
            allowlist_field=allowlist,
            digest_field=digest,
            kind=kind,
        )
        assert (
            construction_source_integrity_identity(
                {"source_integrity_contract": changed}
            )
            != construction_identity
        )
        assert project_golden_source_integrity_contract(changed) == golden_contract
        assert (
            require_golden_source_compatibility(
                registered_golden_contract=golden_contract,
                registered_golden_identity=golden_identity,
                new_full_source_contract=changed,
            )
            == golden_identity
        )


@pytest.mark.parametrize(
    ("allowlist", "digest", "kind"),
    [
        (
            "shared_frozen_source_allowlist",
            "shared_frozen_source_set_digest",
            "shared-frozen",
        ),
        (
            "independent_oracle_source_allowlist",
            "independent_oracle_source_set_digest",
            "independent-oracle",
        ),
    ],
)
def test_golden_source_identity_rejects_shared_or_oracle_drift(
    allowlist: str,
    digest: str,
    kind: str,
) -> None:
    source_contract = _current_source_contract()
    golden_contract = project_golden_source_integrity_contract(source_contract)
    golden_identity = golden_source_identity_from_contract(golden_contract)
    changed = _mutate_source_set(
        source_contract,
        allowlist_field=allowlist,
        digest_field=digest,
        kind=kind,
    )
    with pytest.raises(GoldenSourceIdentityError):
        require_golden_source_compatibility(
            registered_golden_contract=golden_contract,
            registered_golden_identity=golden_identity,
            new_full_source_contract=changed,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("baseline_git_commit", "1" * 40),
        ("shared_change_policy", "ALLOW"),
        ("oracle_change_policy", "ALLOW"),
    ],
)
def test_golden_source_identity_rejects_baseline_or_policy_drift(
    field: str,
    value: str,
) -> None:
    source_contract = _current_source_contract()
    source_contract[field] = value
    with pytest.raises(GoldenSourceIdentityError):
        project_golden_source_integrity_contract(source_contract)


def test_golden_source_projector_fresh_import_closure_is_minimal() -> None:
    code = """
import json
import pathlib
import sys
import dehps.golden_source_identity
root = pathlib.Path(sys.argv[1]).resolve()
loaded = []
for module in tuple(sys.modules.values()):
    raw = getattr(module, "__file__", None)
    if not raw:
        continue
    path = pathlib.Path(raw).resolve()
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        continue
    if relative.startswith("apps/worker-python/dehps/") and relative.endswith(".py"):
        loaded.append(relative)
print(json.dumps(sorted(set(loaded))))
"""
    completed = subprocess.run(
        [sys.executable, "-c", code, str(ROOT)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout) == [
        "apps/worker-python/dehps/__init__.py",
        "apps/worker-python/dehps/contracts/__init__.py",
        "apps/worker-python/dehps/contracts/core.py",
        "apps/worker-python/dehps/golden_source_identity.py",
    ]


def test_golden_reference_fresh_import_closure_is_fully_golden_bound() -> None:
    code = """
import json
import pathlib
import sys
import dehps.research_os.information_theory.measurement_validation.golden_reference
root = pathlib.Path(sys.argv[1]).resolve()
loaded = []
for module in tuple(sys.modules.values()):
    raw = getattr(module, "__file__", None)
    if not raw:
        continue
    path = pathlib.Path(raw).resolve()
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        continue
    if relative.startswith("apps/worker-python/dehps/") and relative.endswith(".py"):
        loaded.append(relative)
print(json.dumps(sorted(set(loaded))))
"""
    completed = subprocess.run(
        [sys.executable, "-c", code, str(ROOT)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    loaded = set(json.loads(completed.stdout))
    shared = set(SHARED_FROZEN_SOURCE_PATHS)
    oracle = set(INDEPENDENT_ORACLE_SOURCE_PATHS)
    acceleration = set(APPROVED_ACCELERATION_SOURCE_PATHS)
    audit = set(AUDIT_ORCHESTRATION_SOURCE_PATHS)
    assert loaded <= shared | oracle
    assert loaded.isdisjoint(acceleration)
    assert loaded.isdisjoint(audit)
    assert (
        "apps/worker-python/dehps/research_os/information_theory/"
        "probes/runtime_cache.py"
    ) in loaded
    assert (
        "apps/worker-python/dehps/research_os/information_theory/"
        "probes/runtime_cache_backend.py"
    ) not in loaded


def test_source_partition_covers_worker_python_and_operational_entrypoints() -> None:
    shared = set(SHARED_FROZEN_SOURCE_PATHS)
    acceleration = set(APPROVED_ACCELERATION_SOURCE_PATHS)
    oracle = set(INDEPENDENT_ORACLE_SOURCE_PATHS)
    audit = set(AUDIT_ORCHESTRATION_SOURCE_PATHS)
    assert (len(shared), len(acceleration), len(oracle), len(audit)) == (
        65,
        4,
        11,
        407,
    )
    assert not shared & acceleration
    assert not shared & oracle
    assert not shared & audit
    assert not acceleration & oracle
    assert not acceleration & audit
    assert not oracle & audit
    classified = shared | acceleration | oracle | audit
    assert len(classified) == 487
    worker_python = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "apps/worker-python/dehps").rglob("*.py")
    }
    assert worker_python <= classified
    assert (
        "apps/worker-python/scripts/run_research_evidence_supervisor.py" in classified
    )
    assert "infra/systemd/dehps-research-evidence-supervisor.service" in classified
    unit = (
        ROOT / "infra/systemd/dehps-research-evidence-supervisor.service"
    ).read_text(encoding="utf-8")
    assert "Environment=PYTHONHASHSEED=0" in unit.splitlines()


@pytest.mark.parametrize(
    ("path", "error_prefix"),
    [
        (SHARED_FROZEN_SOURCE_PATHS[0], "shared_frozen_source_modified"),
        (
            APPROVED_ACCELERATION_SOURCE_PATHS[0],
            "approved_acceleration_source_modified",
        ),
        (
            INDEPENDENT_ORACLE_SOURCE_PATHS[0],
            "independent_oracle_source_modified",
        ),
        (
            AUDIT_ORCHESTRATION_SOURCE_PATHS[0],
            "audit_orchestration_source_modified",
        ),
    ],
)
def test_source_preflight_rejects_actual_byte_tamper(
    path: str,
    error_prefix: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = _current_source_contract()
    plan = {
        "artifact_digest": "1" * 64,
        "source_integrity_contract": contract,
    }
    original_read_bytes = Path.read_bytes
    target = (ROOT / path).resolve()
    baseline_compatibility_bytes = {
        compatibility_path: subprocess.run(
            (
                "git",
                "show",
                f"{BASELINE_GIT_COMMIT}:{compatibility_path}",
            ),
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        for compatibility_path in P263_REVIEWED_SOURCE_COMPATIBILITY_PATHS
    }

    def read_bytes_with_tamper(candidate: Path) -> bytes:
        value = original_read_bytes(candidate)
        return value + b"tamper" if candidate.resolve() == target else value

    monkeypatch.setattr(Path, "read_bytes", read_bytes_with_tamper)
    monkeypatch.setattr(
        source_integrity_module,
        "_baseline_bytes",
        lambda root_dir, *, commit, path: baseline_compatibility_bytes.get(
            path, original_read_bytes(ROOT / path)
        ),
    )

    def fake_git(root_dir: Path, *args: str) -> bytes:
        if args == ("rev-parse", "--show-object-format"):
            return b"sha1\n"
        if args[:4] == ("ls-tree", "-z", "--name-only", BASELINE_GIT_COMMIT):
            candidate = args[-1]
            if candidate.endswith("/probes/runtime_cache_backend.py"):
                return b""
            return candidate.encode("utf-8") + b"\0"
        raise AssertionError(f"unexpected git invocation: {args!r}")

    monkeypatch.setattr(
        source_integrity_module,
        "_run_git",
        fake_git,
    )
    with pytest.raises(SourceIntegrityError, match=f"{error_prefix}:{path}"):
        preflight_source_integrity(root_dir=ROOT, runtime_plan=plan)


def test_source_preflight_rejects_p263_candidate_byte_tamper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = P263_REVIEWED_SOURCE_COMPATIBILITY_PATHS[0]
    plan = {
        "artifact_digest": "1" * 64,
        "source_integrity_contract": _current_source_contract(),
    }
    original_read_bytes = Path.read_bytes
    target = (ROOT / path).resolve()

    def read_bytes_with_tamper(candidate: Path) -> bytes:
        value = original_read_bytes(candidate)
        return value + b"candidate-tamper" if candidate.resolve() == target else value

    monkeypatch.setattr(Path, "read_bytes", read_bytes_with_tamper)
    with pytest.raises(
        SourceIntegrityError,
        match=f"shared_frozen_source_modified:{path}",
    ):
        preflight_source_integrity(root_dir=ROOT, runtime_plan=plan)


def test_source_preflight_accepts_new_acceleration_path_absent_at_baseline() -> None:
    added_path = (
        "apps/worker-python/dehps/research_os/information_theory/"
        "probes/runtime_cache_backend.py"
    )
    listing = subprocess.run(
        (
            "git",
            "ls-tree",
            "-z",
            "--name-only",
            BASELINE_GIT_COMMIT,
            "--",
            added_path,
        ),
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    assert listing.stdout == b""

    plan = {
        "artifact_digest": "1" * 64,
        "source_integrity_contract": _current_source_contract(),
    }
    verified = verify_approved_source_bytes(root_dir=ROOT, runtime_plan=plan)
    assert added_path in verified["acceleration_changed_paths"]
    assert preflight_source_integrity(root_dir=ROOT, runtime_plan=plan) == (
        construction_source_integrity_identity(plan)
    )


def test_source_attestation_rejects_execution_commit_byte_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = _current_source_contract()
    plan = {
        "artifact_digest": "1" * 64,
        "source_integrity_contract": contract,
    }
    git_commit = "2" * 40
    target = AUDIT_ORCHESTRATION_SOURCE_PATHS[0]
    baseline_compatibility_bytes = {
        compatibility_path: subprocess.run(
            (
                "git",
                "show",
                f"{BASELINE_GIT_COMMIT}:{compatibility_path}",
            ),
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        for compatibility_path in P263_REVIEWED_SOURCE_COMPATIBILITY_PATHS
    }

    def fake_git(root_dir: Path, *args: str) -> bytes:
        if args == ("rev-parse", "HEAD"):
            return f"{git_commit}\n".encode()
        if args == ("rev-parse", "--show-object-format"):
            return b"sha1\n"
        return b""

    def fake_commit_bytes(root_dir: Path, *, commit: str, path: str) -> bytes:
        if commit == BASELINE_GIT_COMMIT and path in baseline_compatibility_bytes:
            return baseline_compatibility_bytes[path]
        value = (ROOT / path).read_bytes()
        if commit == git_commit and path == target:
            return value + b"commit-drift"
        return value

    monkeypatch.setattr(source_integrity_module, "_run_git", fake_git)
    monkeypatch.setattr(
        source_integrity_module,
        "_baseline_bytes",
        fake_commit_bytes,
    )
    with pytest.raises(
        SourceIntegrityError,
        match=f"audit_orchestration_source_modified:{target}",
    ):
        build_source_integrity_attestation(
            root_dir=ROOT,
            runtime_plan=plan,
            execution_id="3" * 64,
            git_commit=git_commit,
            exact_fixture_replay_artifact_digest="4" * 64,
        )


def test_historical_source_attestation_rejects_self_digested_shape_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = _current_source_contract()
    plan = {
        "artifact_digest": "1" * 64,
        "source_integrity_contract": contract,
    }
    monkeypatch.setattr(
        source_integrity_module,
        "verify_approved_source_bytes",
        lambda **_kwargs: {
            "contract": contract,
            "baseline_git_commit": BASELINE_GIT_COMMIT,
            "acceleration_changed_paths": [],
        },
    )
    payload = build_source_integrity_attestation(
        root_dir=ROOT,
        runtime_plan=plan,
        execution_id="2" * 64,
        git_commit="3" * 40,
        exact_fixture_replay_artifact_digest="4" * 64,
        golden_reference_execution_artifact_digest="5" * 64,
    )
    construction_identity = construction_source_integrity_identity(plan)
    golden_contract = project_golden_source_integrity_contract(contract)
    golden_identity = golden_source_identity_from_contract(golden_contract)
    validate_registered_source_integrity_attestation(
        payload,
        source_runtime_audit_plan_digest="1" * 64,
        construction_source_identity=construction_identity,
        golden_source_identity=golden_identity,
        execution_id="2" * 64,
        git_commit="3" * 40,
        baseline_git_commit=BASELINE_GIT_COMMIT,
        exact_fixture_replay_artifact_digest="4" * 64,
        golden_reference_execution_artifact_digest="5" * 64,
    )

    tampered = copy.deepcopy(payload)
    tampered["unexpected_semantic_extension"] = True
    tampered["artifact_digest"] = canonical_digest(
        {key: value for key, value in tampered.items() if key != "artifact_digest"},
        domain="dehps.m4.p2-9.source-integrity-attestation.v1",
    )
    with pytest.raises(
        SourceIntegrityError,
        match="registered_source_integrity_attestation_changed",
    ):
        validate_registered_source_integrity_attestation(
            tampered,
            source_runtime_audit_plan_digest="1" * 64,
            construction_source_identity=construction_identity,
            golden_source_identity=golden_identity,
            execution_id="2" * 64,
            git_commit="3" * 40,
            baseline_git_commit=BASELINE_GIT_COMMIT,
            exact_fixture_replay_artifact_digest="4" * 64,
            golden_reference_execution_artifact_digest="5" * 64,
        )


def test_registered_golden_boundary_schedule_rejects_self_consistent_replacement() -> (
    None
):
    identities = [dict(item) for item in golden_boundary_identity_contract()]
    plan = {
        "boundary_suite": {
            "replicate_index": 0,
            "scales": ["FORWARD_61", "HISTORICAL", "LONG"],
            "mechanisms": [
                "uniform_choose_6_without_replacement_from_33",
                "single_number_conditional_shift",
                "local_temporal_state",
                "pair_conditional_signal",
                "marginal_preserving_conditional_signal",
            ],
            "fold_positions": ["first", "middle", "last"],
            "identity_count": len(identities),
            "identity_schedule_digest": canonical_digest(
                identities,
                domain=("dehps.m4-p2-9.golden-boundary-identity-schedule.v1"),
            ),
            "identities": identities,
        }
    }
    _validate_golden_boundary_schedule(plan)

    tampered = copy.deepcopy(plan)
    tampered_identities = tampered["boundary_suite"]["identities"]
    tampered_identities[0]["test_issue"] += 1
    tampered["boundary_suite"]["identity_schedule_digest"] = canonical_digest(
        tampered_identities,
        domain="dehps.m4-p2-9.golden-boundary-identity-schedule.v1",
    )
    with pytest.raises(
        MainlineSupervisorError,
        match="boundary identity schedule changed",
    ):
        _validate_golden_boundary_schedule(tampered)


def _raw_replay() -> dict:
    return {
        "schema_version": "dehps-m4-p2-6-1-raw-execution-replay.v1",
        "status": "REPLAY_VERIFIED",
        "task_key": P261_TASK_KEY,
        "task_digest": P263_TASK_DIGEST,
        "execution_id": P263_EXECUTION_ID,
        "execution_artifact_digest": "1" * 64,
        "measurement_validation_manifest_digest": (
            "a4e46a434a4b2ef9fe56ed0390d58ca5a45bbad21685b81cb983f7261b3abf58"
        ),
        "completion_artifact_digest": "2" * 64,
        "completion_event_digest": "3" * 64,
        "registered_artifact_count": 31034,
        "same_execution_identity": True,
        "same_artifact_identity": True,
        "manual_input_assembly": False,
    }


def _gate_replay(decision: str = "PASS_TO_P3") -> dict:
    return {
        "schema_version": "dehps-m4-p2-7-gate-replay.v1",
        "status": "REPLAY_VERIFIED",
        "task_key": P27_TASK_KEY,
        "task_digest": "4" * 64,
        "execution_id": "5" * 64,
        "execution_artifact_digest": "6" * 64,
        "parent_p2_6_1_execution_id": P263_EXECUTION_ID,
        "parent_p2_6_1_execution_artifact_digest": "1" * 64,
        "automatic_gate_digest": "7" * 64,
        "decision": decision,
        "decision_fact": f"m4-p2-measurement-decision:{decision}",
        "same_execution_identity": True,
        "same_artifact_identity": True,
        "manual_input_assembly": False,
    }


def test_raw_and_gate_replay_bind_the_completed_p263_superseding_execution() -> None:
    measurement_manifest_digest = (
        "a4e46a434a4b2ef9fe56ed0390d58ca5a45bbad21685b81cb983f7261b3abf58"
    )
    execution = {
        "task_key": P261_TASK_KEY,
        "task_digest": P263_TASK_DIGEST,
        "execution_id": P263_EXECUTION_ID,
        "artifact_digest": P263_EXECUTION_ARTIFACT_DIGEST,
        "completion_artifact_digest": P263_COMPLETION_ARTIFACT_DIGEST,
        "measurement_validation_manifest_digest": measurement_manifest_digest,
        "measurement_update_policy_digest": P263_POLICY_DIGEST,
        "status": "COMPLETE",
    }
    raw = build_p261_raw_replay_artifact(
        execution=execution,
        completion_event={
            "event_type": "completed",
            "execution_id": P263_EXECUTION_ID,
            "event_digest": "a" * 64,
        },
        registrations=[
            {
                "artifact_type": "measurement_validation_completion",
                "artifact_digest": P263_COMPLETION_ARTIFACT_DIGEST,
                "execution_id": P263_EXECUTION_ID,
            }
        ],
        expected_task_key=P261_TASK_KEY,
        expected_task_digest=EXPECTED_P261_TASK_DIGEST,
        expected_execution_id=EXPECTED_P261_EXECUTION_ID,
        expected_manifest_digest=measurement_manifest_digest,
    )
    assert raw["task_digest"] == P263_TASK_DIGEST
    assert raw["execution_id"] == P263_EXECUTION_ID
    assert raw["completion_artifact_digest"] == P263_COMPLETION_ARTIFACT_DIGEST

    gate_execution = {
        "task_key": P27_TASK_KEY,
        "task_digest": "b" * 64,
        "execution_id": "c" * 64,
        "artifact_digest": "d" * 64,
        "p26_execution_artifact_digest": P263_EXECUTION_ARTIFACT_DIGEST,
        "automatic_gate_digest": "e" * 64,
        "decision": "REPAIR_MEASUREMENT_SYSTEM",
        "decision_fact": "m4-p2-measurement-decision:REPAIR_MEASUREMENT_SYSTEM",
    }
    gate = build_p27_gate_replay_artifact(
        execution=gate_execution,
        replay={
            "status": "REPLAY_VERIFIED",
            "capability_replay": {
                "status": "REPLAY_VERIFIED",
                "automatic_gate_digest": gate_execution["automatic_gate_digest"],
                "decision": gate_execution["decision"],
                "decision_fact": gate_execution["decision_fact"],
            },
        },
        parent_p261_execution_id=EXPECTED_P261_EXECUTION_ID,
    )
    assert gate["parent_p2_6_1_execution_id"] == P263_EXECUTION_ID
    assert (
        gate["parent_p2_6_1_execution_artifact_digest"]
        == P263_EXECUTION_ARTIFACT_DIGEST
    )


def test_raw_replay_recovery_resets_only_the_exact_failed_task() -> None:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    payload.pop("manifest_digest")
    target = next(
        task for task in payload["tasks"] if task["task_key"] == RAW_REPLAY_TASK_KEY
    )
    target["status"] = "failed"
    target["completion_classification"] = "INTEGRATED"
    live = ControlPlaneManifest.from_dict(payload)
    live_target = next(
        task for task in live.tasks if task.task_key == RAW_REPLAY_TASK_KEY
    )
    assert live_target.artifact_digest == FAILED_TASK_DIGEST
    events = [
        {
            "task_digest": FAILED_TASK_DIGEST,
            "execution_id": FAILED_EXECUTION_ID,
            "event_type": "started",
            "event_digest": FAILED_STARTED_EVENT_DIGEST,
            "payload": [],
        },
        {
            "task_digest": FAILED_TASK_DIGEST,
            "execution_id": FAILED_EXECUTION_ID,
            "event_type": "failed",
            "event_digest": FAILED_TERMINAL_EVENT_DIGEST,
            "payload": [["error", FAILED_ERROR]],
        },
    ]
    recovered, report = build_raw_replay_recovery_manifest(
        live_payload=live.to_dict(include_digest=True),
        execution_events=events,
    )
    after = ControlPlaneManifest.from_dict(recovered)
    state = after.task_state_by_digest[FAILED_TASK_DIGEST]
    assert state.declared_status is TaskStatus.DRAFT
    assert state.completion_classification.value == "INTEGRATION_PENDING"
    assert report["changed_task_count"] == 1
    assert report["rewritten_event_count"] == 0
    assert report["statistical_result_payloads_read"] is False

    tampered = copy.deepcopy(events)
    tampered[-1]["payload"] = [["error", "different"]]
    with pytest.raises(RawReplayRecoveryError, match="event_history_changed"):
        build_raw_replay_recovery_manifest(
            live_payload=live.to_dict(include_digest=True),
            execution_events=tampered,
        )


@pytest.mark.parametrize(
    ("gate_decision", "health", "eligible"),
    [
        ("PASS_TO_P3", "PASS", True),
        ("REPAIR_MEASUREMENT_SYSTEM", "REPAIR", False),
    ],
)
def test_marginal_binding_maps_only_synthetic_health(
    gate_decision: str,
    health: str,
    eligible: bool,
) -> None:
    contract = load_p261_marginal_binding_contract(BINDING_PATH)
    decision = bind_p261_marginal_acceptance(
        contract,
        raw_replay=_raw_replay(),
        gate_replay=_gate_replay(gate_decision),
    )
    assert decision["measurement_health"] == health
    assert decision["eligible_for_formal_branch_program"] is eligible
    assert decision["historical_evidence"] == "NOT_RUN"
    assert decision["historical_run_status"] == "NOT_RUN"
    assert decision["evidence_progress_increment"] == 0
    assert decision["promotion_gate_opened"] is False


@pytest.mark.parametrize(
    ("raw_mutation", "gate_mutation", "reason"),
    [
        (None, None, "missing_or_nonterminal_raw_execution"),
        (
            {"measurement_validation_manifest_digest": "9" * 64},
            {},
            "task_execution_or_manifest_identity_drift",
        ),
        ({"status": "REPLAY_FAILED"}, {}, "raw_execution_replay_not_verified"),
        (
            {},
            {"parent_p2_6_1_execution_artifact_digest": "8" * 64},
            "wrong_p2_6_1_parent",
        ),
        (
            {"partial_statistics": {"power": 0.9}},
            {},
            "input_contains_non_allowlisted_fields",
        ),
    ],
)
def test_marginal_binding_fails_closed(
    raw_mutation: dict | None,
    gate_mutation: dict | None,
    reason: str,
) -> None:
    contract = load_p261_marginal_binding_contract(BINDING_PATH)
    raw = None if raw_mutation is None else {**_raw_replay(), **raw_mutation}
    gate = {**_gate_replay(), **(gate_mutation or {})}
    decision = bind_p261_marginal_acceptance(
        contract,
        raw_replay=raw,
        gate_replay=gate,
    )
    assert decision["measurement_health"] == "INCONCLUSIVE"
    assert reason in decision["failure_reasons"]
    assert decision["historical_evidence"] == "NOT_RUN"


def test_marginal_decision_replay_is_content_exact() -> None:
    contract = load_p261_marginal_binding_contract(BINDING_PATH)
    decision = bind_p261_marginal_acceptance(
        contract,
        raw_replay=_raw_replay(),
        gate_replay=_gate_replay(),
    )
    replay = build_branch_decision_replay_artifact(
        decision=decision,
        reconstructed_decision=copy.deepcopy(decision),
    )
    assert replay["status"] == "REPLAY_VERIFIED"
    assert replay["historical_evidence"] == "NOT_RUN"
    with pytest.raises(Exception, match="decision content changed"):
        build_branch_decision_replay_artifact(
            decision=decision,
            reconstructed_decision={**decision, "measurement_health": "REPAIR"},
        )


def _routing_gate(
    *,
    coverage: str,
    health: tuple[str, str, str],
    evidence: tuple[str, str, str],
    global_evidence: str = "INCONCLUSIVE",
) -> dict:
    branches = (
        "MARGINAL_STATIC",
        "TEMPORAL_MARGINAL_INCREMENT",
        "JOINT_RESIDUAL_INCREMENT",
    )
    return {
        "schema_version": "dehps-m4-measurement-gate-compiler-output.v2",
        "artifact_type": "hierarchical_measurement_gate_output",
        "artifact_digest": "a" * 64,
        "contract_digest": "b" * 64,
        "global_coverage": coverage,
        "global_evidence": global_evidence,
        "branch_outputs": [
            {
                "branch_id": branch,
                "measurement_health": branch_health,
                "historical_evidence": branch_evidence,
            }
            for branch, branch_health, branch_evidence in zip(
                branches, health, evidence, strict=True
            )
        ],
        "promotion_gate_opened": False,
        "production_action": "none",
    }


@pytest.mark.parametrize(
    ("gate", "route", "router"),
    [
        (
            _routing_gate(
                coverage="FULL",
                health=("PASS", "PASS", "PASS"),
                evidence=("POSITIVE", "NEGATIVE", "NEGATIVE"),
                global_evidence="CANDIDATE_INFORMATION_FOUND",
            ),
            "ADAPTIVE_RESEARCH_ELIGIBLE",
            True,
        ),
        (
            _routing_gate(
                coverage="PARTIAL",
                health=("PASS", "INCONCLUSIVE", "INCONCLUSIVE"),
                evidence=("POSITIVE", "INCONCLUSIVE", "NOT_RUN"),
                global_evidence="CANDIDATE_INFORMATION_FOUND",
            ),
            "DEEPER_VALIDATION_REQUIRED",
            False,
        ),
        (
            _routing_gate(
                coverage="FULL",
                health=("PASS", "PASS", "PASS"),
                evidence=("NEGATIVE", "NEGATIVE", "NEGATIVE"),
                global_evidence="NO_DETECTABLE_INFORMATION",
            ),
            NO_DETECTABLE_INFORMATION,
            False,
        ),
        (
            _routing_gate(
                coverage="PARTIAL",
                health=("REPAIR", "INCONCLUSIVE", "INCONCLUSIVE"),
                evidence=("NOT_RUN", "NOT_RUN", "NOT_RUN"),
            ),
            "MEASUREMENT_REPAIR_REQUIRED",
            False,
        ),
        (
            _routing_gate(
                coverage="PARTIAL",
                health=("PASS", "PASS", "INCONCLUSIVE"),
                evidence=("NEGATIVE", "INCONCLUSIVE", "NOT_RUN"),
            ),
            "DEEPER_VALIDATION_REQUIRED",
            False,
        ),
    ],
)
def test_global_routing_requires_full_coverage(
    gate: dict,
    route: str,
    router: bool,
) -> None:
    decision = compile_m4_v2_routing_decision(gate)
    assert decision["route"] == route
    assert decision["expert_router_research_enabled"] is router
    assert decision["promotion_gate_opened"] is False


def _event(event_type: str, *, task_key: str = P261_TASK_KEY) -> dict:
    return {
        "event_digest": (
            {"started": "1", "completed": "2", "failed": "3"}.get(event_type, "4") * 64
        ),
        "execution_id": EXPECTED_P261_EXECUTION_ID,
        "control_plane_key": EXPECTED_CONTROL_PLANE_KEY,
        "manifest_digest": EXPECTED_P261_RUNNING_CONTROL_PLANE_MANIFEST_DIGEST,
        "task_digest": EXPECTED_P261_TASK_DIGEST,
        "task_key": task_key,
        "capability": "m4_p2_6_1_false_positive_and_power",
        "event_type": event_type,
        "sequence": 0 if event_type == "started" else 1,
        "recorded_at": "2026-08-03T00:00:00+00:00",
    }


def test_completion_guard_stops_before_release_and_verifies_post_stop(
    tmp_path: Path,
) -> None:
    completion_relative = (
        Path("runtime/research-os/mainline/tasks")
        / P261_TASK_KEY
        / EXPECTED_P261_EXECUTION_ID
        / "completion.json"
    )
    completion_path = tmp_path / completion_relative
    completion_path.parent.mkdir(parents=True)
    completion_path.write_text("opaque-final-artifact\n", encoding="utf-8")
    events = (_event("started"), _event("completed"))
    registered = MainlineArtifactRegistration(
        execution_id=EXPECTED_P261_EXECUTION_ID,
        control_plane_key=EXPECTED_CONTROL_PLANE_KEY,
        task_key=P261_TASK_KEY,
        task_digest=EXPECTED_P261_TASK_DIGEST,
        artifact_digest="6" * 64,
        artifact_type="measurement_validation_completion",
        schema_version="dehps-m4-p2-measurement-validation-completion.v1",
        artifact_path=completion_relative.as_posix(),
        parent_digests=("9" * 64,),
        git_commit="a" * 40,
    )
    registration = {
        "registration_digest": registered.registration_digest,
        **asdict(registered),
        "parent_digests": list(registered.parent_digests),
    }
    decision = evaluate_terminal_boundary(
        p261_events=events,
        all_events=events,
        registrations=(registration,),
        root_dir=tmp_path,
    )
    assert decision.state == "STOP_REQUIRED"
    assert decision.stop_service is True
    assert decision.publish_slot_event is False
    post = evaluate_post_stop_boundary(
        service_active_state="inactive",
        worker_cgroup_empty=True,
        downstream_started_events=(),
        completion_artifact_digest="6" * 64,
    )
    assert post.state == "SAFE_TO_RELEASE_SLOT"
    assert post.publish_slot_event is True


def test_completion_guard_rejects_running_manifest_drift() -> None:
    started = _event("started")
    completed = {**_event("completed"), "manifest_digest": "4" * 64}
    decision = evaluate_terminal_boundary(
        p261_events=(started, completed),
        all_events=(started, completed),
        registrations=(),
        root_dir=ROOT,
    )
    assert decision.state == "GOVERNANCE_INCIDENT"
    assert decision.reason == "P261_COMPLETION_MANIFEST_IDENTITY_MISSING"


def test_completion_guard_accepts_only_pinned_recovered_failure_history(
    tmp_path: Path,
) -> None:
    completion_relative = (
        Path("runtime/research-os/mainline/tasks")
        / P261_TASK_KEY
        / EXPECTED_P261_EXECUTION_ID
        / "completion.json"
    )
    completion_path = tmp_path / completion_relative
    completion_path.parent.mkdir(parents=True)
    completion_path.write_text("opaque-final-artifact\n", encoding="utf-8")
    started = _event("started")
    failed = {
        **_event("failed"),
        "event_digest": EXPECTED_P261_RECOVERED_FAILED_EVENT_DIGEST,
    }
    waiting = evaluate_terminal_boundary(
        p261_events=(started, failed),
        all_events=(started, failed),
        registrations=(),
        root_dir=tmp_path,
    )
    assert waiting.state == "WAITING"
    assert waiting.reason == "P261_TERMINAL_EVENT_NOT_AVAILABLE"

    completed = {**_event("completed"), "sequence": 2}
    registered = MainlineArtifactRegistration(
        execution_id=EXPECTED_P261_EXECUTION_ID,
        control_plane_key=EXPECTED_CONTROL_PLANE_KEY,
        task_key=P261_TASK_KEY,
        task_digest=EXPECTED_P261_TASK_DIGEST,
        artifact_digest="6" * 64,
        artifact_type="measurement_validation_completion",
        schema_version="dehps-m4-p2-measurement-validation-completion.v1",
        artifact_path=completion_relative.as_posix(),
        parent_digests=("9" * 64,),
        git_commit="a" * 40,
    )
    registration = {
        "registration_digest": registered.registration_digest,
        **asdict(registered),
        "parent_digests": list(registered.parent_digests),
    }
    recovered = evaluate_terminal_boundary(
        p261_events=(started, failed, completed),
        all_events=(started, failed, completed),
        registrations=(registration,),
        root_dir=tmp_path,
    )
    assert recovered.state == "STOP_REQUIRED"
    assert recovered.stop_service is True


def test_completion_guard_rejects_self_digested_registration_path_escape(
    tmp_path: Path,
) -> None:
    escaped = tmp_path / "escaped.json"
    escaped.write_text("opaque\n", encoding="utf-8")
    registered = MainlineArtifactRegistration(
        execution_id=EXPECTED_P261_EXECUTION_ID,
        control_plane_key=EXPECTED_CONTROL_PLANE_KEY,
        task_key=P261_TASK_KEY,
        task_digest=EXPECTED_P261_TASK_DIGEST,
        artifact_digest="6" * 64,
        artifact_type="measurement_validation_completion",
        schema_version="dehps-m4-p2-measurement-validation-completion.v1",
        artifact_path="../escaped.json",
        parent_digests=("9" * 64,),
        git_commit="a" * 40,
    )
    registration = {
        "registration_digest": registered.registration_digest,
        **asdict(registered),
        "parent_digests": list(registered.parent_digests),
    }
    events = (_event("started"), _event("completed"))
    decision = evaluate_terminal_boundary(
        p261_events=events,
        all_events=events,
        registrations=(registration,),
        root_dir=tmp_path,
    )
    assert decision.state == "GOVERNANCE_INCIDENT"
    assert decision.reason == "IMMUTABLE_COMPLETION_ARTIFACT_MISSING"


def test_slot_release_guard_artifact_is_typed_and_self_bound() -> None:
    payload = GuardDecision(
        state="SAFE_TO_RELEASE_SLOT",
        stop_service=False,
        publish_slot_event=True,
        reason="SERVICE_INACTIVE_CGROUP_EMPTY_NO_DOWNSTREAM_START",
        completion_artifact_digest="6" * 64,
    ).to_artifact()
    assert validate_slot_release_guard_artifact(payload) == payload


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("stop_service", True),
        ("reason", "FORGED"),
        ("completion_artifact_digest", "short"),
        ("statistical_results_read", True),
        ("promotion_gate_opened", True),
        ("parent_digests", []),
        ("guard_contract_digest", "7" * 64),
    ],
)
def test_slot_release_guard_rejects_self_digested_semantic_tamper(
    field: str,
    value: object,
) -> None:
    payload = GuardDecision(
        state="SAFE_TO_RELEASE_SLOT",
        stop_service=False,
        publish_slot_event=True,
        reason="SERVICE_INACTIVE_CGROUP_EMPTY_NO_DOWNSTREAM_START",
        completion_artifact_digest="6" * 64,
    ).to_artifact()
    payload[field] = value
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4.p261-completion-guard-decision.v1",
    )
    with pytest.raises(CompletionGuardError):
        validate_slot_release_guard_artifact(payload)


@pytest.mark.parametrize(
    ("events", "reason"),
    [
        ((_event("started"), _event("failed")), "P261_FAILED"),
        (
            (
                _event("started"),
                _event("completed"),
                {**_event("started", task_key=P27_TASK_KEY), "execution_id": "7" * 64},
            ),
            "DOWNSTREAM_DISPATCH_RACE",
        ),
        (
            (
                _event("started"),
                _event("completed"),
                {
                    **_event("started", task_key=LEGACY_P3_TASK_KEY),
                    "execution_id": "8" * 64,
                },
            ),
            "DOWNSTREAM_DISPATCH_RACE",
        ),
    ],
)
def test_completion_guard_incidents_never_release(
    events: tuple[dict, ...],
    reason: str,
    tmp_path: Path,
) -> None:
    decision = evaluate_terminal_boundary(
        p261_events=tuple(item for item in events if item["task_key"] == P261_TASK_KEY),
        all_events=events,
        registrations=(),
        root_dir=tmp_path,
    )
    assert decision.state == "GOVERNANCE_INCIDENT"
    assert decision.reason == reason
    assert decision.stop_service is True
    assert decision.publish_slot_event is False


def test_design_replay_fixture_is_frozen_and_tamper_fails() -> None:
    contract = load_measurement_contract_v2(CONTRACT_PATH)
    fixture = load_gate_replay_fixture(FIXTURE_PATH)
    design = build_design_artifacts(
        contract,
        execution_id="1" * 64,
        git_commit="2" * 40,
    )
    execution = {
        "artifact_type": "research_os_mainline_execution",
        "execution_id": "1" * 64,
        "artifact_digest": "3" * 64,
        "measurement_contract_v2_digest": contract.artifact_digest,
        "estimand_contract_digest": design.estimand_contract["artifact_digest"],
        "mechanism_role_contract_digest": design.mechanism_role_contract[
            "artifact_digest"
        ],
        "gate_compiler_contract_digest": design.gate_compiler_contract[
            "artifact_digest"
        ],
        "completion_artifact_digest": design.completion["artifact_digest"],
    }
    registrations = [
        {
            "artifact_digest": item["artifact_digest"],
            "artifact_type": item["artifact_type"],
            "artifact_path": f"runtime/{index}.json",
            "execution_id": "1" * 64,
        }
        for index, item in enumerate((*design.artifacts, execution))
    ]
    replay = build_design_replay_artifacts(
        contract,
        fixture=fixture,
        design_execution=execution,
        design_child_digests=[item["artifact_digest"] for item in design.artifacts],
        registration_payloads=registrations,
    )
    assert replay.measurement_contract_replay["status"] == "REPLAY_VERIFIED"
    assert replay.gate_compiler_replay["status"] == "REPLAY_VERIFIED"
    tampered = copy.deepcopy(dict(fixture.payload))
    tampered["expected_output_digest"] = "9" * 64
    with pytest.raises(Exception, match="fixture changed"):
        build_design_replay_artifacts(
            contract,
            fixture=type(fixture)(
                payload=tampered, artifact_digest=fixture.artifact_digest
            ),
            design_execution=execution,
            design_child_digests=[item["artifact_digest"] for item in design.artifacts],
            registration_payloads=registrations,
        )


class _DesignReplayRepository:
    def __init__(self, event: dict, registrations: list[dict]) -> None:
        self.event = event
        self.registrations = registrations

    def list_mainline_execution_events(
        self,
        *,
        control_plane_key: str,
        task_key: str | None = None,
        execution_id: str | None = None,
    ) -> tuple[dict, ...]:
        if task_key is not None and task_key != self.event["task_key"]:
            return ()
        if execution_id is not None and execution_id != self.event["execution_id"]:
            return ()
        return (self.event,)

    def list_mainline_artifacts(
        self,
        *,
        control_plane_key: str,
        execution_id: str,
    ) -> tuple[dict, ...]:
        assert execution_id == self.event["execution_id"]
        return tuple(self.registrations)


def test_design_replay_is_a_formal_capability_with_immutable_artifacts(
    tmp_path: Path,
) -> None:
    for relative in (
        "configs/research-os/m4-measurement-contract-v2.json",
        "configs/research-os/m4-measurement-contract-v2-replay-fixture-v1.json",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    manifest = load_m4_manifest(MANIFEST_PATH)
    tasks = {item.task_key: item for item in manifest.tasks}
    design_task = tasks["m4-v2-measurement-contract-design"]
    replay_task = tasks["m4-v2-measurement-contract-design-replay"]
    design_id = "a" * 64
    design = M4MeasurementContractV2DesignCapability(root_dir=tmp_path).execute(
        control_plane_key=EXPECTED_CONTROL_PLANE_KEY,
        task=design_task,
        execution_id=design_id,
        git_commit="b" * 40,
    )
    registrations = [asdict(item) for item in design.registrations]
    event = {
        "event_type": "completed",
        "task_key": design_task.task_key,
        "task_digest": design_task.artifact_digest,
        "execution_id": design_id,
        "payload": {
            "execution_artifact_path": str(
                design.execution_artifact_path.relative_to(tmp_path)
            ),
            "registered_artifact_count": len(registrations),
        },
    }
    repository = _DesignReplayRepository(event, registrations)
    result = M4MeasurementContractV2DesignReplayCapability(
        repository=repository,
        root_dir=tmp_path,
    ).execute(
        control_plane_key=EXPECTED_CONTROL_PLANE_KEY,
        task=replay_task,
        execution_id="c" * 64,
        git_commit="d" * 40,
    )
    assert result.completion_facts == (
        "m4-measurement-contract-v2-design-replay:VERIFIED",
    )
    assert result.execution_artifact["registered_artifact_count"] == 3
    assert {item.artifact_type for item in result.registrations} == {
        "MeasurementContractV2ReplayArtifact",
        "GateCompilerReplayArtifact",
        "research_os_mainline_execution",
    }

    gate_registration = next(
        item
        for item in registrations
        if item["artifact_type"] == "measurement_v2_gate_compiler_contract"
    )
    gate_path = tmp_path / gate_registration["artifact_path"]
    tampered = json.loads(gate_path.read_text(encoding="utf-8"))
    tampered["tampered"] = True
    gate_path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(
        MainlineSupervisorError, match="registered artifact content changed"
    ):
        M4MeasurementContractV2DesignReplayCapability(
            repository=repository,
            root_dir=tmp_path,
        ).execute(
            control_plane_key=EXPECTED_CONTROL_PLANE_KEY,
            task=replay_task,
            execution_id="e" * 64,
            git_commit="d" * 40,
        )


def test_additive_manifest_migration_preserves_live_truth() -> None:
    source = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source.pop("manifest_digest")
    new_tasks = {
        "m4-v2-measurement-contract-design",
        "m4-v2-measurement-contract-design-replay",
        "m4-v2-branch-identifiability-preflight-design",
        "m4-v2-p2-6-1-raw-execution-replay",
        "m4-v2-p2-7-measurement-gate-replay",
        "m4-v2-p2-6-1-marginal-binding",
        "m4-v2-p2-6-1-marginal-decision-replay",
        "m4-p2-9-golden-reference-freeze",
        "m4-p2-9-measurement-runtime-audit",
        "m4-p2-9-p263-golden-reference-freeze",
        "m4-p2-9-p263-measurement-runtime-audit",
        "m4-p2-9-p263-runtime-observation-arithmetic-fix",
        "m4-p2-9-p263-runtime-slot-release-eligibility",
        "m4-v2-global-routing",
    }
    live = copy.deepcopy(source)
    live["goals"] = [
        item
        for item in live["goals"]
        if item["goal_key"] != "M4_MEASUREMENT_RUNTIME_AUDIT"
    ]
    live["tasks"] = [
        item for item in live["tasks"] if item["task_key"] not in new_tasks
    ]
    p3_source = next(
        item for item in source["tasks"] if item["task_key"] == LEGACY_P3_TASK_KEY
    )
    p3_live = next(
        item for item in live["tasks"] if item["task_key"] == LEGACY_P3_TASK_KEY
    )
    p3_live["dependencies"] = [
        {
            "dependency_type": "task",
            "target_key": "m4-p2-synthetic-measurement-validation",
            "required_status": "completed",
        },
        {
            "dependency_type": "artifact",
            "target_key": "m4-p2-measurement-decision:PASS_TO_P3",
            "required_status": "available",
        },
    ]
    assert p3_live["dependencies"] != p3_source["dependencies"]
    additions = {
        item
        for item in source["facts"]["artifacts"]
        if item.startswith(
            (
                "m4-measurement-contract-v2",
                "m4-p2-6-1-marginal-binding-contract",
                "m4-p2-9-runtime-audit-plan",
            )
        )
    }
    live["facts"]["artifacts"] = [
        item for item in live["facts"]["artifacts"] if item not in additions
    ]
    migrated, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=source,
        allowlisted_new_goal_keys=("M4_MEASUREMENT_RUNTIME_AUDIT",),
        allowlisted_new_task_keys=new_tasks,
        allowlisted_revised_task_keys=(LEGACY_P3_TASK_KEY,),
        add_artifact_facts=additions,
        add_external_events=("m4-runtime-slot:p2-6-1-released",),
    )
    assert dry_run["status"] == "VERIFIED"
    assert dry_run["existing_task_deletions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert set(live["facts"]["artifacts"]).issubset(migrated["facts"]["artifacts"])
    migrated_p3 = next(
        item for item in migrated["tasks"] if item["task_key"] == LEGACY_P3_TASK_KEY
    )
    assert migrated_p3["dependencies"] == p3_source["dependencies"]


def test_runtime_audit_equivalence_and_unavailable_metrics() -> None:
    plan = load_runtime_audit_plan(AUDIT_PATH)
    fingerprint_dimensions = set(
        plan["oracle_contract"]["canonical_executor_fingerprint"]["required_dimensions"]
    )
    assert {
        (
            "exact_numerical_runtime_packages_versions_joblib_llvmlite_"
            "narwhals_numba_numpy_orjson_scipy_scikit_learn_threadpoolctl"
        ),
        ("distribution_RECORD_sha256_for_nine_exact_numerical_runtime_packages"),
        (
            "installed_tree_digest_for_nine_exact_numerical_runtime_packages_"
            "excluding_pyc"
        ),
        "critical_numeric_ML_JIT_native_extension_cluster_sha256",
        "LLVM_version_triples_host_cpu_and_features",
        "Numba_codegen_configuration",
        "NUMBA_LLVMLITE_environment_unset",
        "sklearn_config_and_joblib_active_backend_effective_n_jobs",
        "JOBLIB_LOKY_SKLEARN_environment_unset",
        "numeric_environment_exactly_canonical_thread_environment",
    } <= fingerprint_dimensions
    observer = RuntimeAuditObserver(enabled=False)
    assert observer.folds == 0
    payload = {"status": "COMPLETE", "value": [1, 2, 3]}
    children = [{"artifact_type": "child", "artifact_digest": "1" * 64}]
    attestation = build_equivalence_attestation(
        plan_digest=plan["artifact_digest"],
        reference_payload=payload,
        audited_payload=copy.deepcopy(payload),
        reference_child_artifacts=children,
        audited_child_artifacts=copy.deepcopy(children),
    )
    assert attestation["status"] == "EXACT_OUTPUT_EQUIVALENCE_VERIFIED"
    with pytest.raises(RuntimeAuditError, match="replicate payload changed"):
        build_equivalence_attestation(
            plan_digest=plan["artifact_digest"],
            reference_payload=payload,
            audited_payload={**payload, "value": [3, 2, 1]},
            reference_child_artifacts=children,
            audited_child_artifacts=children,
        )
    assert _io_deltas(None, None) == (UNAVAILABLE, UNAVAILABLE)


def test_runtime_observer_enabled_does_not_change_evaluator_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dehps.research_os.information_theory.measurement_system_v2 import (
        runtime_audit,
    )

    class _Evaluator:
        def evaluate(self, replicate: object) -> dict:
            return {"status": "COMPLETE", "payload": [1, 2, 3]}

    disabled = RuntimeAuditObserver(enabled=False)
    enabled = RuntimeAuditObserver(enabled=True)
    assert AuditedEvaluator(_Evaluator(), disabled).evaluate(object()) == (
        AuditedEvaluator(_Evaluator(), enabled).evaluate(object())
    )
    monkeypatch.setattr(runtime_audit, "_read_process_io", lambda: None)
    monkeypatch.setattr(runtime_audit, "_read_host_iowait_ticks", lambda: None)
    missing = RuntimeAuditObserver(enabled=True)
    with missing.phase("checkpoint_artifact_persistence"):
        pass
    missing.stop()
    observation = missing.observation(
        plan_digest="1" * 64,
        execution_id="2" * 64,
        git_commit="3" * 40,
        executor_fingerprint_digest_before="4" * 64,
        executor_fingerprint_digest_after="4" * 64,
        benchmark_attempt_id="5" * 64,
        measured_result_float64_tree_digest="6" * 64,
        measured_checkpoint_journal_sha256="7" * 64,
    )
    assert observation["process_io_read_bytes"] == UNAVAILABLE
    assert observation["process_io_write_bytes"] == UNAVAILABLE
    assert observation["host_iowait_ticks_unattributed"] == UNAVAILABLE
    assert isinstance(observation["artifact_write_latency_ms_p50"], float)


def test_runtime_observer_stop_freezes_metrics_and_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dehps.research_os.information_theory.measurement_system_v2 import (
        runtime_audit,
    )

    io_values = iter(
        (
            {"read_bytes": 10, "write_bytes": 20},
            {"read_bytes": 40, "write_bytes": 80},
        )
    )
    iowait_values = iter((100, 125))
    monkeypatch.setattr(runtime_audit, "_read_process_io", lambda: next(io_values))
    monkeypatch.setattr(
        runtime_audit, "_read_host_iowait_ticks", lambda: next(iowait_values)
    )
    wall_values = iter((100, 1_000_100))
    cpu_values = iter((50, 500_050))
    observer = RuntimeAuditObserver(
        enabled=True,
        clock_ns=lambda: next(wall_values),
        cpu_clock_ns=lambda: next(cpu_values),
    )
    observer.count_fold(2)
    observer.count_fit(3)
    observer.count_resample(4)
    with pytest.raises(RuntimeAuditError, match="must be stopped"):
        observer.observation(
            plan_digest="1" * 64,
            execution_id="2" * 64,
            git_commit="3" * 40,
            executor_fingerprint_digest_before="4" * 64,
            executor_fingerprint_digest_after="4" * 64,
            benchmark_attempt_id="5" * 64,
            measured_result_float64_tree_digest="6" * 64,
            measured_checkpoint_journal_sha256="7" * 64,
        )
    observer.stop()
    frozen = observer.observation(
        plan_digest="1" * 64,
        execution_id="2" * 64,
        git_commit="3" * 40,
        executor_fingerprint_digest_before="4" * 64,
        executor_fingerprint_digest_after="4" * 64,
        benchmark_attempt_id="5" * 64,
        measured_result_float64_tree_digest="6" * 64,
        measured_checkpoint_journal_sha256="7" * 64,
    )
    assert frozen["wall_time_seconds"] == 0.001
    assert frozen["process_cpu_time_seconds"] == 0.0005
    assert frozen["process_io_read_bytes"] == 30
    assert frozen["process_io_write_bytes"] == 60
    assert frozen["host_iowait_ticks_unattributed"] == 25
    assert frozen["folds_per_second"] == 2000.0
    with pytest.raises(RuntimeAuditError, match="already stopped"):
        observer.stop()


def test_p263_runtime_observation_fit_rate_uses_observed_fit_count() -> None:
    plan = load_runtime_audit_plan(AUDIT_PATH)
    observer = RuntimeAuditObserver(enabled=True)
    for (
        phase,
        invocation_count,
    ) in supervisor_module._RUNTIME_AUDIT_PHASE_INVOCATIONS.items():
        for _ in range(invocation_count):
            with observer.phase(phase):
                pass
    observer.count_fold(61)
    observer.count_fit(64)
    observer.count_resample(4000)
    observer.stop()
    fingerprint_digest = plan["oracle_contract"]["canonical_executor_fingerprint"][
        "required_fingerprint_digest"
    ]
    observation = observer.observation(
        plan_digest=plan["artifact_digest"],
        execution_id="2" * 64,
        git_commit="3" * 40,
        executor_fingerprint_digest_before=fingerprint_digest,
        executor_fingerprint_digest_after=fingerprint_digest,
        benchmark_attempt_id="5" * 64,
        measured_result_float64_tree_digest="6" * 64,
        measured_checkpoint_journal_sha256="7" * 64,
    )
    supervisor_module._validate_runtime_observation(
        observation,
        benchmark_plan=plan,
        execution_id="2" * 64,
        git_commit="3" * 40,
        executor_fingerprint_digest=fingerprint_digest,
        benchmark_attempt_id="5" * 64,
        measured_result_float64_tree_digest="6" * 64,
        measured_checkpoint_journal_sha256="7" * 64,
    )

    changed = dict(observation)
    changed["fits_per_second"] = 244 / changed["wall_time_seconds"]
    changed["artifact_digest"] = ""
    changed["artifact_digest"] = canonical_digest(
        {key: value for key, value in changed.items() if key != "artifact_digest"},
        domain="dehps.m4.p2-9.runtime-observation.v1",
    )
    with pytest.raises(
        MainlineSupervisorError,
        match="runtime audit observation arithmetic changed",
    ):
        supervisor_module._validate_runtime_observation(
            changed,
            benchmark_plan=plan,
            execution_id="2" * 64,
            git_commit="3" * 40,
            executor_fingerprint_digest=fingerprint_digest,
            benchmark_attempt_id="5" * 64,
            measured_result_float64_tree_digest="6" * 64,
            measured_checkpoint_journal_sha256="7" * 64,
        )


def test_runtime_correctness_replay_is_outside_measured_trace_capture() -> None:
    measured = PythonReferenceEvaluation(
        result_payload={"status": "COMPLETE", "actual_outer_fold_count": 61},
        fold_traces=(),
        checkpoint_journal_bytes=b'{"fold":1}\n',
    )
    correctness = PythonReferenceEvaluation(
        result_payload=dict(measured.result_payload),
        fold_traces=tuple({"fold_index": index} for index in range(61)),
        checkpoint_journal_bytes=measured.checkpoint_journal_bytes,
    )
    _require_exact_runtime_correctness_replay(
        measured=measured,
        correctness=correctness,
    )
    with pytest.raises(MainlineSupervisorError, match="result changed"):
        _require_exact_runtime_correctness_replay(
            measured=measured,
            correctness=PythonReferenceEvaluation(
                result_payload={**correctness.result_payload, "changed": True},
                fold_traces=correctness.fold_traces,
                checkpoint_journal_bytes=correctness.checkpoint_journal_bytes,
            ),
        )


def test_runtime_attempt_uses_separate_fresh_workdirs_and_never_reuses_legacy(
    tmp_path: Path,
) -> None:
    execution_id = "a" * 64
    task_dir = tmp_path / "task"
    first_id, measured, correctness = _prepare_fresh_runtime_audit_attempt(
        task_dir=task_dir,
        execution_id=execution_id,
    )
    assert first_id
    assert measured != correctness
    assert not measured.exists()
    assert not correctness.exists()

    measured.mkdir(parents=True)
    (measured / "checkpoint-journal.jsonl").write_text("stale", encoding="utf-8")
    second_id, second_measured, second_correctness = (
        _prepare_fresh_runtime_audit_attempt(
            task_dir=task_dir,
            execution_id=execution_id,
        )
    )
    assert second_id != first_id
    assert not second_measured.exists()
    assert not second_correctness.exists()

    (task_dir / "audited-work").mkdir()
    with pytest.raises(MainlineSupervisorError, match="legacy measured workdir"):
        _prepare_fresh_runtime_audit_attempt(
            task_dir=task_dir,
            execution_id=execution_id,
        )


def test_runtime_commit_marker_recovers_registrations_without_rerun(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    task = next(
        item
        for item in manifest.tasks
        if item.task_key == "m4-p2-9-p263-runtime-observation-arithmetic-fix"
    )
    execution_id = "e" * 64
    git_commit = "d" * 40
    task_dir = (
        tmp_path / "runtime/research-os/mainline/tasks" / task.task_key / execution_id
    )
    runtime_plan = {
        "schema_version": "test",
        "artifact_type": "runtime_plan",
        "artifact_digest": task.input_artifact_digests[0],
        "parent_digests": [],
    }
    benchmark_plan = supervisor_module.build_benchmark_plan_artifact(runtime_plan)
    fingerprint = {
        "artifact_type": "CanonicalExecutorFingerprint",
        "artifact_digest": "f" * 64,
    }
    golden_execution = {"artifact_digest": "8" * 64}
    golden_plan = {
        "artifact_digest": "7" * 64,
        "executor_fingerprint": fingerprint,
        "executor_fingerprint_digest": "f" * 64,
    }
    encoded_result = {"value": {"__float64__": "0000000000000000"}}
    golden_fixture = {
        "artifact_digest": "6" * 64,
        "replicate_result": encoded_result,
        "checkpoint_journal_utf8": "journal\n",
    }
    golden_replay = {"artifact_digest": "9" * 64}
    golden_source = {"artifact_digest": "a" * 64}
    observation = {
        "artifact_type": "RuntimeObservationArtifact",
        "artifact_digest": "2" * 64,
        "executor_fingerprint_digest_before": "f" * 64,
        "executor_fingerprint_digest_after": "f" * 64,
    }
    attempt = {
        "artifact_type": "RuntimeBenchmarkAttemptArtifact",
        "artifact_digest": "3" * 64,
        "benchmark_attempt_id": "b" * 64,
        "benchmark_attempt_path": "runtime/attempt",
        "measured_workdir_path": "runtime/attempt/measured",
        "correctness_replay_workdir_path": "runtime/attempt/correctness",
        "measured_result_payload": {"value": 0.0},
        "measured_result_float64_tree": encoded_result,
        "measured_result_float64_tree_digest": "c" * 64,
        "measured_checkpoint_journal_sha256": "1" * 64,
    }
    equivalence = {
        "artifact_type": "EquivalenceAttestationArtifact",
        "artifact_digest": "4" * 64,
    }
    source = {
        "artifact_type": "SourceIntegrityAttestationArtifact",
        "artifact_digest": "5" * 64,
        "backend_source_modified": False,
        "acceleration_changed_paths": [],
    }
    child_specs = (
        (
            "benchmark-plan",
            benchmark_plan["artifact_digest"],
            "plan.json",
            benchmark_plan,
        ),
        ("runtime-observation", "2" * 64, "observation.json", observation),
        ("runtime-benchmark-attempt", "3" * 64, "attempt.json", attempt),
        ("equivalence-attestation", "4" * 64, "attestation.json", equivalence),
        ("source-integrity-attestation", "5" * 64, "attestation.json", source),
    )
    child_payloads: list[tuple[Path, dict]] = []
    for directory, digest, filename, payload in child_specs:
        path = task_dir / "artifacts" / directory / digest / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        child_payloads.append((path, payload))
    execution = {
        "schema_version": "dehps-research-os-mainline-execution.v1",
        "artifact_type": "research_os_mainline_execution",
        "artifact_digest": "",
        "execution_id": execution_id,
        "control_plane_key": EXPECTED_CONTROL_PLANE_KEY,
        "goal_key": task.goal_key,
        "task_key": task.task_key,
        "task_digest": task.artifact_digest,
        "capability": task.requested_capability,
        "status": "COMPLETE",
        "completion_classification": "VALIDATED_IN_MAINLINE",
        "input_artifact_digests": list(task.input_artifact_digests),
        "benchmark_plan_artifact_digest": benchmark_plan["artifact_digest"],
        "runtime_observation_artifact_digest": observation["artifact_digest"],
        "runtime_benchmark_attempt_artifact_digest": attempt["artifact_digest"],
        "source_integrity_attestation_artifact_digest": source["artifact_digest"],
        "golden_source_integrity_attestation_artifact_digest": golden_source[
            "artifact_digest"
        ],
        "runtime_executor_fingerprint_digest_before": "f" * 64,
        "runtime_executor_fingerprint_digest_after": "f" * 64,
        "equivalence_attestation_artifact_digest": equivalence["artifact_digest"],
        "completion_fact": ("m4-p2-9-p263-runtime-audit-arithmetic-fix:VERIFIED"),
        "actual_fold_count": 61,
        "audited_fold_count": 61,
        "correctness_replay_fold_count": 61,
        "total_execution_fold_count": 122,
        "correctness_boundary_snapshot_count": 45,
        "frozen_reference_fold_count": 61,
        "registered_artifact_count": 6,
        "benchmark_attempt_id": attempt["benchmark_attempt_id"],
        "benchmark_attempt_path": attempt["benchmark_attempt_path"],
        "measured_workdir_path": attempt["measured_workdir_path"],
        "correctness_replay_workdir_path": attempt["correctness_replay_workdir_path"],
        "journal_reused": False,
        "fresh_workdir": True,
        "worker_count": 1,
        "formal_benchmark_after_p263_compatibility": True,
        "reference_evaluator_is_oracle": False,
        "immutable_golden_fixture_is_oracle": True,
        "acceleration_boundary_independent": True,
        "acceleration_boundary_independence_scope": (
            "literal_behavior_path_and_fresh_import_closure"
        ),
        "oracle_construction_process_isolated": False,
        "oracle_construction_fully_implementation_independent": False,
        "golden_reference_execution_artifact_digest": golden_execution[
            "artifact_digest"
        ],
        "golden_reference_plan_artifact_digest": golden_plan["artifact_digest"],
        "golden_reference_fixture_artifact_digest": golden_fixture["artifact_digest"],
        "golden_reference_replay_artifact_digest": golden_replay["artifact_digest"],
        "exact_golden_replay_verified": True,
        "shared_frozen_source_modified": False,
        "backend_source_modified": False,
        "acceleration_changed_paths": [],
        "backend_optimization_applied": False,
        "statistical_semantics_modified": False,
        "historical_outcomes_read": False,
        "p2_6_1_partial_statistical_results_read": False,
        "p2_6_3_statistical_results_read": False,
        "measurement_update_policy_digest": (
            "ad58b9abcd90c5e7ee7b9892ac8c209b8033f7a50e603b58c043685b0c7d6f99"
        ),
        "p2_6_3_task_digest": P263_TASK_DIGEST,
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
            golden_source["artifact_digest"],
            *(payload["artifact_digest"] for _, payload in child_payloads),
        ],
    }
    execution["artifact_digest"] = canonical_digest(
        {key: value for key, value in execution.items() if key != "artifact_digest"},
        domain="dehps.research-os.mainline-execution.v1",
    )
    execution_path = task_dir / "execution.json"
    execution_path.write_text(json.dumps(execution), encoding="utf-8")

    monkeypatch.setattr(
        supervisor_module, "build_canonical_executor_fingerprint", lambda: fingerprint
    )
    monkeypatch.setattr(
        supervisor_module, "_validate_runtime_observation", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        supervisor_module,
        "validate_runtime_benchmark_attempt_artifact",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        supervisor_module,
        "_validate_runtime_benchmark_attempt_files",
        lambda **kwargs: b"journal\n",
    )
    monkeypatch.setattr(
        supervisor_module, "build_source_integrity_attestation", lambda **kwargs: source
    )
    monkeypatch.setattr(
        supervisor_module,
        "validate_source_integrity_attestation",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        supervisor_module,
        "_build_runtime_golden_equivalence",
        lambda **kwargs: equivalence,
    )
    monkeypatch.setattr(
        supervisor_module,
        "_observed_reference_evaluation",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("timed work reran")),
    )

    kwargs = {
        "root_dir": tmp_path,
        "owner": SimpleNamespace(root_dir=tmp_path),
        "control_plane_key": EXPECTED_CONTROL_PLANE_KEY,
        "task": task,
        "execution_id": execution_id,
        "git_commit": git_commit,
        "task_dir": task_dir,
        "runtime_plan": runtime_plan,
        "golden_execution": golden_execution,
        "golden_plan": golden_plan,
        "golden_fixture": golden_fixture,
        "golden_replay": golden_replay,
        "golden_source_integrity": golden_source,
        "compatible_golden_source_identity": {"unused": "1" * 64},
    }
    result = _recover_runtime_audit_commit_marker(**kwargs)
    assert result is not None
    assert len(result.registrations) == 6

    tampered = {**execution, "worker_count": 2}
    tampered["artifact_digest"] = canonical_digest(
        {key: value for key, value in tampered.items() if key != "artifact_digest"},
        domain="dehps.research-os.mainline-execution.v1",
    )
    execution_path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(MainlineSupervisorError, match="commit marker identity"):
        _recover_runtime_audit_commit_marker(**kwargs)


def test_manifest_wires_replay_before_preflight_and_disconnects_legacy_p3() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    tasks = {item.task_key: item for item in manifest.tasks}
    preflight = tasks["m4-v2-branch-identifiability-preflight-design"]
    dependencies = {
        (item.dependency_type.value, item.target_key) for item in preflight.dependencies
    }
    assert ("task", "m4-v2-measurement-contract-design-replay") in dependencies
    assert (
        "artifact",
        "m4-measurement-contract-v2-design-replay:VERIFIED",
    ) in dependencies
    p3 = tasks[LEGACY_P3_TASK_KEY]
    p3_dependencies = {item.target_key for item in p3.dependencies}
    assert "m4-p2-measurement-decision:PASS_TO_P3" not in p3_dependencies
    assert "m4-v2-routing:ADAPTIVE_RESEARCH_ELIGIBLE" in p3_dependencies
    p261 = tasks["m4-p2-false-positive-and-power-runs"]
    assert p261.artifact_digest == P263_TASK_DIGEST
    assert "m4-p2-repair-measurement-system" in {
        item.target_key for item in p261.dependencies
    }
    frozen = load_measurement_compatibility_fixture(
        ROOT / P261_FROZEN_FIXTURE_PATH,
        expected_phase="M4-P2.6.1",
    )
    assert frozen.payload["source"]["task_digest"] == EXPECTED_P261_TASK_DIGEST
    compatibility = tasks["m4-p2-6-3-superseding-compatibility-acceptance"]
    assert {item.target_key for item in compatibility.dependencies} >= {
        "m4-p2-false-positive-and-power-runs",
        "m4-p2-automatic-gate-and-report",
    }
    design = tasks["m4-v2-measurement-contract-design"]
    assert {item.target_key for item in design.dependencies} >= {
        "m4-p2-6-3-superseding-compatibility-acceptance",
        "m4-p2-6-3-compatibility:VERIFIED",
    }
    assert (
        tasks["m4-p2-9-golden-reference-freeze"].artifact_digest
        != tasks["m4-p2-9-p263-golden-reference-freeze"].artifact_digest
    )
    golden = tasks["m4-p2-9-p263-golden-reference-freeze"]
    failed_runtime = tasks["m4-p2-9-p263-measurement-runtime-audit"]
    runtime = tasks["m4-p2-9-p263-runtime-observation-arithmetic-fix"]
    assert (
        manifest.task_state_by_digest[failed_runtime.artifact_digest].declared_status
        is TaskStatus.SUPERSEDED
    )
    assert golden.goal_key == runtime.goal_key == "M4_MEASUREMENT_RUNTIME_AUDIT"
    assert golden.lane.value == "maintenance"
    assert runtime.lane.value == "maintenance"
    runtime_dependencies = {item.target_key for item in runtime.dependencies}
    executor_event = (
        "m4-canonical-executor:"
        "e804e4eedf3c67ad9d35207367a096f6b830a6ab2ac29cc03501392d8430af32"
    )
    assert executor_event in {item.target_key for item in golden.dependencies}
    assert executor_event in runtime_dependencies
    assert "m4-p2-9-p263-golden-reference-freeze" in runtime_dependencies
    assert "m4-p2-9-p263-golden-reference:VERIFIED" in runtime_dependencies
    assert "m4-p2-6-3-compatibility:VERIFIED" in runtime_dependencies
    assert "m4-runtime-slot:p2-6-1-released" not in runtime_dependencies


def test_p263_compatibility_and_executor_unlock_golden_then_runtime() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    control_plane = ResearchOSControlPlane()
    source_snapshot = control_plane.resolve(manifest)
    source_resolutions = {item.task_key: item for item in source_snapshot.resolutions}
    assert source_resolutions["m4-p2-9-golden-reference-freeze"].status is (
        TaskStatus.SUPERSEDED
    )
    assert source_resolutions["m4-p2-9-measurement-runtime-audit"].status is (
        TaskStatus.SUPERSEDED
    )
    assert source_resolutions["m4-p2-9-p263-golden-reference-freeze"].status is (
        TaskStatus.EXTERNAL_WAIT
    )

    executor_event = (
        "m4-canonical-executor:"
        "e804e4eedf3c67ad9d35207367a096f6b830a6ab2ac29cc03501392d8430af32"
    )
    executor_payload = manifest.to_dict(include_digest=False)
    executor_payload["facts"]["external_events"] = sorted(
        {*executor_payload["facts"]["external_events"], executor_event}
    )
    executor_payload["facts"]["artifacts"] = sorted(
        {
            *executor_payload["facts"]["artifacts"],
            "m4-p2-6-3-compatibility:VERIFIED",
        }
    )
    with_executor = ControlPlaneManifest.from_dict(executor_payload)
    with_executor_snapshot = control_plane.resolve(with_executor)
    assert (
        next(
            item
            for item in with_executor_snapshot.resolutions
            if item.task_key == "m4-p2-9-p263-golden-reference-freeze"
        ).status
        is TaskStatus.READY
    )
    ready_keys = [item.task_key for item in with_executor_snapshot.ready_queue]
    assert "m4-p2-9-p263-golden-reference-freeze" in ready_keys
    assert "m4-p2-9-p263-runtime-observation-arithmetic-fix" not in ready_keys

    golden_task = next(
        task
        for task in with_executor.tasks
        if task.task_key == "m4-p2-9-p263-golden-reference-freeze"
    )
    payload = with_executor.to_dict(include_digest=False)
    for task in payload["tasks"]:
        if task["task_key"] == golden_task.task_key:
            task["status"] = "completed"
            task["completion_classification"] = "COMPLETE"
            break
    facts = set(payload["facts"]["artifacts"])
    facts.update(
        {
            "m4-p2-9-p263-golden-reference:VERIFIED",
            mainline_completion_fact(task=golden_task, execution_id="e" * 64),
        }
    )
    payload["facts"]["artifacts"] = sorted(facts)
    after_golden = ControlPlaneManifest.from_dict(payload)
    after_golden_snapshot = control_plane.resolve(after_golden)
    after_golden_resolutions = {
        item.task_key: item for item in after_golden_snapshot.resolutions
    }
    audit = after_golden_resolutions["m4-p2-9-p263-runtime-observation-arithmetic-fix"]
    assert audit.status is TaskStatus.READY
    assert not audit.unsatisfied_dependencies


def test_golden_reference_status_projects_only_completed_execution_identity() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    source = build_m4_status(manifest)
    audit_status = source["measurement_runtime_audit"]
    assert audit_status["required_fingerprint_digest"] == (
        "e804e4eedf3c67ad9d35207367a096f6b830a6ab2ac29cc03501392d8430af32"
    )
    assert audit_status["canonical_executor_event"] == (
        "m4-canonical-executor:"
        "e804e4eedf3c67ad9d35207367a096f6b830a6ab2ac29cc03501392d8430af32"
    )
    assert audit_status["canonical_executor_available"] is False
    assert (
        audit_status["supersession"]["p2_6_3_failed_runtime_audit_resolver_status"]
        == "superseded"
    )
    assert audit_status["task_key"] == (
        "m4-p2-9-p263-runtime-observation-arithmetic-fix"
    )
    assert audit_status["execution_status"] == "NOT_RUN"
    assert audit_status["evidence_progress_increment"] == 0
    assert audit_status["historical_outcomes_read"] is None
    assert audit_status["production_action"] is None
    golden = source["measurement_runtime_audit"]["golden_reference"]
    assert golden["resolver_status"] == "external_wait"
    assert golden["resolver_reason_code"] == "external_event_dependency_unsatisfied"
    assert golden["resolver_unsatisfied_dependencies"] == [
        audit_status["canonical_executor_event"],
        "m4-p2-6-3-compatibility:VERIFIED",
    ]
    assert golden["execution_status"] == "NOT_RUN"
    assert golden["plan_artifact_digest"] is None
    assert golden["immutable_golden_fixture_is_oracle"] is None
    assert golden["acceleration_boundary_independent"] is None
    assert golden["acceleration_boundary_independence_scope"] is None
    assert golden["oracle_construction_process_isolated"] is None
    assert golden["oracle_construction_fully_implementation_independent"] is None
    assert golden["exact_replay_verified"] is None
    assert golden["evidence_progress_before"] is None
    assert golden["evidence_progress_after"] is None
    assert golden["historical_outcomes_read"] is None
    assert golden["production_action"] is None

    authorized = manifest_with_external_event(
        manifest,
        event_key=(
            "m4-canonical-executor:"
            "e804e4eedf3c67ad9d35207367a096f6b830a6ab2ac29cc03501392d8430af32"
        ),
    )
    authorized_payload = authorized.to_dict(include_digest=False)
    authorized_payload["facts"]["artifacts"] = sorted(
        {
            *authorized_payload["facts"]["artifacts"],
            "m4-p2-6-3-compatibility:VERIFIED",
        }
    )
    authorized = ControlPlaneManifest.from_dict(authorized_payload)
    completed = build_m4_status(
        authorized,
        golden_reference_execution={
            "golden_reference_plan_artifact_digest": "1" * 64,
            "golden_reference_fixture_artifact_digest": "2" * 64,
            "golden_reference_replay_artifact_digest": "3" * 64,
            "source_integrity_attestation_artifact_digest": "4" * 64,
            "immutable_golden_fixture_is_oracle": True,
            "acceleration_boundary_independent": True,
            "acceleration_boundary_independence_scope": (
                "literal_behavior_path_and_fresh_import_closure"
            ),
            "oracle_construction_process_isolated": False,
            "oracle_construction_fully_implementation_independent": False,
            "exact_replay_verified": True,
            "engineering_progress_before": 0,
            "engineering_progress_after": 100,
            "evidence_progress_before": 0,
            "evidence_progress_after": 0,
            "historical_outcomes_read": False,
            "p2_6_3_statistical_results_read": False,
            "measurement_update_policy_digest": (
                "ad58b9abcd90c5e7ee7b9892ac8c209b8033f7a50e603b58c043685b0c7d6f99"
            ),
            "p2_6_3_task_digest": P263_TASK_DIGEST,
            "production_action": "none",
        },
    )
    projected = completed["measurement_runtime_audit"]["golden_reference"]
    assert (
        completed["measurement_runtime_audit"]["canonical_executor_available"] is True
    )
    assert projected["execution_status"] == "REPLAY_VERIFIED"
    assert projected["plan_artifact_digest"] == "1" * 64
    assert projected["fixture_artifact_digest"] == "2" * 64
    assert projected["replay_artifact_digest"] == "3" * 64
    assert projected["source_integrity_attestation_artifact_digest"] == "4" * 64
    assert projected["immutable_golden_fixture_is_oracle"] is True
    assert projected["acceleration_boundary_independent"] is True
    assert (
        projected["acceleration_boundary_independence_scope"]
        == "literal_behavior_path_and_fresh_import_closure"
    )
    assert projected["oracle_construction_process_isolated"] is False
    assert projected["oracle_construction_fully_implementation_independent"] is False
    assert projected["exact_replay_verified"] is True
    assert projected["engineering_progress_after"] == 100
    assert projected["historical_outcomes_read"] is False
    assert projected["production_action"] == "none"


def test_golden_work_counts_separate_full_folds_from_boundary_snapshots() -> None:
    bundle = _GoldenReferenceBundle(
        plan={},
        fixture={},
        replay={},
        runtime_audit_plan={},
        expected_input_digests=(),
        reference_fold_count=61,
        observed_fold_count=61,
        reference_boundary_snapshot_count=45,
        observed_boundary_snapshot_count=45,
        equivalence_boundary_case_count=45,
    )
    assert _golden_execution_work_counts(bundle) == {
        "actual_fold_count": 122,
        "reference_full_replicate_fold_count": 61,
        "observed_full_replicate_fold_count": 61,
        "reference_boundary_snapshot_count": 45,
        "observed_boundary_snapshot_count": 45,
        "equivalence_boundary_case_count": 45,
    }


def test_observed_boundary_snapshots_bind_replicate_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identities = tuple(
        {
            "scale_id": "FORWARD_61",
            "scenario_id": "NULL",
            "mechanism": "uniform_choose_6_without_replacement_from_33",
            "signal_strength": 0.0,
            "replicate_index": 0,
            "fold_position": f"position_{index}",
            "fold_index": index,
            "train_start_issue": 1,
            "train_end_issue": 10 + index,
            "test_issue": 11 + index,
        }
        for index in range(45)
    )
    cell = SimpleNamespace(
        scale_id="FORWARD_61",
        scenario_id="NULL",
        mechanism="uniform_choose_6_without_replacement_from_33",
        signal_strength=0.0,
    )
    replicate = SimpleNamespace(replicate_index=0, artifact_digest="a" * 64)
    dataset = SimpleNamespace(
        outer_evaluation_length=61,
        minimum_training_length=10,
        artifact_digest="b" * 64,
    )

    class _Cache:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def reveal_training_history(self, *_args, **_kwargs) -> None:
            pass

        def build_train_feature_view(self, *_args, **_kwargs) -> SimpleNamespace:
            return SimpleNamespace(feature_view_digest="c" * 64)

        def build_blind_test_feature_view(self, *_args, **_kwargs) -> SimpleNamespace:
            return SimpleNamespace(feature_view_digest="d" * 64)

    monkeypatch.setattr(
        supervisor_module,
        "golden_boundary_identity_contract",
        lambda: identities,
    )
    monkeypatch.setattr(supervisor_module, "build_cells", lambda *_args: (cell,))
    monkeypatch.setattr(
        supervisor_module,
        "build_replicate",
        lambda **_kwargs: replicate,
    )
    monkeypatch.setattr(
        supervisor_module,
        "generate_evaluation_dataset",
        lambda *_args, **_kwargs: dataset,
    )
    monkeypatch.setattr(supervisor_module, "StrictPriorFeatureCache", _Cache)
    monkeypatch.setattr(
        supervisor_module,
        "restrict_to_training_history",
        lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setattr(
        supervisor_module,
        "full_train_feature_view_payload_digest",
        lambda _view: "e" * 64,
    )
    monkeypatch.setattr(
        supervisor_module,
        "full_blind_feature_view_payload_digest",
        lambda _view: "f" * 64,
    )

    snapshots = supervisor_module._build_observed_boundary_snapshots(
        manifest=object(),
        synthetic=object(),
        truths={},
    )

    assert len(snapshots) == 45
    assert {snapshot["replicate_index"] for snapshot in snapshots} == {0}


def test_runtime_audit_status_requires_registered_independent_golden_lineage() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    authorized = manifest_with_external_event(
        manifest,
        event_key=(
            "m4-canonical-executor:"
            "e804e4eedf3c67ad9d35207367a096f6b830a6ab2ac29cc03501392d8430af32"
        ),
    )
    execution = {
        "golden_reference_execution_artifact_digest": "0" * 64,
        "golden_reference_plan_artifact_digest": "1" * 64,
        "golden_reference_fixture_artifact_digest": "2" * 64,
        "golden_reference_replay_artifact_digest": "3" * 64,
        "benchmark_plan_artifact_digest": "4" * 64,
        "runtime_observation_artifact_digest": "5" * 64,
        "runtime_benchmark_attempt_artifact_digest": "7" * 64,
        "source_integrity_attestation_artifact_digest": "8" * 64,
        "golden_source_integrity_attestation_artifact_digest": "9" * 64,
        "equivalence_attestation_artifact_digest": "6" * 64,
        "reference_evaluator_is_oracle": False,
        "immutable_golden_fixture_is_oracle": True,
        "acceleration_boundary_independent": True,
        "acceleration_boundary_independence_scope": (
            "literal_behavior_path_and_fresh_import_closure"
        ),
        "oracle_construction_process_isolated": False,
        "oracle_construction_fully_implementation_independent": False,
        "exact_golden_replay_verified": True,
        "actual_fold_count": 61,
        "audited_fold_count": 61,
        "correctness_replay_fold_count": 61,
        "total_execution_fold_count": 122,
        "correctness_boundary_snapshot_count": 45,
        "benchmark_attempt_id": "7" * 64,
        "journal_reused": False,
        "fresh_workdir": True,
        "shared_frozen_source_modified": False,
        "backend_source_modified": True,
        "acceleration_changed_paths": ["reference.py"],
        "backend_optimization_applied": False,
        "statistical_semantics_modified": False,
        "evidence_progress_before": 0,
        "evidence_progress_after": 0,
        "historical_outcomes_read": False,
        "p2_6_3_statistical_results_read": False,
        "measurement_update_policy_digest": (
            "ad58b9abcd90c5e7ee7b9892ac8c209b8033f7a50e603b58c043685b0c7d6f99"
        ),
        "p2_6_3_task_digest": P263_TASK_DIGEST,
        "production_action": "none",
    }
    status = build_m4_status(authorized, runtime_audit_execution=execution)
    runtime = status["measurement_runtime_audit"]
    assert runtime["execution_status"] == "EXACT_GOLDEN_EQUIVALENCE_VERIFIED"
    assert runtime["golden_prerequisite_verified"] is True
    assert runtime["golden_reference_execution_artifact_digest"] == "0" * 64
    assert runtime["golden_reference_fixture_artifact_digest"] == "2" * 64
    assert runtime["equivalence_attestation_artifact_digest"] == "6" * 64
    assert runtime["runtime_benchmark_attempt_artifact_digest"] == "7" * 64
    assert runtime["source_integrity_attestation_artifact_digest"] == "8" * 64
    assert runtime["golden_source_integrity_attestation_artifact_digest"] == "9" * 64
    assert runtime["immutable_golden_fixture_is_oracle"] is True
    assert runtime["acceleration_boundary_independent"] is True
    assert (
        runtime["acceleration_boundary_independence_scope"]
        == "literal_behavior_path_and_fresh_import_closure"
    )
    assert runtime["oracle_construction_process_isolated"] is False
    assert runtime["oracle_construction_fully_implementation_independent"] is False
    assert runtime["exact_golden_replay_verified"] is True
    assert runtime["production_like_measured_fold_count"] == 61
    assert runtime["correctness_replay_fold_count"] == 61
    assert runtime["total_execution_fold_count"] == 122
    assert runtime["correctness_boundary_snapshot_count"] == 45
    assert runtime["benchmark_attempt_id"] == "7" * 64
    assert runtime["journal_reused"] is False
    assert runtime["fresh_workdir"] is True
    assert runtime["historical_outcomes_read"] is False
    assert runtime["production_action"] == "none"

    with pytest.raises(ValueError, match="runtime audit execution governance"):
        build_m4_status(
            authorized,
            runtime_audit_execution={
                **execution,
                "reference_evaluator_is_oracle": True,
            },
        )
