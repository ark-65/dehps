from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime, timezone
from enum import Enum
from hashlib import sha256
from typing import Any


_CONTRACT_FAMILY_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")
_SEMANTIC_VERSION_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _canonical_value(value: Any) -> Any:
    # Primitive values dominate large numerical evidence artifacts. Resolve
    # them before the comparatively expensive dataclass and ABC checks while
    # preserving the exact canonical JSON representation.
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("canonical payloads require finite floats")
        return value
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: _canonical_value(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Enum):
        return _canonical_value(value.value)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("canonical datetimes require an explicit timezone")
        normalized = value
        return normalized.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("canonical mappings require string keys")
            normalized[key] = _canonical_value(item)
        return normalized
    if isinstance(value, (set, frozenset)):
        raise TypeError("canonical payloads may not contain unordered collections")
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_canonical_value(item) for item in value]
    raise TypeError(f"unsupported canonical payload type: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    """Return the sole canonical JSON representation used by contract identities."""

    return json.dumps(
        _canonical_value(value),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_digest(value: Any, *, domain: str) -> str:
    if not domain.strip():
        raise ValueError("digest domain must be non-empty")
    encoded = f"{domain}\x00{canonical_json(value)}".encode("utf-8")
    return sha256(encoded).hexdigest()


def canonical_digest_prevalidated_primitives(
    value: Any,
    *,
    domain: str,
) -> str:
    """Digest an internally generated primitive JSON tree without renormalizing.

    Callers must supply only string-keyed mappings, sequences, finite floats,
    strings, integers, booleans, and ``None``. The serialized bytes are
    identical to ``canonical_digest`` for that input.
    """

    if not domain.strip():
        raise ValueError("digest domain must be non-empty")
    serialized = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return sha256(f"{domain}\x00{serialized}".encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ContractRef:
    """Immutable semantic identity; implementation versions are deliberately separate."""

    family: str
    semantic_version: str
    schema_version: str
    normative_digest: str
    golden_suite_digest: str

    def __post_init__(self) -> None:
        if not _CONTRACT_FAMILY_PATTERN.fullmatch(self.family):
            raise ValueError(f"invalid contract family: {self.family!r}")
        if not _SEMANTIC_VERSION_PATTERN.fullmatch(self.semantic_version):
            raise ValueError(f"invalid semantic version: {self.semantic_version!r}")
        if not self.schema_version.strip():
            raise ValueError("contract schema_version must be non-empty")
        for name, value in (
            ("normative_digest", self.normative_digest),
            ("golden_suite_digest", self.golden_suite_digest),
        ):
            if not _DIGEST_PATTERN.fullmatch(value):
                raise ValueError(f"{name} must be a lowercase sha256 digest")

    @classmethod
    def from_definition(
        cls,
        *,
        family: str,
        semantic_version: str,
        schema_version: str,
        normative_definition: Mapping[str, Any],
        golden_suite: Mapping[str, Any],
    ) -> ContractRef:
        return cls(
            family=family,
            semantic_version=semantic_version,
            schema_version=schema_version,
            normative_digest=canonical_digest(
                normative_definition,
                domain="dehps.contract.normative.v1",
            ),
            golden_suite_digest=canonical_digest(
                golden_suite,
                domain="dehps.contract.golden-suite.v1",
            ),
        )

    @property
    def key(self) -> str:
        return f"{self.family}.v{self.semantic_version}"

    @property
    def major_version(self) -> int:
        return int(self.semantic_version.split(".", maxsplit=1)[0])

    def normatively_equals(self, other: object) -> bool:
        return isinstance(other, ContractRef) and self.normative_identity() == other.normative_identity()

    def normative_identity(self) -> dict[str, str]:
        return {
            "family": self.family,
            "semantic_version": self.semantic_version,
            "schema_version": self.schema_version,
            "normative_digest": self.normative_digest,
        }

    def as_dict(self) -> dict[str, str]:
        return {
            **self.normative_identity(),
            "contract_key": self.key,
            "golden_suite_digest": self.golden_suite_digest,
        }


@dataclass(frozen=True)
class ContractRequirement:
    """Explicit compatibility rule; SemVer is metadata, never an implicit permission."""

    dependency_family: str
    accepted_versions: tuple[str, ...]
    accepted_schema_versions: tuple[str, ...]
    accepted_normative_digests: tuple[str, ...]

    def __post_init__(self) -> None:
        if not _CONTRACT_FAMILY_PATTERN.fullmatch(self.dependency_family):
            raise ValueError(f"invalid dependency family: {self.dependency_family!r}")
        if not self.accepted_versions:
            raise ValueError("compatibility rules require at least one accepted version")
        if not self.accepted_schema_versions:
            raise ValueError("compatibility rules require at least one schema version")
        if not self.accepted_normative_digests:
            raise ValueError("compatibility rules require at least one normative digest")
        if any(not _SEMANTIC_VERSION_PATTERN.fullmatch(value) for value in self.accepted_versions):
            raise ValueError("compatibility rules contain an invalid semantic version")
        if any(not value.strip() for value in self.accepted_schema_versions):
            raise ValueError("compatibility rules contain an empty schema version")
        if any(not _DIGEST_PATTERN.fullmatch(value) for value in self.accepted_normative_digests):
            raise ValueError("compatibility rules contain an invalid normative digest")

    @classmethod
    def exact(cls, dependency: ContractRef) -> ContractRequirement:
        return cls(
            dependency_family=dependency.family,
            accepted_versions=(dependency.semantic_version,),
            accepted_schema_versions=(dependency.schema_version,),
            accepted_normative_digests=(dependency.normative_digest,),
        )


class ContractCompatibilityError(ValueError):
    def __init__(
        self,
        *,
        code: str,
        consumer: ContractRef,
        dependency: ContractRef,
        requirement: ContractRequirement,
    ) -> None:
        self.code = code
        self.consumer = consumer
        self.dependency = dependency
        self.requirement = requirement
        super().__init__(
            f"{code}: {consumer.key} rejects {dependency.key} "
            f"for dependency family {requirement.dependency_family}"
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "consumer": self.consumer.as_dict(),
            "dependency": self.dependency.as_dict(),
            "requirement": {
                "dependency_family": self.requirement.dependency_family,
                "accepted_versions": list(self.requirement.accepted_versions),
                "accepted_schema_versions": list(self.requirement.accepted_schema_versions),
                "accepted_normative_digests": list(self.requirement.accepted_normative_digests),
            },
        }


def require_contract_compatibility(
    *,
    consumer: ContractRef,
    dependency: ContractRef,
    requirement: ContractRequirement,
) -> None:
    if dependency.family != requirement.dependency_family:
        code = "contract_dependency_family_mismatch"
    elif dependency.semantic_version not in requirement.accepted_versions:
        code = "unsupported_contract_version"
    elif dependency.schema_version not in requirement.accepted_schema_versions:
        code = "unsupported_contract_schema"
    elif dependency.normative_digest not in requirement.accepted_normative_digests:
        code = "contract_normative_digest_mismatch"
    else:
        return
    raise ContractCompatibilityError(
        code=code,
        consumer=consumer,
        dependency=dependency,
        requirement=requirement,
    )
