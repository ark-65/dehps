import assert from 'node:assert/strict';
import { test } from 'node:test';
import { ForwardStateReadService } from '../src/forward-state/forward-state.service';
import { ForwardStateReadRepository } from '../src/forward-state/forward-state.types';

function repository(): ForwardStateReadRepository {
  return {
    async status() {
      return {
        latestIssue: '2026080',
        pendingEvent: null,
        consumedForwardCount: 1,
        latestTrainingResumeAttempt: null,
      };
    },
  };
}

test('forward state service exposes read-only aggregate status', async () => {
  const service = new ForwardStateReadService(repository());

  const status = await service.status();

  assert.equal(status.entity, 'forward_state');
  assert.equal(status.latestIssue, '2026080');
  assert.equal(status.consumedForwardCount, 1);
  assert.equal(status.writeRoutesEnabled, false);
  assert.equal(status.productionAccess, false);
});
