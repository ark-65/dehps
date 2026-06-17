import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import {
  DashboardPayload,
  ExperimentDetail,
  compareExperiments,
  combinationDistribution,
  ExperimentSummary,
  latestStatus,
  percent,
  reportStatus,
  signedNumber,
  signedPercent,
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
    featureDistributions: [],
  };

  assert.equal(latestStatus(payload), '流水线正常');
});

test('latestStatus handles an empty pipeline list', () => {
  assert.equal(latestStatus({ experiments: [], pipelineRuns: [], syncRuns: [], featureDistributions: [] }), '暂无流水线记录');
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

test('reportStatus summarizes experiment report availability', () => {
  const detail: ExperimentDetail = {
    experimentKey: 'baseline',
    strategyKey: 'baseline_v1',
    hypothesis: 'Check a structural filter.',
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
    reportMarkdown: '# Report',
    reportCreatedAt: '2026-06-15T00:01:00.000Z',
  };

  assert.equal(reportStatus(null), '请选择实验');
  assert.equal(reportStatus(detail), '报告已生成');
  assert.equal(reportStatus({ ...detail, reportMarkdown: null }), '暂无报告');
});

test('compareExperiments reports signed metric deltas', () => {
  const primary: ExperimentSummary = {
    experimentKey: 'primary',
    strategyKey: 'baseline_v2',
    hypothesis: null,
    totalCombinations: 100,
    keptCombinations: 70,
    keepRate: 0.7,
    historyDraws: 10,
    coveredDraws: 9,
    coverageRate: 0.9,
    lift: 1.2857,
    config: {},
    summary: null,
    createdAt: '2026-06-16T00:00:00.000Z',
  };
  const comparison: ExperimentSummary = {
    ...primary,
    experimentKey: 'comparison',
    keptCombinations: 80,
    keepRate: 0.8,
    coveredDraws: 8,
    coverageRate: 0.8,
    lift: 1,
  };

  const result = compareExperiments(primary, comparison);

  assert.equal(signedPercent(result?.keepRateDelta ?? null), '-10.00%');
  assert.equal(signedPercent(result?.coverageRateDelta ?? null), '+10.00%');
  assert.equal(signedNumber(result?.liftDelta ?? null), '+0.2857');
  assert.equal(signedNumber(null), '无');
});

test('training view does not use periodic dashboard polling', () => {
  const component = readFileSync(new URL('../src/app/app.component.ts', import.meta.url), 'utf8');
  const template = readFileSync(new URL('../src/app/app.component.html', import.meta.url), 'utf8');
  const service = readFileSync(new URL('../src/app/dashboard.service.ts', import.meta.url), 'utf8');

  assert.equal(component.includes('timer(0, 30000)'), false);
  assert.equal(component.includes('dashboardService.load().pipe'), false);
  assert.equal(service.includes("window.location.port === '4200' ? '3000'"), false);
  assert.equal(service.includes('/training-status/ws'), true);
  assert.equal(component.includes('liveProgressOption'), true);
  assert.equal(template.includes('@if (hasRoundCharts(training))'), true);
  assert.equal(template.includes('等待第 1 轮回归结果'), true);
  assert.equal(template.includes('weightTrendGroups(training)'), true);
  assert.equal(template.includes('权重演化图待拆分'), false);
  assert.equal(component.includes("title: '权重演化 - 基础'"), true);
  assert.equal(component.includes("title: '权重演化 - 奖惩'"), true);
});
