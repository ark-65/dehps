import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import {
  DashboardPayload,
  ExperimentDetail,
  ServiceStatusPayload,
  compareExperiments,
  combinationDistribution,
  ExperimentSummary,
  latestStatus,
  percent,
  reportStatus,
  serviceStatusLabel,
  serviceStatusSeverity,
  signedNumber,
  signedPercent,
  sortedServiceStatuses,
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

test('service status labels and severity sorting keep failed states first', () => {
  const payload: ServiceStatusPayload = {
    generatedAt: '2026-06-18T12:00:00.000Z',
    overall: 'failed',
    heavyTaskLimits: {
      cpuCount: 32,
      defaultWorkers: 16,
      recommendedInteractiveMax: 8,
      activeTrainingWorkers: 16,
    },
    services: [
      {
        name: 'api',
        label: 'API',
        status: 'ok',
        pid: 1,
        processAlive: true,
        heartbeatAt: '2026-06-18T12:00:00.000Z',
        heartbeatAgeSeconds: 0,
        lastStartedAt: null,
        lastFinishedAt: null,
        recentError: null,
        logFile: null,
        metrics: {},
      },
      {
        name: 'sync',
        label: '开奖同步',
        status: 'failed',
        pid: null,
        processAlive: null,
        heartbeatAt: null,
        heartbeatAgeSeconds: null,
        lastStartedAt: null,
        lastFinishedAt: null,
        recentError: 'failed',
        logFile: null,
        metrics: {},
      },
      {
        name: 'kdj',
        label: '权重KDJ',
        status: 'warning',
        pid: null,
        processAlive: null,
        heartbeatAt: null,
        heartbeatAgeSeconds: null,
        lastStartedAt: null,
        lastFinishedAt: null,
        recentError: null,
        logFile: null,
        metrics: {},
      },
    ],
  };

  assert.equal(serviceStatusLabel('ok'), '正常');
  assert.equal(serviceStatusLabel('warning'), '警告');
  assert.equal(serviceStatusSeverity('failed') > serviceStatusSeverity('warning'), true);
  assert.deepEqual(
    sortedServiceStatuses(payload).map((service) => service.name),
    ['sync', 'kdj', 'api'],
  );
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
  assert.equal(service.includes('/training-rounds?limit=50'), true);
  assert.equal(service.includes('/training-weight-signals?limit=1000'), true);
  assert.equal(service.includes('/training-rounds/${encodeURIComponent(runId)}'), true);
  assert.equal(component.includes('liveProgressOption'), true);
  assert.equal(component.includes('trainingWeightSignalsState$'), true);
  assert.equal(component.includes('weightKdjGroups'), true);
  assert.equal(component.includes("type DashboardTab = 'training' | 'training-rounds' | 'experiments' | 'service-status'"), true);
  assert.equal(component.includes('targetHitRows'), true);
  assert.equal(template.includes('@if (hasRoundCharts(training))'), true);
  assert.equal(template.includes('训练轮次'), true);
  assert.equal(template.includes('服务状态'), true);
  assert.equal(template.includes('命中期次'), true);
  assert.equal(template.includes('红5候选'), true);
  assert.equal(template.includes('等待第 1 轮回归结果'), true);
  assert.equal(template.includes('weightTrendGroups(training)'), true);
  assert.equal(template.includes('weightKdjGroups(kdjSignals.series)'), true);
  assert.equal(template.includes('等待权重KDJ回填'), true);
  assert.equal(template.includes('权重演化图待拆分'), false);
  assert.equal(component.includes("title: '权重演化 - 基础'"), true);
  assert.equal(component.includes("title: '权重演化 - 奖惩'"), true);
});

test('service status tab loads lazily from the dedicated endpoint', () => {
  const component = readFileSync(new URL('../src/app/app.component.ts', import.meta.url), 'utf8');
  const template = readFileSync(new URL('../src/app/app.component.html', import.meta.url), 'utf8');
  const service = readFileSync(new URL('../src/app/dashboard.service.ts', import.meta.url), 'utf8');

  assert.equal(service.includes('loadServiceStatus(): Observable<ServiceStatusPayload>'), true);
  assert.equal(service.includes("'/service-status'"), true);
  assert.equal(component.includes("filter((tab) => tab === 'service-status')"), true);
  assert.equal(component.includes('serviceStatusRefreshRequests'), true);
  assert.equal(component.includes("this.activeTab === 'service-status'"), true);
  assert.equal(template.includes("activeTab === 'service-status'"), true);
  assert.equal(template.includes('serviceStatusState$ | async'), true);
  assert.equal(template.includes('activeTrainingWorkers'), true);
});

test('training round charts enable range zoom for long round sequences', () => {
  const component = readFileSync(new URL('../src/app/app.component.ts', import.meta.url), 'utf8');

  assert.equal(component.includes('const ROUND_ZOOM_DEFAULT_WINDOW = 120'), true);
  assert.equal(component.includes('const ROUND_ZOOM_THRESHOLD = ROUND_ZOOM_DEFAULT_WINDOW'), true);
  assert.equal(component.includes('rounds.length > ROUND_ZOOM_THRESHOLD'), true);
  assert.equal(component.includes('((roundCount - ROUND_ZOOM_DEFAULT_WINDOW) / roundCount) * 100'), true);
  assert.equal(component.includes("type: 'inside'"), true);
  assert.equal(component.includes("type: 'slider'"), true);
  assert.equal(component.includes('zoomOnMouseWheel: true'), true);
  assert.equal(component.includes('moveOnMouseWheel: true'), true);
  assert.equal(component.includes('roundCategoryXAxis(xAxis, rounds)'), true);
  assert.equal(component.includes('roundValueXAxis(rounds)'), true);
  assert.equal(component.includes('roundAxisTooltip(rounds)'), true);
  assert.equal(component.includes('期号 ${round.best.as_of_issue}'), true);
});

test('weight trend charts reuse the shared round range zoom helper', () => {
  const component = readFileSync(new URL('../src/app/app.component.ts', import.meta.url), 'utf8');
  const weightTrend = component.slice(
    component.indexOf('  private weightTrendOption'),
    component.indexOf('  candidateScatterOption'),
  );
  const groupedLine = component.slice(
    component.indexOf('  private groupedLineOption'),
    component.indexOf('  private baseLineOption'),
  );

  assert.equal(weightTrend.includes('this.groupedLineOption'), true);
  assert.equal(weightTrend.includes('rounds,'), true);
  assert.equal(groupedLine.includes('const dataZoom = this.roundRangeDataZoom(rounds)'), true);
  assert.equal(groupedLine.includes('...(dataZoom.length ? { dataZoom } : {})'), true);
});

test('weight kdj charts use issue-series zoom without round coupling', () => {
  const component = readFileSync(new URL('../src/app/app.component.ts', import.meta.url), 'utf8');
  const weightKdj = component.slice(
    component.indexOf('  private weightKdjOption'),
    component.indexOf('  private weightTrendOption'),
  );

  assert.equal(weightKdj.includes('KDJ'), true);
  assert.equal(weightKdj.includes('signalRangeDataZoom(pointCount)'), true);
  assert.equal(weightKdj.includes('signalTooltipText'), true);
  assert.equal(weightKdj.includes('roundRangeDataZoom'), false);
});

test('non-round charts keep the lightweight no-zoom option shape', () => {
  const component = readFileSync(new URL('../src/app/app.component.ts', import.meta.url), 'utf8');
  const liveProgress = component.slice(
    component.indexOf('  liveProgressOption'),
    component.indexOf('  hitTrendOption'),
  );
  const redFiveDifference = component.slice(
    component.indexOf('  redFiveDifferenceOption'),
    component.indexOf('  qianKunDistributionOption'),
  );
  const qianKunDistribution = component.slice(
    component.indexOf('  qianKunDistributionOption'),
    component.indexOf('  weightTrendGroups'),
  );

  assert.equal(liveProgress.includes('dataZoom'), false);
  assert.equal(redFiveDifference.includes('dataZoom'), false);
  assert.equal(qianKunDistribution.includes('dataZoom'), false);
});
