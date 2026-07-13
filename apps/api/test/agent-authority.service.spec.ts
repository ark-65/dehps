import assert from 'node:assert/strict';
import { test } from 'node:test';
import { AgentAuthorityReadService } from '../src/agent-authority/agent-authority.service';
import { AgentRequestReadRepository } from '../src/agent-authority/agent-authority.types';

const repository = {} as AgentRequestReadRepository;

test('authority endpoint publishes explicit default-deny role matrix', () => {
  const authority = new AgentAuthorityReadService(repository).authority();

  assert.equal(authority.default, 'deny');
  assert.deepEqual(authority.roles, ['research', 'engineering', 'reviewer', 'operator']);
  assert.ok(authority.permissions.research.includes('create_hypothesis_proposal'));
  assert.ok(!authority.permissions.research.includes('modify_code'));
  assert.ok(authority.permissions.engineering.includes('modify_code'));
  assert.ok(!authority.permissions.engineering.includes('submit_hypothesis_decision'));
  assert.ok(!authority.permissions.reviewer.includes('run_isolated_experiment'));
  assert.ok(!authority.permissions.operator.includes('create_hypothesis_proposal'));
});

test('authority endpoint reserves promotion for the existing gate and exposes no credentials', () => {
  const authority = new AgentAuthorityReadService(repository).authority();
  assert.deepEqual(authority.productionStrategyPromotion, {
    agentAuthorized: false,
    authority: 'existing_promotion_gate',
  });
  const serialized = JSON.stringify(authority).toLowerCase();
  assert.ok(!serialized.includes('password'));
  assert.ok(!serialized.includes('secret'));
  assert.ok(!serialized.includes('token'));
});
