from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from dehps.artifacts import atomic_write_text
from dehps.contracts import canonical_digest
from dehps.portfolio.models import (
    PORTFOLIO_AUDIT_PROTOCOL,
    PORTFOLIO_NULL_PROTOCOL,
    PortfolioAuditViolation,
    reject,
)


_CONTENT_FIELDS = (
    "artifact_version",
    "evidence_level",
    "status",
    "automatic_promotion_allowed",
    "source",
    "candidate_count",
    "candidate_pool_count",
    "portfolio_digest",
    "candidate_pool_digest",
    "metrics",
    "null_comparisons",
    "null_config",
    "null_config_digest",
    "seed_manifest",
    "provenance_gaps",
    "code_commit",
)


def _content_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    return {field: value[field] for field in _CONTENT_FIELDS}


@dataclass(frozen=True)
class PortfolioAuditArtifact:
    source: dict[str, Any]
    candidate_count: int
    candidate_pool_count: int
    portfolio_digest: str
    candidate_pool_digest: str
    metrics: dict[str, Any]
    null_comparisons: dict[str, Any]
    null_config: dict[str, Any]
    null_config_digest: str
    seed_manifest: dict[str, Any]
    provenance_gaps: tuple[str, ...]
    code_commit: str
    generated_at: str

    @classmethod
    def build(
        cls,
        *,
        source: Mapping[str, Any],
        candidate_count: int,
        candidate_pool_count: int,
        portfolio_digest: str,
        candidate_pool_digest: str,
        metrics: Mapping[str, Any],
        null_comparisons: Mapping[str, Any],
        null_config: Mapping[str, Any],
        null_config_digest: str,
        seed_manifest: Mapping[str, Any],
        provenance_gaps: list[str],
        code_commit: str,
        generated_at: str,
    ) -> PortfolioAuditArtifact:
        artifact = cls(
            source=dict(source),
            candidate_count=int(candidate_count),
            candidate_pool_count=int(candidate_pool_count),
            portfolio_digest=portfolio_digest,
            candidate_pool_digest=candidate_pool_digest,
            metrics=dict(metrics),
            null_comparisons=dict(null_comparisons),
            null_config=dict(null_config),
            null_config_digest=null_config_digest,
            seed_manifest=dict(seed_manifest),
            provenance_gaps=tuple(sorted(set(provenance_gaps))),
            code_commit=code_commit,
            generated_at=generated_at,
        )
        verify_portfolio_audit_payload(artifact.as_dict())
        return artifact

    @property
    def evidence_level(self) -> str:
        return "RESEARCH_ONLY_DIAGNOSTIC"

    @property
    def status(self) -> str:
        return "audited" if not self.provenance_gaps else "audited_with_provenance_gaps"

    def _base_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": PORTFOLIO_AUDIT_PROTOCOL,
            "evidence_level": self.evidence_level,
            "status": self.status,
            "automatic_promotion_allowed": False,
            "source": self.source,
            "candidate_count": self.candidate_count,
            "candidate_pool_count": self.candidate_pool_count,
            "portfolio_digest": self.portfolio_digest,
            "candidate_pool_digest": self.candidate_pool_digest,
            "metrics": self.metrics,
            "null_comparisons": self.null_comparisons,
            "null_config": self.null_config,
            "null_config_digest": self.null_config_digest,
            "seed_manifest": self.seed_manifest,
            "provenance_gaps": list(self.provenance_gaps),
            "code_commit": self.code_commit,
        }

    @property
    def content_digest(self) -> str:
        return canonical_digest(
            self._base_payload(),
            domain="dehps.candidate-portfolio-audit.content.v1",
        )

    @property
    def artifact_digest(self) -> str:
        return canonical_digest(
            {
                **self._base_payload(),
                "content_digest": self.content_digest,
                "generated_at": self.generated_at,
            },
            domain="dehps.candidate-portfolio-audit.artifact.v1",
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            **self._base_payload(),
            "content_digest": self.content_digest,
            "generated_at": self.generated_at,
            "artifact_digest": self.artifact_digest,
        }


def verify_portfolio_audit_payload(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        reject("portfolio_audit_artifact_parse_error", "artifact must be an object")
    payload = dict(value)
    allowed = set((*_CONTENT_FIELDS, "content_digest", "generated_at", "artifact_digest"))
    unexpected = sorted(set(payload) - allowed)
    if unexpected:
        reject(
            "portfolio_audit_artifact_fields_unexpected",
            "artifact contains fields outside the v1 schema",
            unexpected=unexpected,
        )
    missing = [
        field
        for field in (*_CONTENT_FIELDS, "content_digest", "generated_at", "artifact_digest")
        if field not in payload
    ]
    if missing:
        reject(
            "portfolio_audit_artifact_fields_missing",
            "artifact is missing required fields",
            missing=missing,
        )
    if payload["artifact_version"] != PORTFOLIO_AUDIT_PROTOCOL:
        reject("portfolio_audit_artifact_version_mismatch", "unsupported artifact version")
    if payload["evidence_level"] != "RESEARCH_ONLY_DIAGNOSTIC":
        reject(
            "portfolio_audit_evidence_level_invalid",
            "audit evidence must remain research-only diagnostic",
        )
    if payload["automatic_promotion_allowed"] is not False:
        reject(
            "portfolio_audit_promotion_boundary_violation",
            "audit artifacts may never authorize automatic promotion",
        )
    if (
        not isinstance(payload["candidate_count"], int)
        or isinstance(payload["candidate_count"], bool)
        or payload["candidate_count"] < 1
    ):
        reject("portfolio_audit_candidate_count_invalid", "candidate_count must be positive")
    if (
        not isinstance(payload["candidate_pool_count"], int)
        or isinstance(payload["candidate_pool_count"], bool)
        or payload["candidate_pool_count"] < payload["candidate_count"]
    ):
        reject(
            "portfolio_audit_pool_count_invalid",
            "candidate_pool_count must be at least candidate_count",
        )
    if not isinstance(payload["provenance_gaps"], list) or any(
        not isinstance(item, str) or not item
        for item in payload["provenance_gaps"]
    ):
        reject(
            "portfolio_audit_provenance_gaps_invalid",
            "provenance_gaps must be a list of field names",
        )
    if payload["provenance_gaps"] != sorted(set(payload["provenance_gaps"])):
        reject(
            "portfolio_audit_provenance_gaps_not_canonical",
            "provenance_gaps must be unique and sorted",
        )
    if not isinstance(payload["metrics"], Mapping) or payload["metrics"].get(
        "metric_protocol"
    ) != "candidate_portfolio_metrics.v1":
        reject(
            "portfolio_audit_metric_protocol_invalid",
            "metrics must use candidate_portfolio_metrics.v1",
        )
    if payload["metrics"].get("candidate_count") != payload["candidate_count"]:
        reject(
            "portfolio_audit_metric_count_mismatch",
            "metric candidate count must match the artifact candidate count",
        )
    for field in ("source", "null_config", "seed_manifest"):
        if not isinstance(payload[field], Mapping):
            reject(
                "portfolio_audit_object_field_invalid",
                f"{field} must be an object",
                field=field,
            )
    if not isinstance(payload["null_comparisons"], Mapping) or set(
        payload["null_comparisons"]
    ) != {
        "uniform_legal_same_budget",
        "random_from_candidate_pool",
    }:
        reject(
            "portfolio_audit_null_set_invalid",
            "both declared v1 null comparisons are required",
        )
    replicate_fields = {
        "uniform_legal_same_budget": "uniform_legal_replicates",
        "random_from_candidate_pool": "random_from_pool_replicates",
    }
    for null_key, replicate_field in replicate_fields.items():
        comparison = payload["null_comparisons"][null_key]
        if (
            not isinstance(comparison, Mapping)
            or comparison.get("protocol") != PORTFOLIO_NULL_PROTOCOL
            or comparison.get("null_key") != null_key
        ):
            reject(
                "portfolio_audit_null_protocol_invalid",
                "null comparison protocol and key must match the v1 contract",
                null_key=null_key,
            )
        if comparison.get("budget") != payload["candidate_count"]:
            reject(
                "portfolio_audit_null_budget_mismatch",
                "null comparison budget must match candidate_count",
                null_key=null_key,
            )
        if comparison.get("replicates") != payload["null_config"].get(replicate_field):
            reject(
                "portfolio_audit_null_replicates_mismatch",
                "null comparison replicates must match null_config",
                null_key=null_key,
            )
    for field in (
        "portfolio_digest",
        "candidate_pool_digest",
        "null_config_digest",
        "content_digest",
        "artifact_digest",
    ):
        digest = payload[field]
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            reject(
                "portfolio_audit_digest_invalid",
                f"{field} must be a lowercase sha256 digest",
                field=field,
            )
    expected_null_config = canonical_digest(
        payload["null_config"],
        domain="dehps.candidate-portfolio-null-config.v1",
    )
    if payload["null_config_digest"] != expected_null_config:
        reject(
            "portfolio_audit_null_config_digest_mismatch",
            "null config digest does not match canonical null config",
        )
    expected_status = (
        "audited_with_provenance_gaps" if payload["provenance_gaps"] else "audited"
    )
    if payload["status"] != expected_status:
        reject(
            "portfolio_audit_status_mismatch",
            "status must reflect provenance gaps",
        )
    expected_content = canonical_digest(
        _content_payload(payload),
        domain="dehps.candidate-portfolio-audit.content.v1",
    )
    if payload["content_digest"] != expected_content:
        reject(
            "portfolio_audit_content_digest_mismatch",
            "content digest does not match canonical audit content",
        )
    expected_artifact = canonical_digest(
        {key: item for key, item in payload.items() if key != "artifact_digest"},
        domain="dehps.candidate-portfolio-audit.artifact.v1",
    )
    if payload["artifact_digest"] != expected_artifact:
        reject(
            "portfolio_audit_artifact_digest_mismatch",
            "artifact digest does not match serialized audit artifact",
        )
    return {
        "valid": True,
        "artifact_version": payload["artifact_version"],
        "status": payload["status"],
        "content_digest": payload["content_digest"],
        "artifact_digest": payload["artifact_digest"],
    }


def write_portfolio_audit_artifact(artifact: PortfolioAuditArtifact, path: Path) -> Path:
    payload = artifact.as_dict()
    verify_portfolio_audit_payload(payload)
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return path


def load_and_verify_portfolio_audit_artifact(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PortfolioAuditViolation(
            "portfolio_audit_artifact_read_error",
            "could not read portfolio audit artifact",
            path=str(path),
        ) from exc
    return verify_portfolio_audit_payload(payload)
