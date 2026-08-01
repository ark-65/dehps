from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from dehps.input_contracts.candidate_abi import (
    CandidateCompiler,
    CandidateManifest,
    CandidateUniverseManifest,
    candidate_unrank,
)
from dehps.contracts import canonical_digest
from dehps.prediction.v2.contracts import SHADOW_ROUTE, require_issue, seal_artifact, verify_artifact
from dehps.prediction.v2.experts import FusionRouter, diversity_diagnostics


UNIVERSE = CandidateUniverseManifest(domain_size=33, pick_count=6)


def _sample_lex_ids(*, seed_material: bytes, count: int) -> list[int]:
    if count < 1 or count > UNIVERSE.cardinality:
        raise ValueError("candidate count is outside the legal universe")
    accepted: list[int] = []
    seen: set[int] = set()
    counter = 0
    cutoff = (1 << 256) - ((1 << 256) % UNIVERSE.cardinality)
    while len(accepted) < count:
        block = hashlib.sha256(
            b"dehps.prediction-v2.null-sampler.v1\x00"
            + seed_material
            + counter.to_bytes(8, "big")
        ).digest()
        counter += 1
        raw = int.from_bytes(block, "big")
        if raw >= cutoff:
            continue
        lex_id = raw % UNIVERSE.cardinality
        if lex_id not in seen:
            seen.add(lex_id)
            accepted.append(lex_id)
    return accepted


def generate_shadow_pool(
    *,
    contract: Mapping[str, Any],
    state: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    verified_contract = verify_artifact(
        contract,
        domain="dehps.prediction-v2.shadow-contract.v1",
    )
    verified_state = verify_artifact(
        state,
        domain="dehps.prediction-v2.state-artifact.v1",
    )
    contract_digest = str(verified_contract["artifact_digest"])
    state_digest = str(verified_state["artifact_digest"])
    as_of = require_issue(verified_state.get("as_of_issue"), field="as_of_issue")
    target = require_issue(verified_state.get("target_issue"), field="target_issue")
    pool_size = int(verified_contract["pool_size"])
    top_size = int(verified_contract["top_size"])
    router = FusionRouter().select_route(verified_state)
    if router["route"] != SHADOW_ROUTE:
        raise ValueError("Prediction v2 shadow generation must use BASELINE_ONLY")
    seed_payload = {
        "contract_digest": contract_digest,
        "state_digest": state_digest,
        "history_digest": verified_state["history_digest"],
        "as_of_issue": as_of,
        "target_issue": target,
        "pool_size": pool_size,
        "top_size": top_size,
        "route": SHADOW_ROUTE,
    }
    seed_digest = canonical_digest(seed_payload, domain="dehps.prediction-v2.seed.v1")
    ordered_lex_ids = _sample_lex_ids(seed_material=bytes.fromhex(seed_digest), count=pool_size)
    ordered_candidates = [candidate_unrank(value, universe=UNIVERSE) for value in ordered_lex_ids]
    abi_manifest = CandidateManifest.from_candidates(
        universe=UNIVERSE,
        candidates=sorted(ordered_candidates),
    )
    package = CandidateCompiler().compile(abi_manifest)
    pool = seal_artifact(
        {
            "schema_version": "dehps-prediction-v2-shadow-pool-artifact.v1",
            "artifact_type": "PredictionV2ShadowPoolArtifact.v1",
            "shadow_only": True,
            "as_of_issue": as_of,
            "target_issue": target,
            "contract_digest": contract_digest,
            "state_artifact_digest": state_digest,
            "history_digest": verified_state["history_digest"],
            "seed_digest": seed_digest,
            "route": SHADOW_ROUTE,
            "signal_bearing_experts_used": [],
            "candidate_count": pool_size,
            "ordered_lex_ids": ordered_lex_ids,
            "candidate_abi": package.runtime_envelope.as_dict(),
            "diversity_diagnostics": diversity_diagnostics(ordered_candidates),
            "historical_evidence": "NOT_RUN",
            "promotion_gate_opened": False,
            "parent_digests": [contract_digest, state_digest],
        },
        domain="dehps.prediction-v2.shadow-pool-artifact.v1",
    )
    top_candidates = ordered_candidates[:top_size]
    top100 = seal_artifact(
        {
            "schema_version": "dehps-prediction-v2-shadow-top100-artifact.v1",
            "artifact_type": "PredictionV2ShadowTop100Artifact.v1",
            "shadow_only": True,
            "as_of_issue": as_of,
            "target_issue": target,
            "contract_digest": contract_digest,
            "state_artifact_digest": state_digest,
            "pool_artifact_digest": pool["artifact_digest"],
            "route": SHADOW_ROUTE,
            "ranking_semantics": "DETERMINISTIC_LEGAL_NULL_ORDER",
            "candidate_count": top_size,
            "candidates": [
                {"rank": rank, "lex_id": ordered_lex_ids[rank - 1], "red_numbers": list(row)}
                for rank, row in enumerate(top_candidates, start=1)
            ],
            "diversity_diagnostics": diversity_diagnostics(top_candidates),
            "historical_evidence": "NOT_RUN",
            "promotion_gate_opened": False,
            "parent_digests": [pool["artifact_digest"]],
        },
        domain="dehps.prediction-v2.shadow-top100-artifact.v1",
    )
    return pool, top100
