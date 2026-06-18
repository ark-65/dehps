import assert from 'node:assert/strict';
import { mkdtempSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
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
    assert.equal(status.recentRounds[0].round, 2);
  } finally {
    if (previousRoot === undefined) {
      delete process.env.DEHPS_ROOT;
    } else {
      process.env.DEHPS_ROOT = previousRoot;
    }
  }
});
