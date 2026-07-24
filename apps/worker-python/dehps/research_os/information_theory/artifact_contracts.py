from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from dehps.training.research_fingerprint import SeedPolicy


ARTIFACT_IDENTITY_FIELDS = (
    "schema_version",
    "artifact_type",
    "artifact_digest",
    "parent_digests",
    "created_at",
    "git_commit",
    "working_tree_clean",
    "dataset_digest",
    "preregistration_digest",
    "config_digest",
    "seed_policy",
)
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class ArtifactContractViolation(ValueError):
    pass


def validate_artifact_identity(
    payload: Mapping[str, Any],
    *,
    stochastic: bool,
) -> None:
    missing = [field for field in ARTIFACT_IDENTITY_FIELDS if field not in payload]
    if missing:
        raise ArtifactContractViolation(
            "artifact identity missing fields: " + ",".join(missing)
        )
    for field in (
        "artifact_digest",
        "dataset_digest",
        "preregistration_digest",
        "config_digest",
    ):
        if not _DIGEST.fullmatch(str(payload[field])):
            raise ArtifactContractViolation(f"{field} must be a sha256 digest")
    if payload["working_tree_clean"] is not True:
        raise ArtifactContractViolation("formal artifact requires a clean working tree")
    policy = payload["seed_policy"]
    if stochastic:
        if not isinstance(policy, Mapping):
            raise ArtifactContractViolation("random artifact requires SeedPolicy")
        SeedPolicy(
            seeds=tuple(policy.get("seeds", ())),
            aggregation=str(policy.get("aggregation", "distribution")),
            selection_policy=str(policy.get("selection_policy", "no_best_seed")),
        )
    elif policy != "none":
        raise ArtifactContractViolation(
            "deterministic artifact must declare seed_policy=none"
        )
