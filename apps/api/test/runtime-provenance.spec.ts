import assert from 'node:assert/strict';
import { test } from 'node:test';
import { normalizeRuntimeEnvelopeProjection } from '../src/runtime-provenance';

test('historical metadata is unavailable without an invented envelope', () => {
    assert.deepEqual(normalizeRuntimeEnvelopeProjection({}), {
      protocol: 'runtime_envelope_projection.v1',
      status: 'unavailable',
      reason: 'legacy_training_snapshot_without_runtime_envelope',
      envelope: null,
    });
});

test('worker-verified artifact projection is carried unchanged', () => {
    const projection = {
      protocol: 'runtime_envelope_projection.v1' as const,
      status: 'verified' as const,
      reason: null,
      envelope: {
        envelope_version: 'runtime_envelope.v1',
        state: 'artifact_produced',
        envelope_digest: 'a'.repeat(64),
      },
    };

    assert.equal(normalizeRuntimeEnvelopeProjection({ runtime_envelope_projection: projection }), projection);
});

test('malformed stored provenance fails closed', () => {
    assert.throws(() => normalizeRuntimeEnvelopeProjection({
      runtime_envelope_projection: {
        protocol: 'runtime_envelope_projection.v1',
        status: 'verified',
        reason: null,
        envelope: { envelope_digest: 'not-a-digest' },
      },
    }), /invalid verified Runtime Envelope summary/);
});
