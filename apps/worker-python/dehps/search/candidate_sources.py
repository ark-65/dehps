from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateSourceMetadata:
    source_key: str
    protocol_version: str
