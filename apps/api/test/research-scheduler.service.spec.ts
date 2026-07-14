import assert from 'node:assert/strict';
import { test } from 'node:test';
import { BadRequestException } from '@nestjs/common';
import { mapSchedulerQueue } from '../src/research-scheduler/research-scheduler.repository';
import { ResearchSchedulerReadService } from '../src/research-scheduler/research-scheduler.service';
import { ResearchSchedulerQueueRecord, ResearchSchedulerReadRepository } from '../src/research-scheduler/research-scheduler.types';

const queueItem: ResearchSchedulerQueueRecord = {
  id: 1,
  queueKey: 'scheduler-create_proposal_request-abc',
  queueStatus: 'proposal',
  action: 'create_proposal_request',
  priorityScore: 0.65,
  targetHypothesisKey: null,
  targetFamilyKey: null,
  targetExperimentKey: null,
  requestKey: 'research-scheduler-abc',
  requestStatus: 'submitted',
  contextFingerprint: 'fingerprint',
  reason: { reason_code: 'new_proposal_needed' },
  budget: { proposal_quota: 1 },
  policy: { priority_engine: 'deterministic-v1' },
  createdBy: 'research:scheduler',
  createdAt: '2026-07-14T00:00:00.000Z',
  updatedAt: '2026-07-14T00:00:00.000Z',
  completedAt: null,
  metadata: { schema_version: 'autonomous-research-scheduler-v1' },
};

function repository(): ResearchSchedulerReadRepository {
  return {
    async listQueue() { return [queueItem]; },
    async latestQueueItem() { return queueItem; },
    async countOpenQueue() { return 1; },
    async countSchedulerRequests() { return 1; },
  };
}

test('research scheduler service exposes read-only queue and status', async () => {
  const service = new ResearchSchedulerReadService(repository());

  const queue = await service.queue(25, 2);
  const next = await service.next();
  const status = await service.status();

  assert.equal(queue.items[0].queueKey, queueItem.queueKey);
  assert.deepEqual({ limit: queue.limit, offset: queue.offset }, { limit: 25, offset: 2 });
  assert.equal(next.computedByApi, false);
  assert.equal(status.writeRoutesEnabled, false);
  assert.equal(status.openQueueCount, 1);
});

test('research scheduler service rejects invalid pagination', async () => {
  const service = new ResearchSchedulerReadService(repository());

  await assert.rejects(() => service.queue(0, 0), BadRequestException);
  await assert.rejects(() => service.queue(10, -1), BadRequestException);
});

test('postgres scheduler mapper parses json payloads and request status', () => {
  const mapped = mapSchedulerQueue({
    id: 7,
    queue_key: 'scheduler-key',
    queue_status: 'waiting_forward',
    action: 'wait_forward',
    priority_score: '0.1',
    target_hypothesis_key: 'hypothesis-1',
    target_family_key: 'family-1',
    target_experiment_key: null,
    request_key: null,
    request_status: null,
    context_fingerprint: 'fingerprint',
    reason_json: { reason_code: 'forward_evidence_insufficient' },
    budget_json: { daily_experiment_limit: 1 },
    policy_json: { priority_engine: 'deterministic-v1' },
    created_by: 'research:scheduler',
    created_at: new Date('2026-07-14T00:00:00Z'),
    updated_at: new Date('2026-07-14T00:00:00Z'),
    completed_at: null,
    metadata_json: { schema_version: 'autonomous-research-scheduler-v1' },
  });

  assert.equal(mapped.queueStatus, 'waiting_forward');
  assert.equal(mapped.reason.reason_code, 'forward_evidence_insufficient');
  assert.equal(mapped.targetHypothesisKey, 'hypothesis-1');
});
