"""Frozen definitions preserved from dehps/prediction/v2/generator.py.

Original files remain the legacy compatibility implementation. This release-local
copy has explicit calculation-only imports; scientific bodies are checked against
the originals. No historical digest or source contract is rewritten.
"""
from __future__ import annotations

import hashlib
from dehps.input_contracts.candidate_abi import CandidateUniverseManifest


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
