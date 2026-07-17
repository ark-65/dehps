from __future__ import annotations

import pytest

from dehps.runtime_envelope import RuntimeEnvelopeViolation
from dehps.runtime_provenance import project_runtime_envelope


def test_missing_runtime_envelope_is_explicitly_unavailable() -> None:
    projection = project_runtime_envelope(
        None,
        unavailable_reason="legacy_artifact_without_runtime_envelope",
    ).as_dict()

    assert projection == {
        "protocol": "runtime_envelope_projection.v1",
        "status": "unavailable",
        "reason": "legacy_artifact_without_runtime_envelope",
        "envelope": None,
    }


def test_present_malformed_runtime_envelope_fails_closed() -> None:
    with pytest.raises(RuntimeEnvelopeViolation, match="runtime_envelope_parse_error"):
        project_runtime_envelope(
            {"envelope_version": "runtime_envelope.v1"},
            unavailable_reason="must_not_be_used",
        )
