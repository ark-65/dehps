import assert from 'node:assert/strict';
import { ForbiddenException } from '@nestjs/common';
import { test } from 'node:test';
import { WebSocket } from 'ws';
import { ResearchController } from '../src/research.controller';
import { ResearchService } from '../src/research.service';
import { TrainingStatusHub } from '../src/training-status.hub';
import { TrainingStatusPayload } from '../src/research.types';

function payload(runId = 'run-1'): TrainingStatusPayload {
  return {
    status: 'running',
    active: true,
    processAlive: true,
    runId,
    startedAt: '2026-06-17T12:00:00',
    updatedAt: '2026-06-17T12:00:01',
    deadline: null,
    pid: 123,
    historyScope: 'current_regime_default',
    regimeYears: 10,
    regimeStartDate: '2016-06-17',
    trainMode: 'expanding',
    trainWindow: 900,
    evalWindow: 100,
    topN: 10000,
    workers: 16,
    memoryBudgetGb: 20,
    universeSize: 1107568,
    qianKun: {
      total_draws: 0,
      recent_window: 0,
      latest_issue: '',
      latest_numbers: [],
      latest_pattern: '',
      latest_label: '',
      latest_icon: '',
      latest_lines: [],
      qian_count: 0,
      kun_count: 0,
      patterns: [],
    },
    completedRounds: 0,
    rounds: [],
    latestRound: null,
    recentRounds: [],
    best: null,
    latestProgress: null,
    statusFile: null,
    reportFile: null,
    logFile: null,
    serviceUnit: null,
    logTail: [],
    syncSchedule: {
      timezone: 'Asia/Shanghai',
      cron: '45 21 * * 2,4,0',
      description: '每周二、周四、周日 21:45 自动同步当期开奖数据（以实际更新为准）',
    },
  };
}

test('training status hub caches and broadcasts snapshots', () => {
  const hub = new TrainingStatusHub();
  const sent: string[] = [];
  const socket = {
    readyState: WebSocket.OPEN,
    send(message: string) {
      sent.push(message);
    },
    on() {},
  } as unknown as WebSocket;

  hub.addClient(socket);
  hub.publishStatus(payload('run-broadcast'));

  assert.equal(hub.latestStatus()?.runId, 'run-broadcast');
  assert.equal(JSON.parse(sent[0]).type, 'training_status');
  assert.equal(JSON.parse(sent[0]).payload.runId, 'run-broadcast');
});

test('training status event rejects non-local requests', async () => {
  const controller = new ResearchController({ trainingStatusFromEvent: async () => payload() } as ResearchService, new TrainingStatusHub());

  await assert.rejects(
    () => controller.trainingStatusEvent({ ip: '203.0.113.10' }, {}),
    (error: unknown) => error instanceof ForbiddenException,
  );
});

test('training status event accepts local request and publishes normalized status', async () => {
  const hub = new TrainingStatusHub();
  const service = { trainingStatusFromEvent: async () => payload('run-local') } as ResearchService;
  const controller = new ResearchController(service, hub);

  const result = await controller.trainingStatusEvent({ ip: '127.0.0.1' }, {});

  assert.equal(result.status, 'accepted');
  assert.equal(result.runId, 'run-local');
  assert.equal(hub.latestStatus()?.runId, 'run-local');
});
