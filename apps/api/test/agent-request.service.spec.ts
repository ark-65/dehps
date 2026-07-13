import assert from 'node:assert/strict';
import { test } from 'node:test';
import { BadRequestException, NotFoundException } from '@nestjs/common';
import { AgentAuthorityReadService } from '../src/agent-authority/agent-authority.service';
import { AgentRequestReadRepository, AgentRequestRecord } from '../src/agent-authority/agent-authority.types';
import { mapRequest } from '../src/agent-authority/agent-authority.repository';

const request: AgentRequestRecord = {
  id: 1, requestKey: 'request-1', requestType: 'engineering_implementation',
  requestedByRole: 'engineering', requestedBy: 'agent:eng', hypothesisId: null,
  experimentId: null, parentRequestId: null, title: 'Implement', summary: '',
  payload: { scope: 'api' }, status: 'approved', riskLevel: 'medium', requiresReview: true,
  createdAt: '2026-07-13T00:00:00.000Z', updatedAt: '2026-07-13T00:00:00.000Z',
  submittedAt: '2026-07-13T00:00:00.000Z', resolvedAt: null, metadata: {},
};

function repository(): AgentRequestReadRepository {
  return {
    async listRequests() { return [request]; },
    async getRequest(key) { return key === request.requestKey ? request : null; },
    async listDecisions() { return []; },
    async listExecutions() { return []; },
  };
}

test('agent request service validates and forwards all list filters', async () => {
  const repo = repository();
  const calls: unknown[] = [];
  repo.listRequests = async (query) => { calls.push(query); return [request]; };
  const result = await new AgentAuthorityReadService(repo).listRequests({
    status: 'approved', requestType: 'engineering_implementation', requestedByRole: 'engineering',
    riskLevel: 'medium', createdAfter: '2026-01-01T00:00:00Z', limit: 25, offset: 5,
  });
  assert.equal(result.entity, 'agent_request');
  assert.equal(result.items[0].requestKey, 'request-1');
  assert.ok((calls[0] as any).createdAfter instanceof Date);
  assert.equal((calls[0] as any).limit, 25);
});

test('agent request service returns 404 and rejects invalid filters', async () => {
  const service = new AgentAuthorityReadService(repository());
  await assert.rejects(() => service.getRequest('missing'), NotFoundException);
  await assert.rejects(() => service.listDecisions('missing'), NotFoundException);
  await assert.rejects(() => service.listRequests({ status: 'invented' }), BadRequestException);
  await assert.rejects(() => service.listRequests({ requestedByRole: 'admin' }), BadRequestException);
  await assert.rejects(() => service.listRequests({ limit: 0 }), BadRequestException);
});

test('postgres request mapping parses JSON without leaking raw values', () => {
  const mapped = mapRequest({
    id: '1', request_key: 'request-1', request_type: 'engineering_implementation',
    requested_by_role: 'engineering', requested_by: 'agent:eng', hypothesis_id: null,
    experiment_id: null, parent_request_id: null, title: 'Implement', summary: '',
    payload_json: '{"scope":"api"}', status: 'approved', risk_level: 'medium', requires_review: true,
    created_at: '2026-07-13T00:00:00Z', updated_at: '2026-07-13T00:00:00Z',
    submitted_at: '2026-07-13T00:00:00Z', resolved_at: null, metadata_json: '{"source":"cli"}',
  });
  assert.deepEqual(mapped.payload, { scope: 'api' });
  assert.deepEqual(mapped.metadata, { source: 'cli' });
});
