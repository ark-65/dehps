import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  DashboardPayload,
  combinationDistribution,
  ExperimentSummary,
  latestStatus,
  percent,
} from '../src/app/dashboard.model';

test('percent formats ratios as dashboard percentages', () => {
  assert.equal(percent(0.96887324), '96.89%');
});

test('latestStatus summarizes pipeline state', () => {
  const payload: DashboardPayload = {
    experiments: [],
    pipelineRuns: [
      {
        runKey: 'daily-1',
        status: 'success',
        startedAt: '2026-06-15T00:00:00.000Z',
        finishedAt: null,
        syncRunKey: null,
        experimentKey: null,
        gitCommitSha: null,
        errorMessage: null,
      },
    ],
    syncRuns: [],
  };

  assert.equal(latestStatus(payload), 'Pipeline healthy');
});

test('latestStatus handles an empty pipeline list', () => {
  assert.equal(latestStatus({ experiments: [], pipelineRuns: [], syncRuns: [] }), 'No pipeline runs');
});

test('combinationDistribution splits retained and rejected space', () => {
  const experiment: ExperimentSummary = {
    experimentKey: 'baseline',
    strategyKey: 'baseline_v1',
    totalCombinations: 100,
    keptCombinations: 75,
    keepRate: 0.75,
    historyDraws: 10,
    coveredDraws: 8,
    coverageRate: 0.8,
    lift: 1.0667,
    config: {},
    summary: null,
    createdAt: '2026-06-15T00:00:00.000Z',
  };

  assert.deepEqual(combinationDistribution(experiment), {
    retainedCount: 75,
    rejectedCount: 25,
    retainedRate: 0.75,
    rejectedRate: 0.25,
  });
});
