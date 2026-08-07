from __future__ import annotations

import re
import subprocess
from collections.abc import Mapping, Sequence
from hashlib import sha1, sha256
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.golden_source_identity import (
    golden_source_identity_from_contract,
    project_golden_source_integrity_contract,
    validate_golden_source_integrity_identity,
)

from .float_identity import encode_float64_tree
from .source_compatibility import (
    P263_REVIEWED_SOURCE_COMPATIBILITY_FIXTURE_PATH,
    P263_REVIEWED_SOURCE_COMPATIBILITY_PATHS,
    REVIEWED_SHARED_COMPATIBILITY_FIXTURE_PATH,
    REVIEWED_SHARED_COMPATIBILITY_PATHS,
    SourceCompatibilityError,
    load_p263_reviewed_source_compatibility_fixture,
    load_reviewed_shared_compatibility_fixture,
    validate_p263_reviewed_source_compatibility_fixture,
    validate_reviewed_shared_compatibility_fixture,
)

SOURCE_INTEGRITY_SCHEMA = "dehps-m4-p2-9-source-integrity-attestation.v1"
BASELINE_GIT_COMMIT = "70f83a5400c6207cbe3806e69329a233e461e311"
_SHA1_PATTERN = re.compile(r"[0-9a-f]{40}")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
SOURCE_INTEGRITY_ATTESTATION_FIELDS = frozenset(
    {
        "schema_version",
        "artifact_type",
        "artifact_digest",
        "source_runtime_audit_plan_digest",
        "execution_id",
        "execution_git_commit",
        "baseline_git_commit",
        "baseline_is_ancestor",
        "construction_source_integrity_identity",
        "golden_source_integrity_identity",
        "shared_frozen_source_set_digest",
        "approved_acceleration_source_set_digest",
        "independent_oracle_source_set_digest",
        "audit_orchestration_source_set_digest",
        "shared_frozen_source_file_count",
        "approved_acceleration_source_file_count",
        "independent_oracle_source_file_count",
        "audit_orchestration_source_file_count",
        "shared_frozen_source_modified",
        "backend_source_modified",
        "acceleration_changed_paths",
        "backend_optimization_applied",
        "exact_fixture_replay_artifact_digest",
        "golden_reference_execution_artifact_digest",
        "exact_fixture_replay_verified",
        "statistical_semantics_modified",
        "evidence_created",
        "evidence_progress_increment",
        "historical_outcomes_read",
        "production_action",
        "parent_digests",
    }
)

CONSTRUCTION_SOURCE_INTEGRITY_IDENTITY_KEYS = (
    "source_integrity_contract_digest",
    "shared_frozen_source_set_digest",
    "approved_acceleration_source_set_digest",
    "independent_oracle_source_set_digest",
    "audit_orchestration_source_set_digest",
)

_INFORMATION_THEORY_ROOT = "apps/worker-python/dehps/research_os/information_theory"
_P261_FROZEN_SOURCE_SET_DIGESTS = {
    "shared_frozen_source_set_digest": (
        "75c124ba95c3ec0913f597b48a58a292a471fd1a00d8d9246e255ecd7f35715b"
    ),
    "approved_acceleration_source_set_digest": (
        "2616176e39473ac1cfac7a716ee824f46f6012bd61aea6cb1d6d46c13ca8a79f"
    ),
    "independent_oracle_source_set_digest": (
        "3df0dee1cbb4140cfe78ceda01a7de12aeb943a479b26681e572ab23fc7c1a5b"
    ),
    "audit_orchestration_source_set_digest": (
        "6663d1bb8aa31d215f558f9973199b9bb2df4511894e68c6dacf9d3fa5ee8296"
    ),
}
_P261_FROZEN_SOURCE_COUNTS = (65, 4, 11, 371)


def _paths(package: str, names: Sequence[str]) -> tuple[str, ...]:
    return tuple(f"{_INFORMATION_THEORY_ROOT}/{package}/{name}.py" for name in names)


SHARED_FROZEN_SOURCE_PATHS = tuple(
    sorted(
        {
            "apps/worker-python/dehps/artifacts.py",
            "apps/worker-python/dehps/contracts/__init__.py",
            "apps/worker-python/dehps/contracts/core.py",
            "apps/worker-python/dehps/ranking_contract.py",
            "apps/worker-python/dehps/training/research_fingerprint.py",
            f"{_INFORMATION_THEORY_ROOT}/artifact_contracts.py",
            f"{_INFORMATION_THEORY_ROOT}/digest.py",
            f"{_INFORMATION_THEORY_ROOT}/seed_domains.py",
            *_paths("calibration", ("contracts", "mechanisms")),
            *_paths(
                "measurement_validation",
                (
                    "contracts",
                    "dataset",
                    "repaired_contracts",
                    "schedule",
                    "statistics",
                ),
            ),
            *_paths(
                "probes",
                (
                    "__init__",
                    "contracts",
                    "convergence",
                    "empirical_baseline",
                    "logistic_regression",
                    "naive_bayes",
                    "registry",
                    "shallow_calibrated_tree",
                    "theoretical_baseline",
                ),
            ),
            *_paths(
                "metrics",
                (
                    "__init__",
                    "aggregation",
                    "artifacts",
                    "brier",
                    "calibration",
                    "code_length",
                    "contracts",
                    "errors",
                    "information_gain",
                    "kernel",
                    "log_loss",
                    "probability",
                ),
            ),
            *_paths(
                "resampling",
                (
                    "__init__",
                    "contracts",
                    "controls",
                    "plans",
                    "runner",
                    "statistics",
                ),
            ),
            *_paths(
                "synthetic",
                ("__init__", "contracts", "generator", "validation"),
            ),
            *_paths(
                "walk_forward",
                (
                    "artifacts",
                    "contracts",
                    "dataset",
                    "errors",
                    "feature_view",
                    "harness",
                    "inner_validation",
                    "leakage",
                    "manifest",
                    "preprocessing",
                    "split",
                ),
            ),
            (
                "configs/research-os/"
                "m4-information-theory-p2-6-1-measurement-contract-repair-v1.json"
            ),
            (
                "configs/research-os/"
                "m4-information-theory-p2-6-1-measurement-validation-v1.json"
            ),
            (
                "configs/research-os/"
                "m4-information-theory-p2-6-1-state-visible-feature-v1.json"
            ),
            (
                "configs/research-os/"
                "m4-information-theory-p2-synthetic-run-manifest-v1.0.1.json"
            ),
            (
                "configs/research-os/"
                "m4-information-theory-preregistration-v1.0.3.json"
            ),
            (
                "configs/research-os/"
                "m4-information-theory-walk-forward-harness-v1.json"
            ),
            (
                "configs/research-os/"
                "m4-information-theory-p2-5-resampling-kernel-v1.json"
            ),
            ("configs/research-os/" "m4-information-theory-metric-kernel-v1.json"),
        }
    )
)

APPROVED_ACCELERATION_SOURCE_PATHS = tuple(
    sorted(
        {
            f"{_INFORMATION_THEORY_ROOT}/measurement_validation/reference.py",
            f"{_INFORMATION_THEORY_ROOT}/measurement_validation/feature_cache.py",
            f"{_INFORMATION_THEORY_ROOT}/measurement_validation/journal.py",
            f"{_INFORMATION_THEORY_ROOT}/probes/runtime_cache_backend.py",
        }
    )
)

INDEPENDENT_ORACLE_SOURCE_PATHS = (
    "apps/worker-python/dehps/__init__.py",
    "apps/worker-python/dehps/golden_source_identity.py",
    "apps/worker-python/dehps/research_os/__init__.py",
    f"{_INFORMATION_THEORY_ROOT}/__init__.py",
    f"{_INFORMATION_THEORY_ROOT}/calibration/__init__.py",
    f"{_INFORMATION_THEORY_ROOT}/measurement_validation/__init__.py",
    f"{_INFORMATION_THEORY_ROOT}/measurement_validation/float_identity.py",
    f"{_INFORMATION_THEORY_ROOT}/measurement_validation/golden_reference.py",
    f"{_INFORMATION_THEORY_ROOT}/probes/runtime_cache.py",
    f"{_INFORMATION_THEORY_ROOT}/walk_forward/__init__.py",
    "apps/worker-python/dehps/training/__init__.py",
)

_REPOSITORY_ROOT = Path(__file__).resolve().parents[6]
_DEHPS_SOURCE_ROOT = _REPOSITORY_ROOT / "apps/worker-python/dehps"
_ALL_DEHPS_PYTHON_SOURCE_PATHS = tuple(
    sorted(
        path.relative_to(_REPOSITORY_ROOT).as_posix()
        for path in _DEHPS_SOURCE_ROOT.rglob("*.py")
        if path.is_file()
    )
)

# Phase 0 deliberately over-binds orchestration: every Python source file in
# the worker package that is not classified as shared, acceleration, or oracle
# is pinned here.  A superseding plan may narrow this set only after execution
# moves to a narrow subprocess with a reviewed import/trace closure.
AUDIT_ORCHESTRATION_SOURCE_PATHS = tuple(
    sorted(
        {
            *(
                path
                for path in _ALL_DEHPS_PYTHON_SOURCE_PATHS
                if path not in SHARED_FROZEN_SOURCE_PATHS
                and path not in APPROVED_ACCELERATION_SOURCE_PATHS
                and path not in INDEPENDENT_ORACLE_SOURCE_PATHS
            ),
            "apps/worker-python/scripts/build_m4_v2_additive_manifest.py",
            (
                "apps/worker-python/scripts/"
                "run_m4_p261_sparse_tree_compatibility_replay.py"
            ),
            "apps/worker-python/scripts/run_research_evidence_supervisor.py",
            "infra/systemd/dehps-research-evidence-supervisor.service",
        }
    )
)

_COMMON_CORE_SOURCE_PATHS = {
    "apps/worker-python/dehps/artifacts.py",
    "apps/worker-python/dehps/contracts/__init__.py",
    "apps/worker-python/dehps/contracts/core.py",
    "apps/worker-python/dehps/ranking_contract.py",
    f"{_INFORMATION_THEORY_ROOT}/artifact_contracts.py",
}

SHARED_COMPONENT_SOURCE_PATHS: Mapping[str, tuple[str, ...]] = {
    "synthetic_dataset_generator": tuple(
        path
        for path in SHARED_FROZEN_SOURCE_PATHS
        if any(
            token in path
            for token in (
                "/calibration/",
                "/synthetic/",
                "/measurement_validation/contracts.py",
                "/measurement_validation/dataset.py",
                "/measurement_validation/repaired_contracts.py",
                "/measurement_validation/schedule.py",
                "/walk_forward/contracts.py",
                "/walk_forward/errors.py",
                "p2-6-1-measurement",
                "p2-6-1-state-visible-feature",
                "p2-synthetic-run-manifest",
            )
        )
        or path in _COMMON_CORE_SOURCE_PATHS
        or path.endswith(("/contracts.py", "/digest.py", "/seed_domains.py"))
    ),
    "probe_model_core": tuple(
        path
        for path in SHARED_FROZEN_SOURCE_PATHS
        if "/probes/" in path
        or "/walk_forward/" in path
        or "preregistration" in path
        or "walk-forward-harness" in path
        or "state-visible-feature" in path
        or path in _COMMON_CORE_SOURCE_PATHS
    ),
    "issue_metric_kernel": tuple(
        path
        for path in SHARED_FROZEN_SOURCE_PATHS
        if "/metrics/" in path
        or path.endswith(
            (
                "/training/research_fingerprint.py",
                "m4-information-theory-metric-kernel-v1.json",
            )
        )
        or path in _COMMON_CORE_SOURCE_PATHS
    ),
    "bootstrap_kernel": tuple(
        path
        for path in SHARED_FROZEN_SOURCE_PATHS
        if "/resampling/" in path
        or path.endswith(
            (
                "/measurement_validation/statistics.py",
                "/seed_domains.py",
                "m4-information-theory-p2-5-resampling-kernel-v1.json",
            )
        )
        or path in _COMMON_CORE_SOURCE_PATHS
    ),
    "block_permutation_schedule": tuple(
        path
        for path in SHARED_FROZEN_SOURCE_PATHS
        if "/resampling/" in path
        or path.endswith(
            (
                "/measurement_validation/statistics.py",
                "/seed_domains.py",
                "m4-information-theory-p2-5-resampling-kernel-v1.json",
            )
        )
        or path in _COMMON_CORE_SOURCE_PATHS
    ),
    "primary_inference_kernel": tuple(
        path
        for path in SHARED_FROZEN_SOURCE_PATHS
        if path.endswith(
            (
                "/measurement_validation/statistics.py",
                "/resampling/statistics.py",
                "/resampling/contracts.py",
                "m4-information-theory-p2-5-resampling-kernel-v1.json",
            )
        )
        or path in _COMMON_CORE_SOURCE_PATHS
    ),
}


class SourceIntegrityError(RuntimeError):
    pass


def validate_construction_source_integrity_identity(
    value: object,
) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != set(
        CONSTRUCTION_SOURCE_INTEGRITY_IDENTITY_KEYS
    ):
        raise SourceIntegrityError("construction_source_integrity_identity_invalid")
    identity = {
        key: str(value.get(key) or "")
        for key in CONSTRUCTION_SOURCE_INTEGRITY_IDENTITY_KEYS
    }
    if any(_SHA256_PATTERN.fullmatch(digest) is None for digest in identity.values()):
        raise SourceIntegrityError("construction_source_integrity_identity_invalid")
    return identity


def content_sha256(data: bytes) -> str:
    return sha256(data).hexdigest()


def git_blob_sha1(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return sha1(header + data).hexdigest()


def float64_tree_digest(value: Any, *, domain: str) -> str:
    return canonical_digest(encode_float64_tree(value), domain=domain)


def source_set_digest(entries: Sequence[Mapping[str, Any]], *, kind: str) -> str:
    return canonical_digest(
        [dict(entry) for entry in entries],
        domain=f"dehps.m4.p2-9.{kind}-source-set.v1",
    )


def _run_git(root_dir: Path, *args: str) -> bytes:
    try:
        completed = subprocess.run(
            ("git", *args),
            cwd=root_dir,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SourceIntegrityError(
            f"source_integrity_git_failed:{' '.join(args)}"
        ) from exc
    return completed.stdout


def _baseline_bytes(root_dir: Path, *, commit: str, path: str) -> bytes:
    return _run_git(root_dir, "show", f"{commit}:{path}")


def _baseline_bytes_if_present(
    root_dir: Path,
    *,
    commit: str,
    path: str,
) -> bytes | None:
    listing = _run_git(
        root_dir,
        "ls-tree",
        "-z",
        "--name-only",
        commit,
        "--",
        path,
    )
    if listing == b"":
        return None
    expected = path.encode("utf-8") + b"\0"
    if listing != expected:
        raise SourceIntegrityError(f"source_integrity_baseline_path_ambiguous:{path}")
    return _baseline_bytes(root_dir, commit=commit, path=path)


def _entry_by_path(
    raw: object,
    *,
    expected_paths: Sequence[str],
    label: str,
) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, list):
        raise SourceIntegrityError(f"{label}_allowlist_missing")
    entries: dict[str, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, Mapping) or set(item) != {
            "path",
            "content_sha256",
            "git_blob_oid",
        }:
            raise SourceIntegrityError(f"{label}_allowlist_shape_changed")
        path = str(item.get("path") or "")
        if (
            not path
            or Path(path).is_absolute()
            or ".." in Path(path).parts
            or path in entries
            or _SHA256_PATTERN.fullmatch(str(item.get("content_sha256") or "")) is None
            or _SHA1_PATTERN.fullmatch(str(item.get("git_blob_oid") or "")) is None
        ):
            raise SourceIntegrityError(f"{label}_allowlist_entry_invalid")
        entries[path] = dict(item)
    if list(entries) != sorted(entries) or tuple(entries) != tuple(expected_paths):
        raise SourceIntegrityError(f"{label}_allowlist_paths_changed")
    return entries


def validate_source_integrity_contract(
    contract: object,
) -> dict[str, Any]:
    if not isinstance(contract, Mapping):
        raise SourceIntegrityError("source_integrity_contract_missing")
    expected_fields = {
        "baseline_git_commit",
        "git_object_format",
        "shared_component_source_paths",
        "shared_frozen_source_allowlist",
        "shared_frozen_source_set_digest",
        "approved_acceleration_source_allowlist",
        "approved_acceleration_source_set_digest",
        "independent_oracle_source_allowlist",
        "independent_oracle_source_set_digest",
        "audit_orchestration_source_allowlist",
        "audit_orchestration_source_set_digest",
        "reviewed_shared_compatibility_fixture_path",
        "reviewed_shared_compatibility_fixture_digest",
        "reviewed_shared_compatibility_paths",
        "shared_change_policy",
        "oracle_change_policy",
        "acceleration_change_policy",
        "audit_change_policy",
    }
    fixture_path = str(contract.get("reviewed_shared_compatibility_fixture_path"))
    if fixture_path == REVIEWED_SHARED_COMPATIBILITY_FIXTURE_PATH.as_posix():
        compatibility_paths = REVIEWED_SHARED_COMPATIBILITY_PATHS
        current_partition = False
    elif fixture_path == (
        P263_REVIEWED_SOURCE_COMPATIBILITY_FIXTURE_PATH.as_posix()
    ):
        compatibility_paths = P263_REVIEWED_SOURCE_COMPATIBILITY_PATHS
        current_partition = True
    else:
        raise SourceIntegrityError("source_integrity_compatibility_profile_changed")
    if (
        set(contract) != expected_fields
        or contract.get("baseline_git_commit") != BASELINE_GIT_COMMIT
        or contract.get("git_object_format") != "sha1"
        or contract.get("shared_component_source_paths")
        != {key: list(value) for key, value in SHARED_COMPONENT_SOURCE_PATHS.items()}
        or contract.get("shared_change_policy")
        != "FAIL_CLOSED_REQUIRES_NEW_REVIEWED_FIXTURE"
        or contract.get("oracle_change_policy")
        != "FAIL_CLOSED_REQUIRES_NEW_REVIEWED_FIXTURE"
        or contract.get("acceleration_change_policy")
        != "PINNED_FOR_PHASE0_REQUIRES_SUPERSEDING_PLAN"
        or contract.get("audit_change_policy")
        != "PINNED_PER_RUNTIME_PLAN_REQUIRES_SUPERSEDING_PLAN"
        or _SHA256_PATTERN.fullmatch(
            str(contract.get("reviewed_shared_compatibility_fixture_digest") or "")
        )
        is None
        or contract.get("reviewed_shared_compatibility_paths")
        != list(compatibility_paths)
    ):
        raise SourceIntegrityError("source_integrity_contract_shape_changed")
    embedded_paths = []
    for field in (
        "shared_frozen_source_allowlist",
        "approved_acceleration_source_allowlist",
        "independent_oracle_source_allowlist",
        "audit_orchestration_source_allowlist",
    ):
        raw = contract.get(field)
        if not isinstance(raw, list):
            raise SourceIntegrityError(f"{field}_missing")
        if not all(isinstance(item, Mapping) for item in raw):
            raise SourceIntegrityError(f"{field}_invalid")
        embedded_paths.append(tuple(str(item.get("path") or "") for item in raw))
    expected_partitions = (
        (
            SHARED_FROZEN_SOURCE_PATHS,
            APPROVED_ACCELERATION_SOURCE_PATHS,
            INDEPENDENT_ORACLE_SOURCE_PATHS,
            AUDIT_ORCHESTRATION_SOURCE_PATHS,
        )
        if current_partition
        else tuple(embedded_paths)
    )
    shared = _entry_by_path(
        contract.get("shared_frozen_source_allowlist"),
        expected_paths=expected_partitions[0],
        label="shared_frozen_source",
    )
    acceleration = _entry_by_path(
        contract.get("approved_acceleration_source_allowlist"),
        expected_paths=expected_partitions[1],
        label="approved_acceleration_source",
    )
    oracle = _entry_by_path(
        contract.get("independent_oracle_source_allowlist"),
        expected_paths=expected_partitions[2],
        label="independent_oracle_source",
    )
    orchestration = _entry_by_path(
        contract.get("audit_orchestration_source_allowlist"),
        expected_paths=expected_partitions[3],
        label="audit_orchestration_source",
    )
    if (
        contract.get("shared_frozen_source_set_digest")
        != source_set_digest(list(shared.values()), kind="shared-frozen")
        or contract.get("approved_acceleration_source_set_digest")
        != source_set_digest(list(acceleration.values()), kind="approved-acceleration")
        or contract.get("independent_oracle_source_set_digest")
        != source_set_digest(list(oracle.values()), kind="independent-oracle")
        or contract.get("audit_orchestration_source_set_digest")
        != source_set_digest(list(orchestration.values()), kind="audit-orchestration")
    ):
        raise SourceIntegrityError("source_integrity_source_set_digest_changed")
    if not current_partition and (
        tuple(map(len, (shared, acceleration, oracle, orchestration)))
        != _P261_FROZEN_SOURCE_COUNTS
        or any(
            contract.get(field) != digest
            for field, digest in _P261_FROZEN_SOURCE_SET_DIGESTS.items()
        )
    ):
        raise SourceIntegrityError("source_integrity_frozen_partition_changed")
    return dict(contract)


def construction_source_integrity_identity(
    runtime_plan: Mapping[str, Any],
) -> dict[str, str]:
    contract = validate_source_integrity_contract(
        runtime_plan.get("source_integrity_contract")
    )
    return {
        "source_integrity_contract_digest": canonical_digest(
            contract,
            domain="dehps.m4.p2-9.source-integrity-contract.v1",
        ),
        "shared_frozen_source_set_digest": str(
            contract["shared_frozen_source_set_digest"]
        ),
        "approved_acceleration_source_set_digest": str(
            contract["approved_acceleration_source_set_digest"]
        ),
        "independent_oracle_source_set_digest": str(
            contract["independent_oracle_source_set_digest"]
        ),
        "audit_orchestration_source_set_digest": str(
            contract["audit_orchestration_source_set_digest"]
        ),
    }


def golden_source_integrity_contract(
    runtime_plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the self-contained contract embedded in the immutable plan."""

    contract = validate_source_integrity_contract(
        runtime_plan.get("source_integrity_contract")
    )
    return project_golden_source_integrity_contract(contract)


def golden_source_integrity_identity(
    runtime_plan: Mapping[str, Any],
) -> dict[str, str]:
    return golden_source_identity_from_contract(
        golden_source_integrity_contract(runtime_plan)
    )


# Transitional read-only alias for callers migrating to the explicit name.
source_integrity_identity = construction_source_integrity_identity


def verify_approved_source_bytes(
    *,
    root_dir: Path,
    runtime_plan: Mapping[str, Any],
    git_commit: str | None = None,
) -> dict[str, Any]:
    contract = validate_source_integrity_contract(
        runtime_plan.get("source_integrity_contract")
    )
    baseline = str(contract["baseline_git_commit"])
    if git_commit is not None:
        if _SHA1_PATTERN.fullmatch(git_commit) is None:
            raise SourceIntegrityError("source_integrity_execution_commit_invalid")
        _run_git(root_dir, "merge-base", "--is-ancestor", baseline, git_commit)
        if _run_git(root_dir, "rev-parse", "HEAD").decode().strip() != git_commit:
            raise SourceIntegrityError("source_integrity_execution_commit_not_head")
    if _run_git(root_dir, "rev-parse", "--show-object-format").strip() != b"sha1":
        raise SourceIntegrityError("source_integrity_git_object_format_changed")
    shared_entries = contract["shared_frozen_source_allowlist"]
    acceleration_entries = contract["approved_acceleration_source_allowlist"]
    oracle_entries = contract["independent_oracle_source_allowlist"]
    orchestration_entries = contract["audit_orchestration_source_allowlist"]
    try:
        fixture_path = str(contract["reviewed_shared_compatibility_fixture_path"])
        if fixture_path == REVIEWED_SHARED_COMPATIBILITY_FIXTURE_PATH.as_posix():
            compatibility_fixture = load_reviewed_shared_compatibility_fixture(
                root_dir / fixture_path
            )
            validate_reviewed_shared_compatibility_fixture(
                compatibility_fixture,
                expected_artifact_digest=str(
                    contract["reviewed_shared_compatibility_fixture_digest"]
                ),
                expected_candidate_golden_identity=(
                    golden_source_integrity_identity(runtime_plan)
                ),
            )
        else:
            compatibility_fixture = (
                load_p263_reviewed_source_compatibility_fixture(
                    root_dir / fixture_path
                )
            )
            validate_p263_reviewed_source_compatibility_fixture(
                compatibility_fixture,
                expected_artifact_digest=str(
                    contract["reviewed_shared_compatibility_fixture_digest"]
                ),
                expected_candidate_golden_identity=(
                    golden_source_integrity_identity(runtime_plan)
                ),
            )
    except SourceCompatibilityError as exc:
        raise SourceIntegrityError(
            f"reviewed_shared_compatibility_fixture_invalid:{exc}"
        ) from exc
    compatibility_paths = set(contract["reviewed_shared_compatibility_paths"])
    baseline_fixture_entries = {
        str(entry["path"]): dict(entry)
        for entry in compatibility_fixture["baseline_source_entries"]
    }
    candidate_fixture_entries = {
        str(entry["path"]): dict(entry)
        for entry in compatibility_fixture["candidate_source_entries"]
    }
    for entry in shared_entries:
        path = str(entry["path"])
        current = (root_dir / path).read_bytes()
        baseline_content = _baseline_bytes(root_dir, commit=baseline, path=path)
        expected_sha = str(entry["content_sha256"])
        expected_blob = str(entry["git_blob_oid"])
        current_identity = {
            "path": path,
            "content_sha256": content_sha256(current),
            "git_blob_oid": git_blob_sha1(current),
        }
        baseline_identity = {
            "path": path,
            "content_sha256": content_sha256(baseline_content),
            "git_blob_oid": git_blob_sha1(baseline_content),
        }
        fixture_changed_source_invalid = path in compatibility_paths and (
            current_identity != candidate_fixture_entries.get(path)
            or baseline_identity != baseline_fixture_entries.get(path)
        )
        unchanged_source_invalid = path not in compatibility_paths and (
            baseline_identity["content_sha256"] != expected_sha
            or baseline_identity["git_blob_oid"] != expected_blob
        )
        if (
            current_identity["content_sha256"] != expected_sha
            or current_identity["git_blob_oid"] != expected_blob
            or fixture_changed_source_invalid
            or unchanged_source_invalid
            or (
                git_commit is not None
                and _baseline_bytes(root_dir, commit=git_commit, path=path) != current
            )
        ):
            raise SourceIntegrityError(f"shared_frozen_source_modified:{path}")
    changed_paths: list[str] = []
    for entry in acceleration_entries:
        path = str(entry["path"])
        current = (root_dir / path).read_bytes()
        if (
            content_sha256(current) != entry["content_sha256"]
            or git_blob_sha1(current) != entry["git_blob_oid"]
            or (
                git_commit is not None
                and _baseline_bytes(root_dir, commit=git_commit, path=path) != current
            )
        ):
            raise SourceIntegrityError(f"approved_acceleration_source_modified:{path}")
        baseline_content = _baseline_bytes_if_present(
            root_dir,
            commit=baseline,
            path=path,
        )
        if baseline_content is None or current != baseline_content:
            changed_paths.append(path)
    for label, entries in (
        ("independent_oracle_source", oracle_entries),
        ("audit_orchestration_source", orchestration_entries),
    ):
        for entry in entries:
            path = str(entry["path"])
            current = (root_dir / path).read_bytes()
            if (
                content_sha256(current) != entry["content_sha256"]
                or git_blob_sha1(current) != entry["git_blob_oid"]
                or (
                    git_commit is not None
                    and _baseline_bytes(root_dir, commit=git_commit, path=path)
                    != current
                )
            ):
                raise SourceIntegrityError(f"{label}_modified:{path}")
    return {
        "contract": contract,
        "baseline_git_commit": baseline,
        "acceleration_changed_paths": changed_paths,
    }


def preflight_source_integrity(
    *,
    root_dir: Path,
    runtime_plan: Mapping[str, Any],
) -> dict[str, str]:
    verify_approved_source_bytes(
        root_dir=root_dir,
        runtime_plan=runtime_plan,
    )
    return construction_source_integrity_identity(runtime_plan)


def build_source_integrity_attestation(
    *,
    root_dir: Path,
    runtime_plan: Mapping[str, Any],
    execution_id: str,
    git_commit: str,
    exact_fixture_replay_artifact_digest: str,
    golden_reference_execution_artifact_digest: str | None = None,
    golden_source_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if _SHA256_PATTERN.fullmatch(exact_fixture_replay_artifact_digest) is None or (
        golden_reference_execution_artifact_digest is not None
        and _SHA256_PATTERN.fullmatch(golden_reference_execution_artifact_digest)
        is None
    ):
        raise SourceIntegrityError("source_integrity_replay_lineage_invalid")
    verified = verify_approved_source_bytes(
        root_dir=root_dir,
        runtime_plan=runtime_plan,
        git_commit=git_commit,
    )
    contract = verified["contract"]
    baseline = str(verified["baseline_git_commit"])
    shared_entries = contract["shared_frozen_source_allowlist"]
    acceleration_entries = contract["approved_acceleration_source_allowlist"]
    oracle_entries = contract["independent_oracle_source_allowlist"]
    orchestration_entries = contract["audit_orchestration_source_allowlist"]
    changed_paths = list(verified["acceleration_changed_paths"])
    construction_identity = construction_source_integrity_identity(runtime_plan)
    expected_golden_identity = golden_source_integrity_identity(runtime_plan)
    attested_golden_identity = (
        expected_golden_identity
        if golden_source_identity is None
        else validate_golden_source_integrity_identity(golden_source_identity)
    )
    if attested_golden_identity != expected_golden_identity:
        raise SourceIntegrityError("golden_source_integrity_incompatible")
    parent_digests = [
        runtime_plan["artifact_digest"],
        exact_fixture_replay_artifact_digest,
        *sorted(construction_identity.values()),
        *sorted(attested_golden_identity.values()),
    ]
    if golden_reference_execution_artifact_digest is not None:
        parent_digests.append(golden_reference_execution_artifact_digest)
    payload: dict[str, Any] = {
        "schema_version": SOURCE_INTEGRITY_SCHEMA,
        "artifact_type": "SourceIntegrityAttestationArtifact",
        "artifact_digest": "",
        "source_runtime_audit_plan_digest": runtime_plan["artifact_digest"],
        "execution_id": execution_id,
        "execution_git_commit": git_commit,
        "baseline_git_commit": baseline,
        "baseline_is_ancestor": True,
        "construction_source_integrity_identity": construction_identity,
        "golden_source_integrity_identity": attested_golden_identity,
        "shared_frozen_source_set_digest": contract["shared_frozen_source_set_digest"],
        "approved_acceleration_source_set_digest": contract[
            "approved_acceleration_source_set_digest"
        ],
        "independent_oracle_source_set_digest": contract[
            "independent_oracle_source_set_digest"
        ],
        "audit_orchestration_source_set_digest": contract[
            "audit_orchestration_source_set_digest"
        ],
        "shared_frozen_source_file_count": len(shared_entries),
        "approved_acceleration_source_file_count": len(acceleration_entries),
        "independent_oracle_source_file_count": len(oracle_entries),
        "audit_orchestration_source_file_count": len(orchestration_entries),
        "shared_frozen_source_modified": False,
        "backend_source_modified": bool(changed_paths),
        "acceleration_changed_paths": changed_paths,
        "backend_optimization_applied": False,
        "exact_fixture_replay_artifact_digest": (exact_fixture_replay_artifact_digest),
        "golden_reference_execution_artifact_digest": (
            golden_reference_execution_artifact_digest
        ),
        "exact_fixture_replay_verified": True,
        "statistical_semantics_modified": False,
        "evidence_created": False,
        "evidence_progress_increment": 0,
        "historical_outcomes_read": False,
        "production_action": "none",
        "parent_digests": parent_digests,
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4.p2-9.source-integrity-attestation.v1",
    )
    return payload


def validate_source_integrity_attestation(
    payload: Mapping[str, Any],
    *,
    runtime_plan: Mapping[str, Any],
    execution_id: str,
    git_commit: str,
    exact_fixture_replay_artifact_digest: str,
    golden_reference_execution_artifact_digest: str | None = None,
    golden_source_identity: Mapping[str, Any] | None = None,
) -> None:
    identity = dict(payload)
    digest = identity.pop("artifact_digest", None)
    contract = validate_source_integrity_contract(
        runtime_plan.get("source_integrity_contract")
    )
    construction_identity = construction_source_integrity_identity(runtime_plan)
    expected_golden_identity = (
        golden_source_integrity_identity(runtime_plan)
        if golden_source_identity is None
        else validate_golden_source_integrity_identity(golden_source_identity)
    )
    if expected_golden_identity != golden_source_integrity_identity(runtime_plan):
        raise SourceIntegrityError("golden_source_integrity_incompatible")
    if (
        set(payload) != SOURCE_INTEGRITY_ATTESTATION_FIELDS
        or digest
        != canonical_digest(
            identity,
            domain="dehps.m4.p2-9.source-integrity-attestation.v1",
        )
        or payload.get("schema_version") != SOURCE_INTEGRITY_SCHEMA
        or payload.get("artifact_type") != "SourceIntegrityAttestationArtifact"
        or payload.get("source_runtime_audit_plan_digest")
        != runtime_plan.get("artifact_digest")
        or payload.get("execution_id") != execution_id
        or payload.get("execution_git_commit") != git_commit
        or payload.get("baseline_git_commit") != BASELINE_GIT_COMMIT
        or payload.get("baseline_is_ancestor") is not True
        or payload.get("construction_source_integrity_identity")
        != construction_identity
        or payload.get("golden_source_integrity_identity") != expected_golden_identity
        or payload.get("shared_frozen_source_set_digest")
        != contract["shared_frozen_source_set_digest"]
        or payload.get("approved_acceleration_source_set_digest")
        != contract["approved_acceleration_source_set_digest"]
        or payload.get("independent_oracle_source_set_digest")
        != contract["independent_oracle_source_set_digest"]
        or payload.get("audit_orchestration_source_set_digest")
        != contract["audit_orchestration_source_set_digest"]
        or payload.get("shared_frozen_source_file_count")
        != len(SHARED_FROZEN_SOURCE_PATHS)
        or payload.get("approved_acceleration_source_file_count")
        != len(APPROVED_ACCELERATION_SOURCE_PATHS)
        or payload.get("independent_oracle_source_file_count")
        != len(INDEPENDENT_ORACLE_SOURCE_PATHS)
        or payload.get("audit_orchestration_source_file_count")
        != len(AUDIT_ORCHESTRATION_SOURCE_PATHS)
        or payload.get("shared_frozen_source_modified") is not False
        or payload.get("backend_source_modified")
        is not bool(payload.get("acceleration_changed_paths"))
        or payload.get("backend_optimization_applied") is not False
        or payload.get("exact_fixture_replay_artifact_digest")
        != exact_fixture_replay_artifact_digest
        or payload.get("golden_reference_execution_artifact_digest")
        != golden_reference_execution_artifact_digest
        or payload.get("exact_fixture_replay_verified") is not True
        or payload.get("statistical_semantics_modified") is not False
        or payload.get("evidence_created") is not False
        or payload.get("evidence_progress_increment") != 0
        or payload.get("historical_outcomes_read") is not False
        or payload.get("production_action") != "none"
        or payload.get("parent_digests")
        != [
            runtime_plan.get("artifact_digest"),
            exact_fixture_replay_artifact_digest,
            *sorted(construction_identity.values()),
            *sorted(expected_golden_identity.values()),
            *(
                [golden_reference_execution_artifact_digest]
                if golden_reference_execution_artifact_digest is not None
                else []
            ),
        ]
        or payload.get("acceleration_changed_paths")
        != sorted(payload.get("acceleration_changed_paths") or [])
        or any(
            path not in APPROVED_ACCELERATION_SOURCE_PATHS
            for path in payload.get("acceleration_changed_paths") or []
        )
    ):
        raise SourceIntegrityError("source_integrity_attestation_changed")


def validate_registered_source_integrity_attestation(
    payload: Mapping[str, Any],
    *,
    source_runtime_audit_plan_digest: str,
    construction_source_identity: Mapping[str, Any],
    golden_source_identity: Mapping[str, Any],
    execution_id: str,
    git_commit: str,
    baseline_git_commit: str,
    exact_fixture_replay_artifact_digest: str,
    golden_reference_execution_artifact_digest: str | None = None,
) -> None:
    """Validate an immutable historical attestation without the old plan file."""

    construction = validate_construction_source_integrity_identity(
        construction_source_identity
    )
    golden = validate_golden_source_integrity_identity(golden_source_identity)
    identity = dict(payload)
    digest = identity.pop("artifact_digest", None)
    changed_paths = payload.get("acceleration_changed_paths")
    counts = (
        payload.get("shared_frozen_source_file_count"),
        payload.get("approved_acceleration_source_file_count"),
        payload.get("independent_oracle_source_file_count"),
        payload.get("audit_orchestration_source_file_count"),
    )
    expected_parents = [
        source_runtime_audit_plan_digest,
        exact_fixture_replay_artifact_digest,
        *sorted(construction.values()),
        *sorted(golden.values()),
        *(
            [golden_reference_execution_artifact_digest]
            if golden_reference_execution_artifact_digest is not None
            else []
        ),
    ]
    if (
        set(payload) != SOURCE_INTEGRITY_ATTESTATION_FIELDS
        or _SHA256_PATTERN.fullmatch(source_runtime_audit_plan_digest) is None
        or _SHA256_PATTERN.fullmatch(execution_id) is None
        or _SHA1_PATTERN.fullmatch(git_commit) is None
        or _SHA256_PATTERN.fullmatch(exact_fixture_replay_artifact_digest) is None
        or (
            golden_reference_execution_artifact_digest is not None
            and _SHA256_PATTERN.fullmatch(golden_reference_execution_artifact_digest)
            is None
        )
        or digest
        != canonical_digest(
            identity,
            domain="dehps.m4.p2-9.source-integrity-attestation.v1",
        )
        or payload.get("schema_version") != SOURCE_INTEGRITY_SCHEMA
        or payload.get("artifact_type") != "SourceIntegrityAttestationArtifact"
        or payload.get("source_runtime_audit_plan_digest")
        != source_runtime_audit_plan_digest
        or payload.get("execution_id") != execution_id
        or payload.get("execution_git_commit") != git_commit
        or payload.get("baseline_git_commit") != baseline_git_commit
        or _SHA1_PATTERN.fullmatch(baseline_git_commit) is None
        or payload.get("baseline_is_ancestor") is not True
        or payload.get("construction_source_integrity_identity") != construction
        or payload.get("golden_source_integrity_identity") != golden
        or payload.get("shared_frozen_source_set_digest")
        != construction["shared_frozen_source_set_digest"]
        or payload.get("shared_frozen_source_set_digest")
        != golden["shared_frozen_source_set_digest"]
        or payload.get("approved_acceleration_source_set_digest")
        != construction["approved_acceleration_source_set_digest"]
        or payload.get("independent_oracle_source_set_digest")
        != construction["independent_oracle_source_set_digest"]
        or payload.get("independent_oracle_source_set_digest")
        != golden["independent_oracle_source_set_digest"]
        or payload.get("audit_orchestration_source_set_digest")
        != construction["audit_orchestration_source_set_digest"]
        or any(type(count) is not int or count <= 0 for count in counts)
        or payload.get("shared_frozen_source_modified") is not False
        or not isinstance(changed_paths, list)
        or changed_paths != sorted({str(path) for path in changed_paths})
        or any(
            not path or Path(path).is_absolute() or ".." in Path(path).parts
            for path in changed_paths
        )
        or len(changed_paths)
        > int(payload.get("approved_acceleration_source_file_count") or 0)
        or payload.get("backend_source_modified") is not bool(changed_paths)
        or payload.get("backend_optimization_applied") is not False
        or payload.get("exact_fixture_replay_artifact_digest")
        != exact_fixture_replay_artifact_digest
        or payload.get("golden_reference_execution_artifact_digest")
        != golden_reference_execution_artifact_digest
        or payload.get("exact_fixture_replay_verified") is not True
        or payload.get("statistical_semantics_modified") is not False
        or payload.get("evidence_created") is not False
        or payload.get("evidence_progress_increment") != 0
        or payload.get("historical_outcomes_read") is not False
        or payload.get("production_action") != "none"
        or payload.get("parent_digests") != expected_parents
    ):
        raise SourceIntegrityError("registered_source_integrity_attestation_changed")
