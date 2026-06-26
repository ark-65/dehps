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

test('controller numeric params reject non-decimal integer forms', () => {
  const calls: Array<{ method: string; value: number | undefined }> = [];
  const roundCalls: Array<{ runId: string; roundIndex: number }> = [];
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
    getTrainingRoundDetail(runId: string, roundIndex: number) {
      roundCalls.push({ runId, roundIndex });
      return null;
    },
  } as unknown as ResearchService;
  const controller = new ResearchController(service, new TrainingStatusHub());

  controller.dashboard('1e2');
  controller.trainingStatus('0x50');
  controller.trainingNextCandidates('2.5');
  controller.trainingWeightSignals(undefined, undefined, '0010');
  controller.trainingRoundDetail('run-100', '002');
  controller.trainingRoundDetail('run-100', '2.9');

  assert.deepEqual(calls, [
    { method: 'dashboard', value: undefined },
    { method: 'trainingStatus', value: undefined },
    { method: 'getTrainingNextCandidates', value: undefined },
    { method: 'listTrainingWeightSignals', value: 10 },
  ]);
  assert.deepEqual(roundCalls[0], { runId: 'run-100', roundIndex: 2 });
  assert.deepEqual(roundCalls[1], { runId: 'run-100', roundIndex: 0 });
});

test('controller numeric params reject unsafe integers', () => {
  const calls: Array<{ method: string; value: number | undefined }> = [];
  const roundCalls: Array<{ runId: string; roundIndex: number }> = [];
  const service = {
    dashboard(limit?: number) {
      calls.push({ method: 'dashboard', value: limit });
      return {};
    },
    trainingStatus(lines?: number) {
      calls.push({ method: 'trainingStatus', value: lines });
      return {};
    },
    getTrainingRoundDetail(runId: string, roundIndex: number) {
      roundCalls.push({ runId, roundIndex });
      return null;
    },
  } as unknown as ResearchService;
  const controller = new ResearchController(service, new TrainingStatusHub());

  controller.dashboard('9007199254740992');
  controller.trainingStatus('-9007199254740992');
  controller.trainingRoundDetail('run-100', '9007199254740992');
  controller.trainingRoundDetail('run-100', '9007199254740991');

  assert.deepEqual(calls, [
    { method: 'dashboard', value: undefined },
    { method: 'trainingStatus', value: undefined },
  ]);
  assert.deepEqual(roundCalls, [
    { runId: 'run-100', roundIndex: 0 },
    { runId: 'run-100', roundIndex: 9007199254740991 },
  ]);
});
