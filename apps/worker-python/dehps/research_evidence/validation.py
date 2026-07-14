from __future__ import annotations

from dehps.research_evidence.models import DecisionDraft, EvidenceRecord


def validate_evidence_records(records: tuple[EvidenceRecord, ...]) -> dict[str, object]:
    failures: list[str] = []
    if not records:
        failures.append("at least one evidence record is required")
    seen = set()
    for record in records:
        if not record.content_hash:
            failures.append(f"{record.evidence_key} is missing content_hash")
        if record.content_hash in seen:
            failures.append(f"duplicate evidence content hash: {record.content_hash}")
        seen.add(record.content_hash)
        if not record.artifact_path:
            failures.append(f"{record.evidence_key} is missing artifact_path")
        if record.registry_id is None:
            # Pre-append evidence records may omit registry_id; this is a warning,
            # not invalid for build previews.
            continue
    return {"valid": not failures, "failure_reasons": failures}


def validate_decision_draft(draft: DecisionDraft) -> dict[str, object]:
    failures: list[str] = []
    if not draft.evidence_ids:
        failures.append("decision draft must cite Evidence IDs")
    if draft.proposed_status.value not in {
        "accepted_for_followup",
        "rejected",
        "inconclusive",
        "invalidated",
    }:
        failures.append(f"unsupported proposed status: {draft.proposed_status.value}")
    if draft.proposed_status.value == "rejected" and draft.rejection_scope.value == "none":
        failures.append("rejected decision drafts require a rejection scope")
    return {"valid": not failures, "failure_reasons": failures}
