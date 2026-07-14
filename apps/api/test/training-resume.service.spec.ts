import assert from 'node:assert/strict';
import { test } from 'node:test';
import { BadRequestException } from '@nestjs/common';
import { mapTrainingResumeAttempt } from '../src/training-resume/training-resume.repository';
import { TrainingResumeReadService } from '../src/training-resume/training-resume.service';
import {
  TrainingResumeAttemptRecord,
  TrainingResumeReadRepository,
} from '../src/training-resume/training-resume.types';

const attempt: TrainingResumeAttemptRecord = {
  id: 1,
  attemptKey: 'attempt-1',
  eventKey: 'event-1',
  decision: 'launched',
  reasonCode: 'launched',
  oldRunId: 'old-run',
  newRunId: 'new-run',
  startedAt: '2026-07-14T00:00:00.000Z',
  completedAt: '2026-07-14T00:00:01.000Z',
  result: { launched: true },
};

function repository(): TrainingResumeReadRepository {
  return {
    async history() { return [attempt]; },
    async status() { return { latestAttempt: attempt, retryableEventCount: 0 }; },
  };
}

test('training resume service exposes read-only status and history', async () => {
  const service = new TrainingResumeReadService(repository());

  const status = await service.status();
  const history = await service.history(25, 2);

  assert.equal(status.writeRoutesEnabled, false);
  assert.equal(status.latestAttempt?.attemptKey, 'attempt-1');
  assert.equal(history.items[0].newRunId, 'new-run');
  assert.deepEqual({ limit: history.limit, offset: history.offset }, { limit: 25, offset: 2 });
});

test('training resume service rejects invalid pagination', async () => {
  const service = new TrainingResumeReadService(repository());

  await assert.rejects(() => service.history(0, 0), BadRequestException);
  await assert.rejects(() => service.history(10, -1), BadRequestException);
});

test('training resume mapper normalizes result payload', () => {
  const mapped = mapTrainingResumeAttempt({
    id: '7',
    attempt_key: 'attempt',
    event_key: null,
    decision: 'wait',
    reason_code: 'no_pending_event',
    old_run_id: null,
    new_run_id: null,
    started_at: new Date('2026-07-14T00:00:00Z'),
    completed_at: null,
    result_json: '{"reason":"none"}',
  });

  assert.equal(mapped.id, 7);
  assert.equal(mapped.result.reason, 'none');
});
