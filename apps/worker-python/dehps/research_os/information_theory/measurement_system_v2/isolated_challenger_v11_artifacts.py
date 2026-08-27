from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dehps.config import ROOT_DIR

from . import isolated_challenger_v11_contract as contract

ENVELOPE_KEYS = {
    "schema_version",
    "artifact_type",
    "artifact_digest",
    "body",
    "parent_digests",
}
COMMON_BODY_KEYS = {
    "lineage_id",
    "task_key",
    "target_issue",
    "git_commit",
    "source_contract_digest",
    "contract_digest",
    "config_digest",
    "input_digest",
    "output_digest",
    "created_at",
    "deterministic_seed",
    "replay_status",
}
MAIL_CONFIGURATION_KEYS = {
    "transport_mode",
    "smtp_host",
    "smtp_port",
    "tls_mode",
    "sender_address_digest",
    "recipient_set_digest",
    "credential_present",
    "credential_secret_serialized",
    "auth_probe_started_at",
    "auth_probe_completed_at",
    "auth_probe_result",
    "smtp_noop_reply_code",
    "smtp_noop_reply_bytes_digest",
    "tls_peer_certificate_sha256",
    "configuration_digest",
}
DELIVERY_RECEIPT_KEYS = {
    "mail_kind",
    "delivery_key",
    "mail_envelope_digest",
    "mail_replay_digest",
    "content_digest",
    "recipient_set_digest",
    "mail_configuration_digest",
    "transport_mode",
    "simulation",
    "attempt_count",
    "client_message_id",
    "smtp_transaction_started_at",
    "smtp_data_accepted_at",
    "smtp_final_reply_code",
    "smtp_final_reply_bytes_digest",
    "tls_peer_certificate_sha256",
    "provider_message_id_or_null",
    "state",
    "error_code_or_null",
}
OPERATOR_ATTESTATION_KEYS = {
    "operator_request_id",
    "approval_decision_id",
    "execution_id",
    "payload_sha256",
    "environment",
    "scope_digest",
    "secret_values_serialized",
}
FORMAL_P3_PROJECTION_KEYS = {
    "status",
    "projection",
    "projection_digest",
    "formal_p3_artifact_digests",
    "formal_p3_aggregate_result_reads",
    "formal_p3_write_access",
}
FORMAL_P3_PENDING_KEYS = {
    "status",
    "reason_codes",
    "formal_p3_aggregate_result_reads",
    "formal_p3_write_access",
}
EMPTY_INCIDENT_HEAD_KEYS = {
    "incident_seq",
    "open_count",
    "latest_incident_digest",
}
INCIDENT_KEYS = {
    "status",
    "incident_id",
    "reason_code",
    "offending_artifact_digests",
    "opened_at",
}
INCIDENT_HEAD_KEYS = {
    "incident_seq",
    "open_count",
    "latest_incident_digest",
    "opened_at",
}
RNG_TYPES = frozenset(
    {
        "M4IsolatedCandidateRegistrationV11",
        "M4IsolatedExecutionAttemptV11",
        "M4IsolatedCandidateResultV11",
        "M4IsolatedRandomBaselineSetV11",
        "M4IsolatedPredictionV11",
    }
)


class IsolatedArtifactError(contract.IsolatedChallengerContractError):
    pass


def validate_operator_attestation_body(body: Mapping[str, Any]) -> None:
    environment = body.get("environment")
    identifiers = (
        body.get("operator_request_id"),
        body.get("approval_decision_id"),
        body.get("execution_id"),
    )
    if body.get("secret_values_serialized") is not False:
        raise IsolatedArtifactError("operator_attestation_secret_boundary_changed")
    contract.require_digest(body.get("payload_sha256"), field="payload_sha256")
    contract.require_digest(body.get("scope_digest"), field="scope_digest")
    if environment == "production":
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 1
            for value in identifiers
        ):
            raise IsolatedArtifactError("operator_attestation_identity_invalid")
    elif environment == "simulation":
        if identifiers != (0, 0, 0) or any(
            body.get(field) != "0" * 64
            for field in ("payload_sha256", "scope_digest")
        ):
            raise IsolatedArtifactError("operator_attestation_simulation_changed")
    else:
        raise IsolatedArtifactError("operator_attestation_environment_changed")


def validate_mail_configuration_body(body: Mapping[str, Any]) -> None:
    if body.get("credential_secret_serialized") is not False:
        raise IsolatedArtifactError("mail_configuration_secret_boundary_changed")
    mode = body.get("transport_mode")
    if mode == "FAKE_EPHEMERAL":
        expected_digest = contract.domain_digest(
            {"transport_mode": "FAKE_EPHEMERAL", "simulation": True},
            domain="dehps.m4.isolated-24h-challenger.mail-configuration.v11",
        )
        if (
            body.get("smtp_host") != "fake.invalid"
            or body.get("smtp_port") != 0
            or body.get("tls_mode") != "NONE"
            or body.get("credential_present") is not False
            or body.get("auth_probe_started_at") is not None
            or body.get("auth_probe_completed_at") is not None
            or body.get("auth_probe_result") != "FAKE_EPHEMERAL_ONLY"
            or body.get("smtp_noop_reply_code") is not None
            or body.get("smtp_noop_reply_bytes_digest") is not None
            or body.get("tls_peer_certificate_sha256") is not None
            or body.get("configuration_digest") != expected_digest
        ):
            raise IsolatedArtifactError("mail_configuration_simulation_changed")
    elif mode == "EXTERNAL_QQ_SMTP":
        try:
            started = datetime.fromisoformat(str(body["auth_probe_started_at"]))
            completed = datetime.fromisoformat(str(body["auth_probe_completed_at"]))
        except (KeyError, ValueError) as exc:
            raise IsolatedArtifactError("mail_configuration_probe_time_invalid") from exc
        for field in (
            "sender_address_digest",
            "recipient_set_digest",
            "smtp_noop_reply_bytes_digest",
            "tls_peer_certificate_sha256",
        ):
            contract.require_digest(body.get(field), field=field)
        expected_digest = contract.domain_digest(
            {
                "transport_mode": mode,
                "smtp_host": body.get("smtp_host"),
                "smtp_port": body.get("smtp_port"),
                "tls_mode": body.get("tls_mode"),
                "sender_address_digest": body.get("sender_address_digest"),
                "recipient_set_digest": body.get("recipient_set_digest"),
                "credential_present": body.get("credential_present"),
                "credential_secret_serialized": False,
            },
            domain="dehps.m4.isolated-24h-challenger.mail-configuration.v11",
        )
        if (
            body.get("smtp_host") != "smtp.qq.com"
            or body.get("smtp_port") != 465
            or body.get("tls_mode") != "IMPLICIT_TLS"
            or body.get("credential_present") is not True
            or body.get("auth_probe_result") != "TLS_AUTH_NOOP_VERIFIED"
            or body.get("smtp_noop_reply_code") != 250
            or started.tzinfo is None
            or completed.tzinfo is None
            or completed < started
            or body.get("configuration_digest") != expected_digest
        ):
            raise IsolatedArtifactError("mail_configuration_external_changed")
    else:
        raise IsolatedArtifactError("mail_configuration_transport_changed")
    contract.require_digest(
        body.get("sender_address_digest"), field="sender_address_digest"
    )
    contract.require_digest(
        body.get("recipient_set_digest"), field="recipient_set_digest"
    )
    contract.require_digest(
        body.get("configuration_digest"), field="configuration_digest"
    )


def _timestamp(value: str | None) -> str:
    candidate = value or datetime.now(UTC).isoformat()
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError as exc:
        raise IsolatedArtifactError("artifact_created_at_invalid") from exc
    if parsed.tzinfo is None:
        raise IsolatedArtifactError("artifact_created_at_not_aware")
    return candidate


def _seed(value: str | None, *, required: bool) -> str | None:
    if value is None:
        if required:
            raise IsolatedArtifactError("artifact_rng_seed_missing")
        return None
    if len(value) != 32 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise IsolatedArtifactError("artifact_rng_seed_invalid")
    if not required:
        raise IsolatedArtifactError("artifact_non_rng_seed_present")
    return value


def build_artifact(
    *,
    artifact_type: str,
    task_key: str,
    target_issue: str | None,
    git_commit: str,
    source_contract_digest: str,
    config_digest: str,
    parent_digests: Sequence[str],
    type_body: Mapping[str, Any],
    deterministic_seed: str | None = None,
    replay_status: str = "NOT_APPLICABLE",
    created_at: str | None = None,
) -> dict[str, Any]:
    if artifact_type not in contract.ARTIFACT_TYPES:
        raise IsolatedArtifactError("artifact_type_not_frozen")
    if not task_key.startswith("m4-isolated-24h-challenger-v11-"):
        raise IsolatedArtifactError("artifact_task_namespace_changed")
    if len(git_commit) != 40 or any(
        character not in "0123456789abcdef" for character in git_commit
    ):
        raise IsolatedArtifactError("artifact_git_commit_invalid")
    source_contract_digest = contract.require_digest(
        source_contract_digest, field="source_contract_digest"
    )
    config_digest = contract.require_digest(config_digest, field="config_digest")
    parents = [
        contract.require_digest(item, field="parent_digest") for item in parent_digests
    ]
    if len(parents) != len(set(parents)):
        raise IsolatedArtifactError("artifact_parent_duplicate")
    if target_issue is not None:
        target_issue = contract.require_issue(target_issue)
    type_payload = deepcopy(dict(type_body))
    if COMMON_BODY_KEYS.intersection(type_payload):
        raise IsolatedArtifactError("artifact_type_body_overrides_common_field")
    input_digest = contract.domain_digest(
        parents, domain="dehps.m4.isolated-24h-challenger.input-set.v11"
    )
    output_digest = contract.domain_digest(
        type_payload,
        domain=f"dehps.m4.isolated-24h-challenger.output.{artifact_type}.v11",
    )
    body: dict[str, Any] = {
        "lineage_id": contract.LINEAGE_ID,
        "task_key": task_key,
        "target_issue": target_issue,
        "git_commit": git_commit,
        "source_contract_digest": source_contract_digest,
        "contract_digest": contract.CONTRACT_DIGEST,
        "config_digest": config_digest,
        "input_digest": input_digest,
        "output_digest": output_digest,
        "created_at": _timestamp(created_at),
        "deterministic_seed": _seed(
            deterministic_seed, required=artifact_type in RNG_TYPES
        ),
        "replay_status": replay_status,
        **type_payload,
    }
    payload: dict[str, Any] = {
        "schema_version": contract.ARTIFACT_SCHEMA,
        "artifact_type": artifact_type,
        "body": body,
        "parent_digests": parents,
    }
    payload["artifact_digest"] = contract.domain_digest(
        payload, domain=contract.ARTIFACT_DOMAIN
    )
    return validate_artifact(payload)


def validate_artifact(value: Mapping[str, Any]) -> dict[str, Any]:
    payload = deepcopy(dict(value))
    if set(payload) != ENVELOPE_KEYS:
        raise IsolatedArtifactError("artifact_envelope_shape_changed")
    artifact_type = str(payload.get("artifact_type") or "")
    if (
        payload.get("schema_version") != contract.ARTIFACT_SCHEMA
        or artifact_type not in contract.ARTIFACT_TYPES
    ):
        raise IsolatedArtifactError("artifact_identity_changed")
    digest = contract.require_digest(
        payload.pop("artifact_digest"), field="artifact_digest"
    )
    if contract.domain_digest(payload, domain=contract.ARTIFACT_DOMAIN) != digest:
        raise IsolatedArtifactError("artifact_digest_mismatch")
    body = payload.get("body")
    parents = payload.get("parent_digests")
    if not isinstance(body, dict) or not isinstance(parents, list):
        raise IsolatedArtifactError("artifact_body_or_parents_invalid")
    if not COMMON_BODY_KEYS.issubset(body):
        raise IsolatedArtifactError("artifact_common_body_incomplete")
    if (
        body.get("lineage_id") != contract.LINEAGE_ID
        or body.get("contract_digest") != contract.CONTRACT_DIGEST
    ):
        raise IsolatedArtifactError("artifact_lineage_or_contract_changed")
    task_key = str(body.get("task_key") or "")
    if not task_key.startswith("m4-isolated-24h-challenger-v11-"):
        raise IsolatedArtifactError("artifact_task_namespace_changed")
    expected_input = contract.domain_digest(
        parents, domain="dehps.m4.isolated-24h-challenger.input-set.v11"
    )
    if body.get("input_digest") != expected_input:
        raise IsolatedArtifactError("artifact_input_digest_changed")
    git_commit = str(body.get("git_commit") or "")
    if len(git_commit) != 40 or any(
        character not in "0123456789abcdef" for character in git_commit
    ):
        raise IsolatedArtifactError("artifact_git_commit_invalid")
    contract.require_digest(
        body.get("source_contract_digest"), field="source_contract_digest"
    )
    contract.require_digest(body.get("config_digest"), field="config_digest")
    target_issue = body.get("target_issue")
    if target_issue is not None:
        contract.require_issue(target_issue)
    _timestamp(str(body.get("created_at") or ""))
    if body.get("replay_status") not in {"NOT_APPLICABLE", "REPLAY_VERIFIED"}:
        raise IsolatedArtifactError("artifact_replay_status_changed")
    type_body = {
        key: value for key, value in body.items() if key not in COMMON_BODY_KEYS
    }
    expected_output = contract.domain_digest(
        type_body,
        domain=f"dehps.m4.isolated-24h-challenger.output.{artifact_type}.v11",
    )
    if body.get("output_digest") != expected_output:
        raise IsolatedArtifactError("artifact_output_digest_changed")
    for item in parents:
        contract.require_digest(item, field="parent_digest")
    if len(parents) != len(set(parents)):
        raise IsolatedArtifactError("artifact_parent_duplicate")
    expected_seed_required = artifact_type in RNG_TYPES
    _seed(body.get("deterministic_seed"), required=expected_seed_required)
    if (
        artifact_type == "M4IsolatedMailConfigurationV11"
        and set(body) != COMMON_BODY_KEYS | MAIL_CONFIGURATION_KEYS
    ):
        raise IsolatedArtifactError("mail_configuration_body_shape_changed")
    if artifact_type == "M4IsolatedMailConfigurationV11":
        validate_mail_configuration_body(body)
        if body.get("config_digest") != body.get("configuration_digest"):
            raise IsolatedArtifactError("mail_configuration_common_digest_changed")
    if artifact_type == "M4IsolatedDeliveryReceiptV11":
        if set(body) != COMMON_BODY_KEYS | DELIVERY_RECEIPT_KEYS:
            raise IsolatedArtifactError("delivery_receipt_body_shape_changed")
        validate_delivery_receipt_body(body)
    exact_type_keys = {
        "M4IsolatedOperatorAttestationV11": OPERATOR_ATTESTATION_KEYS,
        "M4IsolatedFormalP3IssueProjectionV11": FORMAL_P3_PROJECTION_KEYS,
        "M4IsolatedFormalP3PendingMarkerV11": FORMAL_P3_PENDING_KEYS,
        "M4IsolatedEmptyIncidentHeadV11": EMPTY_INCIDENT_HEAD_KEYS,
        "M4IsolatedIncidentV11": INCIDENT_KEYS,
        "M4IsolatedIncidentHeadV11": INCIDENT_HEAD_KEYS,
    }.get(artifact_type)
    if exact_type_keys is not None and set(body) != COMMON_BODY_KEYS | exact_type_keys:
        raise IsolatedArtifactError("lifecycle_addendum_body_shape_changed")
    if artifact_type == "M4IsolatedOperatorAttestationV11":
        validate_operator_attestation_body(body)
    payload["artifact_digest"] = digest
    return payload


def validate_delivery_receipt_body(body: Mapping[str, Any]) -> None:
    for field in (
        "delivery_key",
        "mail_envelope_digest",
        "mail_replay_digest",
        "content_digest",
        "recipient_set_digest",
        "mail_configuration_digest",
    ):
        contract.require_digest(body.get(field), field=field)
    message_id = str(body.get("client_message_id") or "")
    delivery_key = str(body.get("delivery_key") or "")
    if not message_id.startswith(f"<{delivery_key}@") or not message_id.endswith(">"):
        raise IsolatedArtifactError("delivery_message_id_changed")
    state = body.get("state")
    simulation = body.get("simulation")
    if state == "SENT":
        try:
            started = datetime.fromisoformat(
                str(body.get("smtp_transaction_started_at") or "").replace(
                    "Z", "+00:00"
                )
            )
            accepted = datetime.fromisoformat(
                str(body.get("smtp_data_accepted_at") or "").replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise IsolatedArtifactError("delivery_sent_timestamp_invalid") from exc
        if (
            simulation is not False
            or body.get("transport_mode") != "EXTERNAL_QQ_SMTP"
            or body.get("attempt_count") != 1
            or body.get("smtp_final_reply_code") != 250
            or started.tzinfo is None
            or accepted.tzinfo is None
            or accepted < started
            or not isinstance(body.get("smtp_final_reply_bytes_digest"), str)
            or not isinstance(body.get("tls_peer_certificate_sha256"), str)
            or body.get("error_code_or_null") is not None
        ):
            raise IsolatedArtifactError("delivery_sent_condition_failed")
        contract.require_digest(
            body.get("smtp_final_reply_bytes_digest"),
            field="smtp_final_reply_bytes_digest",
        )
        contract.require_digest(
            body.get("tls_peer_certificate_sha256"),
            field="tls_peer_certificate_sha256",
        )
    elif state == "UNCERTAIN":
        try:
            started = datetime.fromisoformat(
                str(body.get("smtp_transaction_started_at") or "").replace(
                    "Z", "+00:00"
                )
            )
        except ValueError as exc:
            raise IsolatedArtifactError("delivery_uncertain_timestamp_invalid") from exc
        if (
            simulation is not False
            or body.get("transport_mode") != "EXTERNAL_QQ_SMTP"
            or body.get("attempt_count") != 1
            or started.tzinfo is None
            or body.get("smtp_data_accepted_at") is not None
            or body.get("smtp_final_reply_code") is not None
            or body.get("error_code_or_null") in {None, ""}
        ):
            raise IsolatedArtifactError("delivery_uncertain_condition_failed")
    elif state == "SIMULATED":
        if (
            simulation is not True
            or body.get("transport_mode") != "FAKE_EPHEMERAL"
            or body.get("attempt_count") != 0
            or any(
                body.get(field) is not None
                for field in (
                    "smtp_transaction_started_at",
                    "smtp_data_accepted_at",
                    "smtp_final_reply_code",
                    "smtp_final_reply_bytes_digest",
                    "tls_peer_certificate_sha256",
                    "provider_message_id_or_null",
                    "error_code_or_null",
                )
            )
        ):
            raise IsolatedArtifactError("delivery_simulation_condition_failed")
    else:
        raise IsolatedArtifactError("delivery_receipt_state_invalid")


def replay_artifact(
    artifact: Mapping[str, Any], *, expected_parent_digests: Sequence[str] | None = None
) -> dict[str, Any]:
    parsed = validate_artifact(artifact)
    if expected_parent_digests is not None and parsed["parent_digests"] != list(
        expected_parent_digests
    ):
        raise IsolatedArtifactError("artifact_replay_parent_chain_changed")
    reconstructed = deepcopy(parsed)
    digest = reconstructed.pop("artifact_digest")
    if contract.domain_digest(reconstructed, domain=contract.ARTIFACT_DOMAIN) != digest:
        raise IsolatedArtifactError("artifact_replay_failed")
    return {
        "status": "REPLAY_VERIFIED",
        "artifact_digest": digest,
        "artifact_type": parsed["artifact_type"],
        "parent_digests": list(parsed["parent_digests"]),
        "same_artifact_identity": True,
        "same_parent_identity": True,
        "manual_input_assembly": False,
        "dispatch_performed": False,
    }


def load_source_contract(*, root_dir: Path = ROOT_DIR) -> dict[str, Any]:
    root = root_dir.resolve()
    path = (root / contract.SOURCE_CONTRACT_PATH).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise IsolatedArtifactError("source_contract_missing")
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema_version",
        "artifact_type",
        "artifact_digest",
        "source_set_digest",
        "contract_key",
        "contract_digest",
        "governance_bindings",
        "runtime_versions",
        "source_entries",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise IsolatedArtifactError("source_contract_shape_changed")
    if (
        payload["schema_version"] != contract.SOURCE_SCHEMA
        or payload["artifact_type"] != contract.SOURCE_ARTIFACT_TYPE
        or payload["contract_key"] != contract.CONTRACT_KEY
        or payload["contract_digest"] != contract.CONTRACT_DIGEST
    ):
        raise IsolatedArtifactError("source_contract_identity_changed")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in payload.get("source_entries", []):
        if not isinstance(raw, dict) or set(raw) != {"path", "sha256", "bytes"}:
            raise IsolatedArtifactError("source_entry_shape_changed")
        relative = str(raw["path"])
        source = (root / relative).resolve()
        if relative in seen or not source.is_relative_to(root) or not source.is_file():
            raise IsolatedArtifactError("source_entry_path_changed")
        content = source.read_bytes()
        sha = hashlib.sha256(content).hexdigest()
        if sha != raw["sha256"] or len(content) != raw["bytes"]:
            raise IsolatedArtifactError("source_entry_bytes_changed")
        seen.add(relative)
        normalized.append({"path": relative, "sha256": sha, "bytes": len(content)})
    if not normalized:
        raise IsolatedArtifactError("source_entries_missing")
    source_set_digest = contract.domain_digest(
        {"source_entries": normalized}, domain=contract.SOURCE_SET_DOMAIN
    )
    identity = deepcopy(payload)
    artifact_digest = contract.require_digest(
        identity.pop("artifact_digest"), field="source_artifact_digest"
    )
    if (
        payload["source_set_digest"] != source_set_digest
        or contract.domain_digest(identity, domain=contract.SOURCE_DOMAIN)
        != artifact_digest
    ):
        raise IsolatedArtifactError("source_contract_digest_changed")
    return payload


def content_sha256(value: bytes | str) -> str:
    raw = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(raw).hexdigest()
