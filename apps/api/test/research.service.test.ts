import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { CANONICAL_WEIGHT_KDJ_SIGNAL_RUN_ID, PostgresResearchRepository } from '../src/research.repository';
import { ResearchService } from '../src/research.service';
import { ResearchRepository } from '../src/research.types';

const repository: ResearchRepository = {
  async listExperiments(limit) {
    return [
      {
        experimentKey: `experiment-${limit}`,
        strategyKey: 'baseline_v1',
        hypothesis: 'Baseline smoke hypothesis',
        totalCombinations: 1107568,
        keptCombinations: 1073093,
        keepRate: 0.96887324,
        historyDraws: 1497,
        coveredDraws: 1450,
        coverageRate: 0.96860387,
        lift: 0.9997219,
        config: { min_score: 0.45 },
        summary: null,
        createdAt: '2026-06-15T00:00:00.000Z',
      },
    ];
  },
  async getExperimentDetail(experimentKey) {
    if (experimentKey !== 'experiment-1') {
      return null;
    }
    return {
      experimentKey,
      strategyKey: 'baseline_v1',
      hypothesis: 'Baseline smoke hypothesis',
      totalCombinations: 1107568,
      keptCombinations: 1073093,
      keepRate: 0.96887324,
      historyDraws: 1497,
      coveredDraws: 1450,
      coverageRate: 0.96860387,
      lift: 0.9997219,
      config: { min_score: 0.45 },
      summary: null,
      createdAt: '2026-06-15T00:00:00.000Z',
      reportMarkdown: '# Experiment Report\n\nEvidence.',
      reportCreatedAt: '2026-06-15T00:01:00.000Z',
    };
  },
  async listPipelineRuns(limit) {
    return [
      {
        runKey: `pipeline-${limit}`,
        status: 'success',
        startedAt: '2026-06-15T00:00:00.000Z',
        finishedAt: '2026-06-15T00:01:00.000Z',
        syncRunKey: 'sync-1',
        experimentKey: 'experiment-1',
        gitCommitSha: null,
        errorMessage: null,
      },
    ];
  },
  async listSyncRuns(limit) {
    return [
      {
        runKey: `sync-${limit}`,
        source: 'zhcw',
        status: 'success',
        startedAt: '2026-06-15T00:00:00.000Z',
        finishedAt: '2026-06-15T00:00:30.000Z',
        fetchedCount: 1,
        insertedCount: 1,
        updatedCount: 0,
        skippedCount: 0,
        conflictCount: 0,
        errorMessage: null,
      },
    ];
  },
  async listFeatureDistributions() {
    return [
      {
        featureKey: 'sum_value',
        label: 'Sum Value',
        totalCount: 100,
        bins: [
          { label: '<70', count: 20, rate: 0.2 },
          { label: '70-89', count: 80, rate: 0.8 },
        ],
      },
    ];
  },
  async listTrainingRounds(limit) {
    return [
      {
        runId: `run-${limit}`,
        roundIndex: 2,
        phase: 'micro',
        step: 0.01,
        trainMode: 'expanding',
        trainWindow: 900,
        evalWindow: 100,
        topN: 10000,
        asOfIssue: '2026067',
        improved: true,
        top100Hits: 0,
        top1000Hits: 1,
        top10000Hits: 3,
        red5Top100Hits: 2,
        red5Top1000Hits: 4,
        red5Top10000Hits: 8,
        medianRank: 12345.5,
        bestRank: 88,
        worstRank: 900000,
        objectiveScore: 29.5,
        createdAt: '2026-06-18T00:00:00.000Z',
      },
    ];
  },
  async getTrainingRoundDetail(runId, roundIndex) {
    if (!['run-1', 'run-100'].includes(runId) || roundIndex !== 2) {
      return null;
    }
    return {
      runId,
      roundIndex,
      phase: 'micro',
      step: 0.01,
      trainMode: 'expanding',
      trainWindow: 900,
      evalWindow: 100,
      topN: 10000,
      asOfIssue: '2026067',
      historyFingerprint: 'history-1',
      improved: true,
      top100Hits: 0,
      top1000Hits: 1,
      top10000Hits: 3,
      red5Top100Hits: 2,
      red5Top1000Hits: 4,
      red5Top10000Hits: 8,
      medianRank: 12345.5,
      bestRank: 88,
      worstRank: 900000,
      objectiveScore: 29.5,
      bestConfig: { frequency_weight: 0.4 },
      bestSummary: {
        config: { frequency_weight: 0.4 },
        as_of_issue: '2026067',
        history_fingerprint: 'history-1',
        config_hash: 'config-1',
        evaluated_draws: 100,
        top_100_hits: 0,
        top_1000_hits: 1,
        top_10000_hits: 3,
        median_rank: 12345.5,
        best_rank: 88,
        worst_rank: 900000,
        red5: { top_100_hits: 2, top_1000_hits: 4, top_10000_hits: 8 },
        run_key: 'result-1',
        frozen_validation: null,
      },
      topResults: [],
      targetResults: [
        {
          issue: '2026001',
          draw_date: '2026-01-01',
          red_numbers: [1, 2, 3, 4, 5, 6],
          rank: 88,
          score: 0.72,
          hit_top_100: true,
          hit_top_1000: true,
          hit_top_10000: true,
          red5_rank: 50,
          red5_score: 0.71,
          red5_numbers: [1, 2, 3, 4, 5, 7],
          red5_missing_number: 6,
          red5_extra_number: 7,
          hit_red5_top_100: true,
          hit_red5_top_1000: true,
          hit_red5_top_10000: true,
        },
      ],
      prefilter: {
        mode: 'sampled-targets',
        round: 2,
        target_stride: 4,
        target_count: 25,
        target_worker_count: 1,
        generated_config_count: 64,
        kept_config_count: 4,
        promote_limit: 2,
        diversity_quota: 2,
        diversity_added_count: 1,
        stagnation_rounds: 16,
        low_coverage_fields: ['sum_tail_weight'],
        candidate_budget: { exploitation: 26, exploration: 19, replay: 13, baseline: 6 },
        frozen_validation_window: 20,
        control_experiments: [{ label: 'structural_baseline', top_10000_hits: 1 }],
        weight_kdj_advisor: {
          enabled: true,
          signal_run_id: 'weight-kdj-run-1',
          latest_issue: '2026068',
          budget: 3,
          field_count: 2,
          fields: ['frequency_weight', 'omission_weight'],
          selected_count: 1,
          downweighted_count: 1,
          rejected_count: 1,
          candidate_count: 2,
          control_verdict: { passed: false, language: 'control baseline held' },
          advice: [
            {
              weight_name: 'frequency_weight',
              latest_issue: '2026068',
              offset: 0.02,
              applied_offset: 0.02,
              decision: 'selected',
              reason: 'positive_delta',
            },
          ],
          mode: 'advisor_only',
        },
        ridge_kdj_advisor: {
          enabled: true,
          status: 'ready',
          signal_run_id: 'ridge-kdj-run-1',
          latest_issue: '2026068',
          budget: 2,
          fields: ['sum_tail_weight'],
          selected_count: 1,
          rejected_count: 0,
          control_verdict: { passed: true, language: 'beats frozen controls' },
          advice: [
            {
              weight_name: 'sum_tail_weight',
              suggested_offset: -0.01,
              confidence: 0.7,
              validation_metric: 0.02,
              baseline_metric: 0.03,
              config_hash: 'ridge-hash-1',
              source: 'ml_kdj_offset_advisor_v0',
            },
          ],
          mode: 'advisor_only',
        },
        neural_kdj_advisor: {
          enabled: false,
          status: 'waiting',
          latest_issue: '2026068',
          budget: 0,
          fields: [],
          advice: [],
          control_verdict: 'not evaluated',
        },
        refined_config_count: 6,
        elapsed_seconds: 0.5,
        note: 'target prefilter before full 100-draw refine',
      },
      createdAt: '2026-06-18T00:00:00.000Z',
    };
  },
  async listTrainingWeightSignals(signalRunId, weights, limit) {
    return [
      {
        signalRunId: signalRunId ?? 'weight-kdj-run-1',
        weightName: weights[0] ?? `frequency_weight_${limit}`,
        source: 'weight_response_probe_v0',
        trainMode: 'expanding',
        trainWindow: 900,
        evalWindow: 1,
        topN: 10000,
        points: [
          {
            issue: '2026068',
            drawDate: '2026-06-16',
            baseValue: 0.3,
            closeValue: 0.33,
            issueLowValue: 0.24,
            issueHighValue: 0.36,
            rollingLowValue: 0.24,
            rollingHighValue: 0.36,
            rsv: 75,
            kValue: 58.333333,
            dValue: 52.777778,
            jValue: 69.444444,
            recommendedOffset: 0.011667,
            bestObjectiveScore: 10,
            objectiveDelta: 2,
            sampleCount: 5,
          },
        ],
      },
    ];
  },
  async getSsqHistorySummary() {
    return {
      tablePresent: true,
      totalDraws: 1497,
      minDrawDate: '2003-02-23',
      maxDrawDate: '2026-06-16',
      latestIssue: '2026067',
      latestDrawDate: '2026-06-16',
      latestCreatedAt: '2026-06-16T15:59:00.000Z',
    };
  },
  async getTrainingWeightSignalSummary() {
    return {
      tablePresent: true,
      totalRows: 3000,
      latestSignalRunId: 'weight-kdj-run-1',
      latestIssue: '2026068',
      latestDrawDate: '2026-06-16',
      latestCreatedAt: '2026-06-16T16:00:00.000Z',
      weights: ['frequency_weight', 'structural_weight'],
    };
  },
};

test('dashboard returns experiments, pipeline runs, and sync runs', async () => {
  const service = new ResearchService(repository);

  const dashboard = await service.dashboard(500);

  assert.equal(dashboard.experiments[0].experimentKey, 'experiment-100');
  assert.equal(dashboard.pipelineRuns[0].runKey, 'pipeline-100');
  assert.equal(dashboard.syncRuns[0].runKey, 'sync-100');
  assert.equal(dashboard.featureDistributions[0].featureKey, 'sum_value');
});

test('health reports read-only API mode', () => {
  const service = new ResearchService(repository);

  assert.deepEqual(service.health(), {
    status: 'ok',
    service: 'dehps-api',
    mode: 'read-only',
  });
});

test('experiment detail trims keys and includes report markdown', async () => {
  const service = new ResearchService(repository);

  const detail = await service.getExperimentDetail(' experiment-1 ');

  assert.equal(detail?.experimentKey, 'experiment-1');
  assert.equal(detail?.reportMarkdown, '# Experiment Report\n\nEvidence.');
});

test('feature distributions return structural sample bins', async () => {
  const service = new ResearchService(repository);

  const distributions = await service.listFeatureDistributions();

  assert.equal(distributions[0].totalCount, 100);
  assert.equal(distributions[0].bins[1].rate, 0.8);
});

test('training rounds list uses normalized limit', async () => {
  const service = new ResearchService(repository);

  const rounds = await service.listTrainingRounds(500);

  assert.equal(rounds[0].runId, 'run-100');
  assert.equal(rounds[0].red5Top10000Hits, 8);
});

test('training round detail normalizes target hit rows', async () => {
  const service = new ResearchService(repository);

  const detail = await service.getTrainingRoundDetail(' run-1 ', 2);

  assert.equal(detail?.runId, 'run-1');
  assert.equal(detail?.bestSummary?.top_10000_hits, 3);
  assert.equal(detail?.targetResults[0].redNumbers.join(','), '1,2,3,4,5,6');
  assert.equal(detail?.targetResults[0].red5MissingNumber, 6);
  assert.equal(await service.getTrainingRoundDetail('missing', 1), null);
});

test('training weight signals normalize run id, weights, and limit', async () => {
  const service = new ResearchService(repository);

  const series = await service.listTrainingWeightSignals(' weight-kdj-run-1 ', 'frequency_weight, bad value ', 5000);

  assert.equal(series[0].signalRunId, 'weight-kdj-run-1');
  assert.equal(series[0].weightName, 'frequency_weight');
  assert.equal(series[0].points[0].jValue, 69.444444);
});

test('postgres training weight signal mapping preserves date-only values', async () => {
  const repository = new PostgresResearchRepository();
  try {
    const point = (repository as any).trainingWeightSignalPoint({
      issue: '2026068',
      draw_date: new Date(2026, 5, 16),
      base_value: '0.300000',
      close_value: '0.330000',
      issue_low_value: '0.240000',
      issue_high_value: '0.360000',
      rolling_low_value: '0.240000',
      rolling_high_value: '0.360000',
      rsv: '75.000000',
      k_value: '58.333333',
      d_value: '52.777778',
      j_value: '69.444444',
      recommended_offset: '0.011667',
      best_objective_score: '10.000000',
      objective_delta: '2.000000',
      sample_count: '5',
    });

    assert.equal(point.drawDate, '2026-06-16');
  } finally {
    await repository.onModuleDestroy();
  }
});

test('postgres omitted training weight run id prefers canonical run before latest ad hoc', async () => {
  const repository = new PostgresResearchRepository();
  const originalPool = (repository as any).pool;
  const queries: Array<{ sql: string; params?: unknown[] }> = [];
  (repository as any).pool = {
    async query(sql: string, params?: unknown[]) {
      queries.push({ sql, params });
      if (sql.includes("to_regclass('public.training_weight_signals')")) {
        return { rows: [{ table_name: 'training_weight_signals' }] };
      }
      return { rows: [] };
    },
    async end() {
      return undefined;
    },
  };

  try {
    await repository.listTrainingWeightSignals(null, [], 100);
  } finally {
    await repository.onModuleDestroy();
    await originalPool.end();
  }

  assert.match(queries[1].sql, /WHERE signal_run_id = \$4/);
  assert.deepEqual(queries[1].params, [null, null, 100, CANONICAL_WEIGHT_KDJ_SIGNAL_RUN_ID]);
});

test('training status is derived from database rounds without status json', async () => {
  const previousRoot = process.env.DEHPS_ROOT;
  process.env.DEHPS_ROOT = mkdtempSync(path.join(os.tmpdir(), 'dehps-api-test-'));
  try {
    const service = new ResearchService(repository);

    const status = await service.trainingStatus();

    assert.equal(status.runId, 'run-100');
    assert.equal(status.statusFile, null);
    assert.equal(status.completedRounds, 2);
    assert.equal(status.best?.top_10000_hits, 3);
    assert.equal(status.prefilter?.latest?.diversityAddedCount, 1);
    assert.equal(status.prefilter?.latest?.lowCoverageFields[0], 'sum_tail_weight');
    assert.equal(status.prefilter?.latest?.frozenValidationWindow, 20);
    assert.equal(status.prefilter?.latest?.controlExperiments[0]?.label, 'structural_baseline');
    const weightAdvisor = status.advisorSummaries.find((advisor) => advisor.source === 'weight_kdj_advisor');
    const ridgeAdvisor = status.advisorSummaries.find((advisor) => advisor.source === 'ridge_kdj_advisor');
    const neuralAdvisor = status.advisorSummaries.find((advisor) => advisor.source === 'neural_kdj_advisor');
    assert.equal(weightAdvisor?.enabled, true);
    assert.equal(weightAdvisor?.latestSignalIssue, '2026068');
    assert.equal(weightAdvisor?.advice[0]?.weightName, 'frequency_weight');
    assert.equal(weightAdvisor?.advice[0]?.suggestedOffset, 0.02);
    assert.equal((weightAdvisor?.controlVerdict as Record<string, unknown>)?.['passed'], false);
    assert.equal(ridgeAdvisor?.advice[0]?.weightName, 'sum_tail_weight');
    assert.equal(ridgeAdvisor?.advice[0]?.confidence, 0.7);
    assert.equal(ridgeAdvisor?.advice[0]?.validationMetric, 0.02);
    assert.equal(ridgeAdvisor?.advice[0]?.baselineMetric, 0.03);
    assert.equal(ridgeAdvisor?.advice[0]?.configHash, 'ridge-hash-1');
    assert.equal(neuralAdvisor?.enabled, false);
    assert.equal(neuralAdvisor?.controlVerdict, 'not evaluated');
    assert.equal(status.recentRounds[0].round, 2);
  } finally {
    if (previousRoot === undefined) {
      delete process.env.DEHPS_ROOT;
    } else {
      process.env.DEHPS_ROOT = previousRoot;
    }
  }
});

test('service status returns the read-only service shape and heavy task limits', async () => {
  const previousRoot = process.env.DEHPS_ROOT;
  const root = mkdtempSync(path.join(os.tmpdir(), 'dehps-service-status-'));
  mkdirSync(path.join(root, 'runtime/logs'), { recursive: true });
  writeFileSync(path.join(root, 'runtime/logs/api-dashboard.log'), 'api ready\n');
  writeFileSync(path.join(root, 'runtime/logs/web-dashboard.log'), 'web ready\n');
  try {
    process.env.DEHPS_ROOT = root;
    const service = new ResearchService(repository);

    const status = await service.serviceStatus();

    assert.equal(typeof status.generatedAt, 'string');
    assert.equal(status.services.length, 6);
    assert.equal(status.services.map((item) => item.name).join(','), 'api,web,db,sync,kdj,training');
    assert.equal(status.heavyTaskLimits.defaultWorkers, 16);
    assert.equal(status.heavyTaskLimits.cpuCount > 0, true);
    assert.equal(status.services.find((item) => item.name === 'api')?.pid, process.pid);
    assert.equal(status.services.find((item) => item.name === 'db')?.metrics['latestIssue'], '2026067');
    assert.equal(status.services.find((item) => item.name === 'kdj')?.metrics['totalRows'], 3000);
  } finally {
    if (previousRoot === undefined) {
      delete process.env.DEHPS_ROOT;
    } else {
      process.env.DEHPS_ROOT = previousRoot;
    }
  }
});

test('service status ignores recovered web build errors', async () => {
  const previousRoot = process.env.DEHPS_ROOT;
  const root = mkdtempSync(path.join(os.tmpdir(), 'dehps-service-status-'));
  mkdirSync(path.join(root, 'runtime/logs'), { recursive: true });
  writeFileSync(path.join(root, 'runtime/logs/api-dashboard.log'), 'api ready\n');
  writeFileSync(
    path.join(root, 'runtime/logs/web-dashboard.log'),
    [
      'Application bundle generation failed.',
      "ERROR TS2339: Property 'status' does not exist",
      'Application bundle generation complete.',
      'Page reload sent to client(s).',
    ].join('\n'),
  );
  try {
    process.env.DEHPS_ROOT = root;
    const service = new ResearchService(repository);

    const status = await service.serviceStatus();
    const web = status.services.find((item) => item.name === 'web');

    assert.equal(web?.status, 'ok');
    assert.equal(web?.recentError, null);
  } finally {
    if (previousRoot === undefined) {
      delete process.env.DEHPS_ROOT;
    } else {
      process.env.DEHPS_ROOT = previousRoot;
    }
  }
});

test('service status flags stale pid, missing log, and recent sync errors without shelling out', async () => {
  const previousRoot = process.env.DEHPS_ROOT;
  const root = mkdtempSync(path.join(os.tmpdir(), 'dehps-service-status-'));
  mkdirSync(path.join(root, 'runtime/logs'), { recursive: true });
  writeFileSync(path.join(root, 'runtime/logs/api-dashboard.log'), 'api ready\n');
  writeFileSync(path.join(root, 'runtime/logs/web-dashboard.pid'), '999999999\n');
  writeFileSync(path.join(root, 'runtime/logs/ssq_draw_sync.log'), 'sync ERROR failed to fetch draw\n');
  try {
    process.env.DEHPS_ROOT = root;
    const service = new ResearchService(repository);

    const status = await service.serviceStatus();
    const web = status.services.find((item) => item.name === 'web');
    const sync = status.services.find((item) => item.name === 'sync');

    assert.equal(status.overall, 'failed');
    assert.equal(web?.processAlive, false);
    assert.equal(web?.status, 'failed');
    assert.match(web?.recentError ?? '', /web-dashboard\.log/);
    assert.equal(sync?.status, 'failed');
    assert.match(sync?.recentError ?? '', /failed to fetch draw/);
  } finally {
    if (previousRoot === undefined) {
      delete process.env.DEHPS_ROOT;
    } else {
      process.env.DEHPS_ROOT = previousRoot;
    }
  }
});

test('service status reports an empty but present KDJ signal table as warning', async () => {
  const previousRoot = process.env.DEHPS_ROOT;
  const root = mkdtempSync(path.join(os.tmpdir(), 'dehps-service-status-'));
  mkdirSync(path.join(root, 'runtime/logs'), { recursive: true });
  writeFileSync(path.join(root, 'runtime/logs/api-dashboard.log'), 'api ready\n');
  const emptyKdjRepository: ResearchRepository = {
    ...repository,
    async getTrainingWeightSignalSummary() {
      return {
        tablePresent: true,
        totalRows: 0,
        latestSignalRunId: null,
        latestIssue: null,
        latestDrawDate: null,
        latestCreatedAt: null,
        weights: [],
      };
    },
  };
  try {
    process.env.DEHPS_ROOT = root;
    const service = new ResearchService(emptyKdjRepository);

    const status = await service.serviceStatus();
    const kdj = status.services.find((item) => item.name === 'kdj');

    assert.equal(kdj?.status, 'warning');
    assert.equal(kdj?.metrics['tablePresent'], true);
    assert.match(kdj?.recentError ?? '', /暂无数据/);
  } finally {
    if (previousRoot === undefined) {
      delete process.env.DEHPS_ROOT;
    } else {
      process.env.DEHPS_ROOT = previousRoot;
    }
  }
});
