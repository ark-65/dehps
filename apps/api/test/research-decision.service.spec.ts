import assert from 'node:assert/strict';
import { test } from 'node:test';
import { BadRequestException, NotFoundException } from '@nestjs/common';
import { mapDecision } from '../src/research-decision/research-decision.repository';
import { ResearchDecisionReadService } from '../src/research-decision/research-decision.service';
import { ResearchDecisionReadRepository, ResearchDecisionRecord } from '../src/research-decision/research-decision.types';

const decision: ResearchDecisionRecord = {
  key: 'decision-1',
  requestKey: 'request-1',
  status: 'submitted',
  proposedStatus: 'inconclusive',
  hypothesisKey: 'hypothesis-1',
  evidenceIds: [1],
  payload: { proposed_status: 'inconclusive' },
  executionResult: {},
  createdAt: '2026-07-14T00:00:00.000Z',
  resolvedAt: null,
};

function repository(): ResearchDecisionReadRepository {
  return {
    async listDecisions() { return [decision]; },
    async getDecision(key) { return ['decision-1', 'request-1'].includes(key) ? decision : null; },
    async reviewStatus() { return { pending: 1, completed: 0, rejected: 0 }; },
  };
}

test('research decision service exposes read-only decision drafts and review status', async () => {
  const service = new ResearchDecisionReadService(repository());

  const list = await service.decisions(25, 4);
  const item = await service.decision('decision-1');
  const status = await service.status();

  assert.equal(list.items[0].proposedStatus, 'inconclusive');
  assert.deepEqual({ limit: list.limit, offset: list.offset }, { limit: 25, offset: 4 });
  assert.equal(item.data.hypothesisKey, 'hypothesis-1');
  assert.equal(status.pending, 1);
  assert.equal(status.writeRoutesEnabled, false);
});

test('research decision service rejects missing decisions and invalid pagination', async () => {
  const service = new ResearchDecisionReadService(repository());

  await assert.rejects(() => service.decision('missing'), NotFoundException);
  await assert.rejects(() => service.decisions(0, 0), BadRequestException);
  await assert.rejects(() => service.decisions(10, -1), BadRequestException);
});

test('postgres decision mapper parses request payload and latest execution result', () => {
  const mapped = mapDecision({
    request_key: 'request-1',
    status: 'completed',
    payload_json: { hypothesis_key: 'hypothesis-1', proposed_status: 'inconclusive', evidence_ids: [1] },
    metadata_json: { decision_key: 'decision-key' },
    result_json: { registry_update: { hypothesis_status: 'inconclusive' } },
    created_at: new Date('2026-07-14T00:00:00Z'),
    resolved_at: null,
  });

  assert.equal(mapped.key, 'decision-key');
  assert.equal(mapped.executionResult.registry_update?.['hypothesis_status'], 'inconclusive');
});
