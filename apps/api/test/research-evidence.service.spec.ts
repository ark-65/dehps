import assert from 'node:assert/strict';
import { test } from 'node:test';
import { BadRequestException, NotFoundException } from '@nestjs/common';
import { mapEvidence } from '../src/research-evidence/research-evidence.repository';
import { ResearchEvidenceReadService } from '../src/research-evidence/research-evidence.service';
import { ResearchEvidenceReadRepository, ResearchEvidenceRecord } from '../src/research-evidence/research-evidence.types';

const evidence: ResearchEvidenceRecord = {
  id: 1,
  evidenceKey: 'evidence-1',
  hypothesisKey: 'hypothesis-1',
  experimentKey: 'experiment-1',
  evidenceType: 'round25_metric',
  direction: 'neutral',
  summary: 'summary',
  metrics: { adjusted_p_value: 1 },
  artifactPath: 'data/output/a.json',
  contentHash: 'hash',
  observedAt: '2026-07-14T00:00:00.000Z',
  createdAt: '2026-07-14T00:00:00.000Z',
  metadata: { evidence_key: 'evidence-1' },
};

function repository(): ResearchEvidenceReadRepository {
  return {
    async listEvidence() { return [evidence]; },
    async getEvidence(key) { return ['1', 'evidence-1'].includes(key) ? evidence : null; },
    async countEvidence() { return 1; },
  };
}

test('research evidence service exposes read-only evidence records', async () => {
  const service = new ResearchEvidenceReadService(repository());

  const list = await service.evidence(25, 4);
  const item = await service.evidenceByKey('evidence-1');
  const status = await service.status();

  assert.equal(list.items[0].evidenceKey, 'evidence-1');
  assert.deepEqual({ limit: list.limit, offset: list.offset }, { limit: 25, offset: 4 });
  assert.equal(item.data.direction, 'neutral');
  assert.equal(status.writeRoutesEnabled, false);
});

test('research evidence service rejects missing evidence and invalid pagination', async () => {
  const service = new ResearchEvidenceReadService(repository());

  await assert.rejects(() => service.evidenceByKey('missing'), NotFoundException);
  await assert.rejects(() => service.evidence(0, 0), BadRequestException);
  await assert.rejects(() => service.evidence(10, -1), BadRequestException);
});

test('postgres evidence mapper parses metadata evidence key', () => {
  const mapped = mapEvidence({
    id: 7,
    hypothesis_key: 'hypothesis-1',
    experiment_key: 'experiment-1',
    evidence_type: 'round25_metric',
    direction: 'supporting',
    summary: 'summary',
    metrics_json: { effect_size: 0.2 },
    artifact_path: 'data/output/a.json',
    content_hash: 'hash',
    observed_at: new Date('2026-07-14T00:00:00Z'),
    created_at: new Date('2026-07-14T00:00:00Z'),
    metadata_json: { evidence_key: 'evidence-key' },
  });

  assert.equal(mapped.evidenceKey, 'evidence-key');
  assert.equal(mapped.hypothesisKey, 'hypothesis-1');
});
