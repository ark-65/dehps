import assert from 'node:assert/strict';
import { test } from 'node:test';
import { BadRequestException, NotFoundException } from '@nestjs/common';
import { ResearchHypothesisReadService } from '../src/research-hypotheses/research-hypothesis.service';
import { HypothesisReadRepository } from '../src/research-hypotheses/research-hypothesis.types';
import { mapHypothesis } from '../src/research-hypotheses/research-hypothesis.repository';

const family = {
  id: 1, familyKey: 'family-1', title: 'Family', description: '', mechanism: 'mechanism',
  status: 'active', rejectionScope: 'none', rejectionReason: null, reopenCondition: null,
  createdAt: '2026-07-13T00:00:00.000Z', updatedAt: '2026-07-13T00:00:00.000Z',
  resolvedAt: null, metadata: { source: 'manual' },
};
const hypothesis = {
  id: 2, hypothesisKey: 'hypothesis-1', familyId: 1, familyKey: 'family-1', parentHypothesisId: null,
  title: 'Hypothesis', statement: 'statement', mechanism: 'mechanism', nullHypothesis: 'null',
  minimalNonNull: 'minimal', invariants: [], baselineDefinition: {}, metricDefinition: {},
  failureCondition: {}, selfDeceptionRisk: [], status: 'proposed', rejectionScope: 'none',
  rejectionReason: null, reopenCondition: null, createdAt: family.createdAt, updatedAt: family.updatedAt,
  preregisteredAt: null, startedAt: null, resolvedAt: null, metadata: {},
};

function repository(): HypothesisReadRepository {
  return {
    async listFamilies() { return [family]; },
    async getFamily(key) { return key === family.familyKey ? family : null; },
    async listHypotheses() { return [hypothesis]; },
    async getHypothesis(key) { return key === hypothesis.hypothesisKey ? hypothesis : null; },
    async listExperiments() { return []; },
    async listEvidence() { return []; },
    async listDecisions() { return []; },
  };
}

test('hypothesis service lists, filters, and paginates typed entities', async () => {
  const calls: unknown[] = [];
  const repo = repository();
  const original = repo.listHypotheses;
  repo.listHypotheses = async (query) => { calls.push(query); return original(query); };
  const service = new ResearchHypothesisReadService(repo);

  const result = await service.listHypotheses({
    status: 'proposed', familyKey: ' family-1 ', createdAfter: '2026-01-01T00:00:00Z', limit: 25, offset: 5,
  });

  assert.equal(result.entity, 'hypothesis');
  assert.equal(result.items[0].hypothesisKey, 'hypothesis-1');
  assert.equal((calls[0] as any).familyKey, 'family-1');
  assert.equal((calls[0] as any).limit, 25);
  assert.equal((calls[0] as any).offset, 5);
  assert.ok((calls[0] as any).createdAfter instanceof Date);
});

test('hypothesis service returns 404 for missing detail and child collections', async () => {
  const service = new ResearchHypothesisReadService(repository());
  await assert.rejects(() => service.getFamily('missing'), NotFoundException);
  await assert.rejects(() => service.getHypothesis('missing'), NotFoundException);
  await assert.rejects(() => service.listEvidence('missing', {}), NotFoundException);
});

test('hypothesis service rejects invalid filters and pagination', async () => {
  const service = new ResearchHypothesisReadService(repository());
  await assert.rejects(() => service.listHypotheses({ status: 'invented' }), BadRequestException);
  await assert.rejects(() => service.listFamilies({ limit: 0 }), BadRequestException);
  await assert.rejects(
    () => service.listHypotheses({ createdAfter: '2026-02-01', createdBefore: '2026-01-01' }),
    BadRequestException,
  );
});

test('postgres mapping normalizes JSON strings into parsed values', () => {
  const mapped = mapHypothesis({
    id: '2', hypothesis_key: 'hypothesis-1', family_id: '1', family_key: 'family-1',
    parent_hypothesis_id: null, title: 'Hypothesis', statement: 'statement', mechanism: 'mechanism',
    null_hypothesis: 'null', minimal_non_null: 'minimal', invariants_json: '["frozen"]',
    baseline_definition_json: '{"key":"baseline"}', metric_definition_json: '{"metric":"objective"}',
    failure_condition_json: '{"failed":true}', self_deception_risk_json: '["seed"]', status: 'proposed',
    rejection_scope: 'none', rejection_reason: null, reopen_condition: null,
    created_at: '2026-07-13T00:00:00Z', updated_at: '2026-07-13T00:00:00Z',
    preregistered_at: null, started_at: null, resolved_at: null, metadata_json: '{"source":"manual"}',
  });

  assert.deepEqual(mapped.invariants, ['frozen']);
  assert.deepEqual(mapped.baselineDefinition, { key: 'baseline' });
  assert.deepEqual(mapped.metadata, { source: 'manual' });
});
