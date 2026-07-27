from __future__ import annotations

from typing import Any

from dehps.contracts import canonical_digest


SEED_DERIVATION_DOMAIN = "dehps.m4-p2.seed-domain.v1"
M4_P2_SEED_DOMAINS = frozenset(
    {
        "M4_P2_CALIBRATION",
        "M4_P2_EVALUATION_DATASET",
        "M4_P2_BOOTSTRAP",
        "M4_P2_STATIONARY_BOOTSTRAP",
        "M4_P2_ISSUE_PERMUTATION",
        "M4_P2_NUMBER_PERMUTATION",
        "M4_P2_CIRCULAR_SHIFT",
        "M4_P2_RANDOM_FEATURE",
        "M4_P2_RANDOM_SCORE",
        "M4_P2_POWER_REPLICATE",
        "M4_P2_SHARD_ASSIGNMENT",
    }
)


def derive_m4_p2_seed(
    *,
    root_seed_set_digest: str,
    seed_domain: str,
    scenario_id: str,
    method_id: str,
    replicate_index: int,
    parent_run_digest: str,
) -> dict[str, Any]:
    """Derive a stable child stream identity without creating or consuming RNG output."""
    if seed_domain not in M4_P2_SEED_DOMAINS:
        raise ValueError("unknown M4 P2 seed domain")
    for name, value in (
        ("root_seed_set_digest", root_seed_set_digest),
        ("parent_run_digest", parent_run_digest),
    ):
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError(f"{name} must be a lowercase sha256 digest")
    if not scenario_id or not method_id:
        raise ValueError("scenario_id and method_id are required")
    if replicate_index < 0:
        raise ValueError("replicate_index must be non-negative")
    identity = {
        "root_seed_set_digest": root_seed_set_digest,
        "seed_domain": seed_domain,
        "scenario_id": scenario_id,
        "method_id": method_id,
        "replicate_index": replicate_index,
        "parent_run_digest": parent_run_digest,
    }
    seed_digest = canonical_digest(identity, domain=SEED_DERIVATION_DOMAIN)
    return {
        "identity": identity,
        "seed_digest": seed_digest,
        "seed": int(seed_digest[:16], 16),
    }
