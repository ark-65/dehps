from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from dehps.runtime_envelope import RuntimeEnvelopeV1, RuntimeState


RUNTIME_ENVELOPE_PROJECTION_VERSION = "runtime_envelope_projection.v1"
RUNTIME_ENVELOPE_VERIFIED = "verified"
RUNTIME_ENVELOPE_UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class RuntimeEnvelopeProjection:
    status: str
    reason: str | None
    envelope: RuntimeEnvelopeV1 | None

    @classmethod
    def verified(cls, envelope: RuntimeEnvelopeV1) -> RuntimeEnvelopeProjection:
        return cls(
            status=RUNTIME_ENVELOPE_VERIFIED,
            reason=None,
            envelope=envelope,
        )

    @classmethod
    def unavailable(cls, reason: str) -> RuntimeEnvelopeProjection:
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("unavailable Runtime Envelope provenance requires a reason")
        return cls(
            status=RUNTIME_ENVELOPE_UNAVAILABLE,
            reason=reason.strip(),
            envelope=None,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "protocol": RUNTIME_ENVELOPE_PROJECTION_VERSION,
            "status": self.status,
            "reason": self.reason,
            "envelope": self.envelope.as_dict() if self.envelope is not None else None,
        }


def project_runtime_envelope(
    value: object,
    *,
    unavailable_reason: str,
    require_artifact_produced: bool = True,
) -> RuntimeEnvelopeProjection:
    """Normalize persisted Runtime Envelope evidence without inventing history.

    Absence is an explicit legacy/unavailable state. A present payload must pass
    the canonical Runtime Envelope parser and verifier; malformed evidence is a
    hard error and may not be silently downgraded to unavailable.
    """

    if value is None:
        return RuntimeEnvelopeProjection.unavailable(unavailable_reason)
    if isinstance(value, RuntimeEnvelopeV1):
        envelope = value
    elif isinstance(value, Mapping):
        envelope = RuntimeEnvelopeV1.from_dict(value)
    else:
        raise TypeError("runtime_envelope must be a RuntimeEnvelopeV1 or object")
    if require_artifact_produced and envelope.state is not RuntimeState.ARTIFACT_PRODUCED:
        raise ValueError("persisted artifact provenance requires state=artifact_produced")
    return RuntimeEnvelopeProjection.verified(envelope)


def projection_from_metadata(
    metadata: object,
    *,
    unavailable_reason: str,
) -> RuntimeEnvelopeProjection:
    if not isinstance(metadata, Mapping):
        return RuntimeEnvelopeProjection.unavailable(unavailable_reason)
    return project_runtime_envelope(
        metadata.get("runtime_envelope"),
        unavailable_reason=unavailable_reason,
    )
