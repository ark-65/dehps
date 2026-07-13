import assert from 'node:assert/strict';
import { test } from 'node:test';
import { AgentAuthorityController } from '../src/agent-authority/agent-authority.controller';
import { AgentAuthorityReadService } from '../src/agent-authority/agent-authority.service';

test('agent request controller routes detail decisions and executions to read service', () => {
  const calls: string[] = [];
  const service = {
    getRequest(key: string) { calls.push(`request:${key}`); return {}; },
    listDecisions(key: string) { calls.push(`decisions:${key}`); return {}; },
    listExecutions(key: string) { calls.push(`executions:${key}`); return {}; },
  } as AgentAuthorityReadService;
  const controller = new AgentAuthorityController(service);
  controller.request('request-1');
  controller.decisions('request-1');
  controller.executions('request-1');
  assert.deepEqual(calls, ['request:request-1', 'decisions:request-1', 'executions:request-1']);
});

test('agent request controller exposes no write route methods', () => {
  const controller = new AgentAuthorityController({} as AgentAuthorityReadService);
  const methods = Object.getOwnPropertyNames(Object.getPrototypeOf(controller));
  assert.deepEqual(
    methods.filter((name) => !['constructor', 'query', 'integer'].includes(name)).sort(),
    ['authority', 'decisions', 'executions', 'request', 'requests'].sort(),
  );
  for (const forbidden of ['approve', 'reject', 'create', 'update', 'delete']) {
    assert.ok(!methods.includes(forbidden));
  }
});
