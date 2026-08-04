from __future__ import annotations

import copy
import re
from collections.abc import Mapping, Sequence
from typing import Any

from dehps.contracts import canonical_digest

BASELINE_GIT_COMMIT = "70f83a5400c6207cbe3806e69329a233e461e311"
GOLDEN_SOURCE_CONTRACT_DOMAIN = "dehps.m4.p2-9.golden-source-integrity-contract.v1"
GOLDEN_SOURCE_INTEGRITY_IDENTITY_KEYS = (
    "golden_source_contract_digest",
    "shared_frozen_source_set_digest",
    "independent_oracle_source_set_digest",
)
GOLDEN_SOURCE_CONTRACT_FIELDS = (
    "baseline_git_commit",
    "git_object_format",
    "shared_component_source_paths",
    "shared_frozen_source_allowlist",
    "shared_frozen_source_set_digest",
    "independent_oracle_source_allowlist",
    "independent_oracle_source_set_digest",
    "shared_change_policy",
    "oracle_change_policy",
)
SHARED_FROZEN_COMPONENTS = (
    "synthetic_dataset_generator",
    "probe_model_core",
    "issue_metric_kernel",
    "bootstrap_kernel",
    "block_permutation_schedule",
    "primary_inference_kernel",
)

_SHA1_PATTERN = re.compile(r"[0-9a-f]{40}")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


class GoldenSourceIdentityError(RuntimeError):
    pass


def _source_set_digest(
    entries: Sequence[Mapping[str, Any]],
    *,
    kind: str,
) -> str:
    return canonical_digest(
        [dict(entry) for entry in entries],
        domain=f"dehps.m4.p2-9.{kind}-source-set.v1",
    )


def _validate_allowlist(value: object, *, label: str) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        raise GoldenSourceIdentityError(f"{label}_allowlist_missing")
    entries: list[dict[str, Any]] = []
    paths: list[str] = []
    for raw in value:
        if not isinstance(raw, Mapping) or set(raw) != {
            "path",
            "content_sha256",
            "git_blob_oid",
        }:
            raise GoldenSourceIdentityError(f"{label}_allowlist_shape_changed")
        path = str(raw.get("path") or "")
        if (
            not path
            or path.startswith("/")
            or ".." in path.split("/")
            or _SHA256_PATTERN.fullmatch(str(raw.get("content_sha256") or "")) is None
            or _SHA1_PATTERN.fullmatch(str(raw.get("git_blob_oid") or "")) is None
        ):
            raise GoldenSourceIdentityError(f"{label}_allowlist_entry_invalid")
        paths.append(path)
        entries.append(dict(raw))
    if paths != sorted(set(paths)):
        raise GoldenSourceIdentityError(f"{label}_allowlist_paths_changed")
    return tuple(entries)


def validate_golden_source_integrity_contract(
    contract: object,
) -> dict[str, Any]:
    if (
        not isinstance(contract, Mapping)
        or set(contract) != set(GOLDEN_SOURCE_CONTRACT_FIELDS)
        or contract.get("baseline_git_commit") != BASELINE_GIT_COMMIT
        or contract.get("git_object_format") != "sha1"
        or contract.get("shared_change_policy")
        != "FAIL_CLOSED_REQUIRES_NEW_REVIEWED_FIXTURE"
        or contract.get("oracle_change_policy")
        != "FAIL_CLOSED_REQUIRES_NEW_REVIEWED_FIXTURE"
    ):
        raise GoldenSourceIdentityError("golden_source_integrity_contract_changed")

    shared = _validate_allowlist(
        contract.get("shared_frozen_source_allowlist"),
        label="golden_shared_frozen_source",
    )
    oracle = _validate_allowlist(
        contract.get("independent_oracle_source_allowlist"),
        label="golden_independent_oracle_source",
    )
    if contract.get("shared_frozen_source_set_digest") != _source_set_digest(
        shared, kind="shared-frozen"
    ) or contract.get("independent_oracle_source_set_digest") != _source_set_digest(
        oracle, kind="independent-oracle"
    ):
        raise GoldenSourceIdentityError("golden_source_integrity_set_digest_changed")

    component_paths = contract.get("shared_component_source_paths")
    shared_paths = {str(entry["path"]) for entry in shared}
    if not isinstance(component_paths, Mapping) or set(component_paths) != set(
        SHARED_FROZEN_COMPONENTS
    ):
        raise GoldenSourceIdentityError("golden_shared_component_source_paths_changed")
    for component in SHARED_FROZEN_COMPONENTS:
        paths = component_paths.get(component)
        if (
            not isinstance(paths, list)
            or paths != sorted({str(path) for path in paths})
            or not paths
            or any(str(path) not in shared_paths for path in paths)
        ):
            raise GoldenSourceIdentityError(
                "golden_shared_component_source_paths_changed"
            )
    return copy.deepcopy(dict(contract))


def project_golden_source_integrity_contract(
    full_source_contract: object,
) -> dict[str, Any]:
    if not isinstance(full_source_contract, Mapping) or any(
        field not in full_source_contract for field in GOLDEN_SOURCE_CONTRACT_FIELDS
    ):
        raise GoldenSourceIdentityError("golden_source_projection_input_invalid")
    projection = {
        field: copy.deepcopy(full_source_contract[field])
        for field in GOLDEN_SOURCE_CONTRACT_FIELDS
    }
    return validate_golden_source_integrity_contract(projection)


def golden_source_identity_from_contract(
    contract: Mapping[str, Any],
) -> dict[str, str]:
    projection = validate_golden_source_integrity_contract(contract)
    return {
        "golden_source_contract_digest": canonical_digest(
            projection,
            domain=GOLDEN_SOURCE_CONTRACT_DOMAIN,
        ),
        "shared_frozen_source_set_digest": str(
            projection["shared_frozen_source_set_digest"]
        ),
        "independent_oracle_source_set_digest": str(
            projection["independent_oracle_source_set_digest"]
        ),
    }


def validate_golden_source_integrity_identity(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != set(
        GOLDEN_SOURCE_INTEGRITY_IDENTITY_KEYS
    ):
        raise GoldenSourceIdentityError("golden_source_integrity_identity_invalid")
    identity = {
        key: str(value.get(key) or "") for key in GOLDEN_SOURCE_INTEGRITY_IDENTITY_KEYS
    }
    if any(_SHA256_PATTERN.fullmatch(digest) is None for digest in identity.values()):
        raise GoldenSourceIdentityError("golden_source_integrity_identity_invalid")
    return identity


def require_golden_source_compatibility(
    *,
    registered_golden_contract: Mapping[str, Any],
    registered_golden_identity: Mapping[str, Any],
    new_full_source_contract: Mapping[str, Any],
) -> dict[str, str]:
    """Accept a new runtime plan only when the old golden projection is exact."""

    old_contract = validate_golden_source_integrity_contract(registered_golden_contract)
    old_identity = validate_golden_source_integrity_identity(registered_golden_identity)
    if golden_source_identity_from_contract(old_contract) != old_identity:
        raise GoldenSourceIdentityError("registered_golden_source_identity_changed")
    new_contract = project_golden_source_integrity_contract(new_full_source_contract)
    new_identity = golden_source_identity_from_contract(new_contract)
    if new_contract != old_contract or new_identity != old_identity:
        raise GoldenSourceIdentityError("golden_source_integrity_incompatible")
    return new_identity
