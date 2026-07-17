export type RuntimeEnvelopeProjection = {
  protocol: 'runtime_envelope_projection.v1';
  status: 'verified' | 'unavailable';
  reason: string | null;
  envelope: Record<string, unknown> | null;
};

const DIGEST = /^[0-9a-f]{64}$/;

export function normalizeRuntimeEnvelopeProjection(
  metadata: Record<string, unknown>,
): RuntimeEnvelopeProjection {
  const raw = metadata.runtime_envelope_projection;
  if (raw === undefined || raw === null) {
    return {
      protocol: 'runtime_envelope_projection.v1',
      status: 'unavailable',
      reason: 'legacy_training_snapshot_without_runtime_envelope',
      envelope: null,
    };
  }
  if (typeof raw !== 'object' || Array.isArray(raw)) {
    throw new Error('runtime_envelope_projection must be an object');
  }
  const projection = raw as Record<string, unknown>;
  if (projection.protocol !== 'runtime_envelope_projection.v1') {
    throw new Error('unsupported runtime_envelope_projection protocol');
  }
  if (projection.status === 'unavailable') {
    if (typeof projection.reason !== 'string' || !projection.reason.trim() || projection.envelope !== null) {
      throw new Error('invalid unavailable runtime_envelope_projection');
    }
    return projection as RuntimeEnvelopeProjection;
  }
  if (projection.status !== 'verified') {
    throw new Error('unknown runtime_envelope_projection status');
  }
  if (projection.reason !== null || typeof projection.envelope !== 'object' || projection.envelope === null || Array.isArray(projection.envelope)) {
    throw new Error('invalid verified runtime_envelope_projection');
  }
  const envelope = projection.envelope as Record<string, unknown>;
  if (
    envelope.envelope_version !== 'runtime_envelope.v1'
    || envelope.state !== 'artifact_produced'
    || typeof envelope.envelope_digest !== 'string'
    || !DIGEST.test(envelope.envelope_digest)
  ) {
    throw new Error('invalid verified Runtime Envelope summary');
  }
  return projection as RuntimeEnvelopeProjection;
}
