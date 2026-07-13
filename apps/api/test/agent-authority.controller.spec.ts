import assert from 'node:assert/strict';
import { test } from 'node:test';
import { BadRequestException } from '@nestjs/common';
import { AgentAuthorityController } from '../src/agent-authority/agent-authority.controller';
import { AgentAuthorityReadService } from '../src/agent-authority/agent-authority.service';

test('agent authority controller maps snake-case request filters', () => {
  const calls: unknown[] = [];
  const service = { listRequests(query: unknown) { calls.push(query); return {}; } } as AgentAuthorityReadService;
  const controller = new AgentAuthorityController(service);

  controller.requests({
    status: 'approved', request_type: 'engineering_implementation',
    requested_by_role: 'engineering', risk_level: 'medium',
    created_after: '2026-01-01', created_before: '2026-07-13', limit: '20', offset: '4',
  });

  assert.deepEqual(calls[0], {
    status: 'approved', requestType: 'engineering_implementation',
    requestedByRole: 'engineering', riskLevel: 'medium',
    createdAfter: '2026-01-01', createdBefore: '2026-07-13', limit: 20, offset: 4,
  });
});

test('agent authority controller rejects unsafe pagination', () => {
  const controller = new AgentAuthorityController({ listRequests() { return {}; } } as any);
  assert.throws(() => controller.requests({ limit: '1e2' }), BadRequestException);
  assert.throws(() => controller.requests({ offset: '9007199254740992' }), BadRequestException);
});
