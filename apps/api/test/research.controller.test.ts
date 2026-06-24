import assert from 'node:assert/strict';
import { test } from 'node:test';
import { ResearchController } from '../src/research.controller';
import { ResearchService } from '../src/research.service';
import { TrainingStatusHub } from '../src/training-status.hub';

test('controller keeps blank numeric query params on service defaults', () => {
  const calls: Array<{ method: string; value: number | undefined }> = [];
  const service = {
    dashboard(limit?: number) {
      calls.push({ method: 'dashboard', value: limit });
      return {};
    },
    trainingStatus(lines?: number) {
      calls.push({ method: 'trainingStatus', value: lines });
      return {};
    },
    getTrainingNextCandidates(limit?: number) {
      calls.push({ method: 'getTrainingNextCandidates', value: limit });
      return {};
    },
    listTrainingWeightSignals(_runId?: string, _weights?: string, limit?: number) {
      calls.push({ method: 'listTrainingWeightSignals', value: limit });
      return [];
    },
  } as unknown as ResearchService;
  const controller = new ResearchController(service, new TrainingStatusHub());

  controller.dashboard('');
  controller.trainingStatus('   ');
  controller.trainingNextCandidates('0');
  controller.trainingWeightSignals(undefined, undefined, '\t');

  assert.deepEqual(calls, [
    { method: 'dashboard', value: undefined },
    { method: 'trainingStatus', value: undefined },
    { method: 'getTrainingNextCandidates', value: 0 },
    { method: 'listTrainingWeightSignals', value: undefined },
  ]);
});
