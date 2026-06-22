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
        bestRankQuality: {
          top_50000_hits: 4,
          top_100000_hits: 7,
          top_250000_hits: 23,
          top_500000_hits: 41,
          p90_rank: 918821,
          p95_rank: 983672,
          tail_over_750000_count: 33,
          tail_over_900000_count: 13,
          tail_over_1000000_count: 4,
          worst_rank_reward: 0.013159,
          median_rank_reward: 0.951943,
          band_reward: 0.735,
          tail_risk_penalty: 33.644567,
          reward: 1.700102,
        },
        prefilter: {
          mode: 'sampled-targets',
          phase_stage: 'early_broad',
          search_base_min_distance: 0.08,
          search_base: {
            source: 'search_challenger',
            selected_config_distance: 1.21,
            median_rank: 415503.5,
            worst_rank: 1089391,
            rank_quality: {
              tail_over_750000_count: 30,
              tail_over_900000_count: 15,
              tail_over_1000000_count: 8,
            },
            reward: { objectiveScore: 14.147182 },
          },
        },
        rankMovement: {
          comparedToRound: 1,
          comparedTargetCount: 100,
          changedTargetCount: 31,
          medianChangedAbsDelta: 1,
          maxAbsDelta: 2,
          sameRankVector: false,
        },
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
        rank_quality: {
          top_50000_hits: 4,
          top_100000_hits: 7,
          top_250000_hits: 23,
          top_500000_hits: 41,
          p90_rank: 918821,
          p95_rank: 983672,
          tail_over_750000_count: 33,
          tail_over_900000_count: 13,
          tail_over_1000000_count: 4,
          worst_rank_reward: 0.013159,
          median_rank_reward: 0.951943,
          band_reward: 0.735,
          tail_risk_penalty: 33.644567,
          reward: 1.700102,
        },
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
        phase_stage: 'early_broad',
        search_base_min_distance: 0.08,
        search_base: {
          source: 'search_challenger',
          changed: true,
          previous_config_hash: 'best-config',
          config_hash: 'search-config',
          candidate_config_hash: 'search-config',
          min_config_distance: 0.08,
          selected_config_distance: 1.21,
          search_challenger_config_distance: 1.21,
          search_challenger_rank_vector_changed: true,
          recent_search_base_hashes: ['best-config'],
          top_100_hits: 0,
          top_1000_hits: 0,
          top_10000_hits: 3,
          median_rank: 415503.5,
          best_rank: 1474,
          worst_rank: 1089391,
          rank_quality: {
            top_50000_hits: 11,
            top_100000_hits: 17,
            top_250000_hits: 26,
            top_500000_hits: 59,
            p90_rank: 962110,
            p95_rank: 1021464,
            tail_over_750000_count: 30,
            tail_over_900000_count: 15,
            tail_over_1000000_count: 8,
            worst_rank_reward: 0.043731,
            median_rank_reward: 1.248302,
            band_reward: 1.335,
            tail_risk_penalty: 39.057646,
            reward: 2.627033,
          },
          reward: {
            hitReward: 30,
            red5Reward: 21.2,
            rankQualityReward: 2.627033,
            rankPenalty: 0.622205,
            tailRiskPenalty: 39.057646,
            objectiveScore: 14.147182,
          },
          config: { frequency_weight: 0 },
        },
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
        target_weight_inversion_advisor: {
          enabled: true,
          status: 'ready',
          latest_issue: '2026068',
          fields: ['frequency_weight'],
          selected_count: 1,
          control_verdict: { passed: true, language: 'inversion held on target window' },
          advice: [
            {
              weight_name: 'frequency_weight',
              suggested_offset: -0.03,
              confidence: 0.6,
              decision: 'selected',
              reason: 'target_weight_inversion',
            },
          ],
          mode: 'advisor_only',
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
  async listSsqHistoryDraws() {
    return [
      { issue: '2026066', drawDate: '2026-06-12', redNumbers: [1, 3, 5, 7, 9, 11] },
      { issue: '2026067', drawDate: '2026-06-14', redNumbers: [2, 4, 6, 8, 10, 12] },
      { issue: '2026068', drawDate: '2026-06-16', redNumbers: [3, 5, 16, 18, 29, 32] },
    ];
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
  async getTrainingNextCandidates(limit) {
    return {
      status: 'ready',
      snapshotKey: 'training-next-2026068-config',
      runId: 'run-100',
      sourceRoundIndex: 2,
      asOfIssue: '2026068',
      nextIssue: '2026069',
      nextDrawDate: '2026-06-18',
      trainMode: 'expanding',
      trainWindow: 900,
      evalWindow: 100,
      topN: 10000,
      historyFingerprint: 'history-current',
      configHash: 'config-1',
      config: { frequency_weight: 0.4 },
      generatedAt: '2026-06-18T09:00:00.000Z',
      totalCount: 10000,
      candidates: [
        { rank: 1, redNumbers: [1, 2, 3, 4, 5, 6], score: 0.9 },
        { rank: Math.min(limit, 10000), redNumbers: [7, 8, 9, 10, 11, 12], score: 0.8 },
      ],
      guardrail: '历史响应面候选清单，不代表预测能力或概率优势。',
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
  assert.equal(rounds[0].bestRankQuality?.tail_over_750000_count, 33);
  assert.equal(rounds[0].prefilter?.searchBase?.source, 'search_challenger');
  assert.equal(rounds[0].prefilter?.searchBase?.rank_quality.tail_over_900000_count, 15);
  assert.equal(rounds[0].rankMovement?.changedTargetCount, 31);
  assert.equal(rounds[0].rankMovement?.maxAbsDelta, 2);
});

test('training round detail normalizes target hit rows', async () => {
  const service = new ResearchService(repository);

  const detail = await service.getTrainingRoundDetail(' run-1 ', 2);

  assert.equal(detail?.runId, 'run-1');
  assert.equal(detail?.bestSummary?.top_10000_hits, 3);
  assert.equal(detail?.prefilter?.phaseStage, 'early_broad');
  assert.equal(detail?.prefilter?.searchBaseMinDistance, 0.08);
  assert.equal(detail?.prefilter?.searchBase?.source, 'search_challenger');
  assert.equal(detail?.prefilter?.searchBase?.selectedConfigDistance, 1.21);
  assert.equal(detail?.prefilter?.searchBase?.rank_quality.tail_over_1000000_count, 8);
  assert.equal(detail?.prefilter?.searchBase?.reward?.objectiveScore, 14.147182);
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

test('training next candidates allow a top 10000 current snapshot', async () => {
  const service = new ResearchService(repository);

  const payload = await service.getTrainingNextCandidates(50000);

  assert.equal(payload.status, 'ready');
  assert.equal(payload.nextIssue, '2026069');
  assert.equal(payload.totalCount, 10000);
  assert.equal(payload.candidates[1].rank, 10000);
});

test('training status parses progress log lines with worker suffix', async () => {
  const previousRoot = process.env.DEHPS_ROOT;
  const root = mkdtempSync(path.join(os.tmpdir(), 'dehps-progress-test-'));
  mkdirSync(path.join(root, 'runtime/logs'), { recursive: true });
  writeFileSync(
    path.join(root, 'runtime/logs/training-supervisor-run-100.log'),
    '[supervisor] 2026-06-18T17:09:30 round=39 target=40/100 issue=2026004 train_draws=1433 elapsed=16.7s target_workers=10\n',
  );
  try {
    process.env.DEHPS_ROOT = root;
    const service = new ResearchService(repository);

    const status = await service.trainingStatus();

    assert.equal(status.latestProgress?.round, 39);
    assert.equal(status.latestProgress?.targetIndex, 40);
    assert.equal(status.active, true);
    assert.equal(status.status, 'running');
  } finally {
    if (previousRoot === undefined) {
      delete process.env.DEHPS_ROOT;
    } else {
      process.env.DEHPS_ROOT = previousRoot;
    }
  }
});

test('training status keeps db-backed run active between completed rounds', async () => {
  const previousRoot = process.env.DEHPS_ROOT;
  const root = mkdtempSync(path.join(os.tmpdir(), 'dehps-live-status-test-'));
  mkdirSync(path.join(root, 'data/output/optimization'), { recursive: true });
  writeFileSync(
    path.join(root, 'data/output/optimization/training-supervisor-run-100.json'),
    JSON.stringify({
      run_id: 'run-100',
      status: 'running',
      pid: process.pid,
      updated_at: '2026-06-18T17:09:30',
      workers: 10,
      latest_progress: {
        logged_at: '2026-06-18T17:09:30',
        round: 2,
        target_index: 100,
        target_total: 100,
        issue: '2026068',
        train_draws: 1497,
        elapsed_seconds: 40.4,
      },
    }),
  );
  try {
    process.env.DEHPS_ROOT = root;
    const service = new ResearchService(repository);

    const status = await service.trainingStatus();

    assert.equal(status.status, 'running');
    assert.equal(status.active, true);
    assert.equal(status.processAlive, true);
    assert.equal(status.workers, 10);
    assert.equal(status.latestProgress?.targetIndex, 100);
  } finally {
    if (previousRoot === undefined) {
      delete process.env.DEHPS_ROOT;
    } else {
      process.env.DEHPS_ROOT = previousRoot;
    }
  }
});

test('training status prefers a live status json before the new run has db rounds', async () => {
  const previousRoot = process.env.DEHPS_ROOT;
  const root = mkdtempSync(path.join(os.tmpdir(), 'dehps-live-status-switch-test-'));
  mkdirSync(path.join(root, 'data/output/optimization'), { recursive: true });
  writeFileSync(
    path.join(root, 'data/output/optimization/training-supervisor-run-101.json'),
    JSON.stringify({
      run_id: 'run-101',
      status: 'running',
      pid: process.pid,
      updated_at: '2026-06-18T23:17:19',
      workers: 10,
      train_window: 900,
      eval_window: 100,
      top_n: 10000,
      prefilter: {
        latest: {
          round: 1,
          candidate_budget: { target_weight_inversion: 0, ridge_kdj: 3 },
        },
      },
      latest_progress: {
        logged_at: '2026-06-18T23:17:19',
        round: 1,
        target_index: 100,
        target_total: 100,
        issue: '2026068',
        train_draws: 1497,
        elapsed_seconds: 38.1,
      },
    }),
  );
  try {
    process.env.DEHPS_ROOT = root;
    const service = new ResearchService(repository);

    const status = await service.trainingStatus();

    assert.equal(status.runId, 'run-101');
    assert.equal(status.status, 'running');
    assert.equal(status.active, true);
    assert.equal(status.processAlive, true);
    assert.equal(status.completedRounds, 0);
    assert.equal(status.latestProgress?.round, 1);
    assert.equal(status.latestProgress?.targetIndex, 100);
    assert.equal(status.prefilter?.latest?.candidateBudget?.ridge_kdj, 3);
  } finally {
    if (previousRoot === undefined) {
      delete process.env.DEHPS_ROOT;
    } else {
      process.env.DEHPS_ROOT = previousRoot;
    }
  }
});

test('training status event payload preserves live progress over db snapshot', async () => {
  const service = new ResearchService(repository);

  const status = await service.trainingStatusFromEvent({
    run_id: 'run-100',
    status: 'running',
    pid: process.pid,
    updated_at: '2026-06-18T17:09:30',
    latest_progress: {
      logged_at: '2026-06-18T17:09:30',
      round: 39,
      target_index: 40,
      target_total: 100,
      issue: '2026004',
      train_draws: 1433,
      elapsed_seconds: 16.7,
    },
  });

  assert.equal(status.status, 'running');
  assert.equal(status.active, true);
  assert.equal(status.pid, process.pid);
  assert.equal(status.processAlive, true);
  assert.equal(status.latestProgress?.issue, '2026004');
});

test('training status event process observation can mark a running payload inactive', async () => {
  const service = new ResearchService(repository);

  const status = await service.trainingStatusFromEvent({
    run_id: 'run-100',
    status: 'running',
    process_alive: false,
    latest_progress: {
      logged_at: '2026-06-18T17:09:30',
      round: 39,
      target_index: 40,
      target_total: 100,
      issue: '2026004',
      train_draws: 1433,
      elapsed_seconds: 16.7,
    },
  });

  assert.equal(status.status, 'running');
  assert.equal(status.active, false);
  assert.equal(status.processAlive, false);
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

test('postgres history draw mapping preserves sorted qian-kun inputs', async () => {
  const repository = new PostgresResearchRepository();
  const originalPool = (repository as any).pool;
  (repository as any).pool = {
    async query(sql: string) {
      if (sql.includes("to_regclass('public.ssq_history')")) {
        return { rows: [{ table_name: 'ssq_history' }] };
      }
      if (sql.includes('FROM ssq_history')) {
        return {
          rows: [
            {
              issue: '2026068',
              draw_date: new Date(2026, 5, 16),
              red_numbers: ['3', '5', '16', '18', '29', '32'],
            },
          ],
        };
      }
      return { rows: [] };
    },
    async end() {
      return undefined;
    },
  };

  try {
    const draws = await repository.listSsqHistoryDraws();

    assert.equal(draws[0].issue, '2026068');
    assert.equal(draws[0].drawDate, '2026-06-16');
    assert.deepEqual(draws[0].redNumbers, [3, 5, 16, 18, 29, 32]);
  } finally {
    await repository.onModuleDestroy();
    await originalPool.end();
  }
});

test('postgres training next candidates mapping reads the current snapshot', async () => {
  const repository = new PostgresResearchRepository();
  const originalPool = (repository as any).pool;
  const queries: Array<{ sql: string; params?: unknown[] }> = [];
  (repository as any).pool = {
    async query(sql: string, params?: unknown[]) {
      queries.push({ sql, params });
      if (sql.includes("to_regclass('public.training_next_candidates_current')")) {
        return { rows: [{ table_name: 'training_next_candidates_current' }] };
      }
      if (sql.includes('count(*)::int AS total_count')) {
        return { rows: [{ total_count: 10000 }] };
      }
      if (sql.includes('FROM training_next_candidates_current')) {
        return {
          rows: [
            {
              snapshot_key: 'training-next-1',
              run_id: 'run-1',
              source_round_index: 7,
              as_of_issue: '2026068',
              next_issue: '2026069',
              next_draw_date: new Date(2026, 5, 18),
              train_mode: 'expanding',
              train_window: 900,
              eval_window: 100,
              top_n: 10000,
              history_fingerprint: 'history-current',
              config_hash: 'config-1',
              config: { frequency_weight: '0.4' },
              rank: 1,
              red_numbers: ['1', '2', '3', '4', '5', '6'],
              score: '0.90000000',
              generated_at: new Date('2026-06-18T09:00:00.000Z'),
            },
          ],
        };
      }
      return { rows: [] };
    },
    async end() {
      return undefined;
    },
  };

  try {
    const payload = await repository.getTrainingNextCandidates(10000);

    assert.equal(payload.status, 'ready');
    assert.equal(payload.totalCount, 10000);
    assert.equal(payload.nextDrawDate, '2026-06-18');
    assert.deepEqual(payload.candidates[0].redNumbers, [1, 2, 3, 4, 5, 6]);
    assert.deepEqual(queries.at(-1)?.params, [10000]);
  } finally {
    await repository.onModuleDestroy();
    await originalPool.end();
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
    const inversionAdvisor = status.advisorSummaries.find((advisor) => advisor.source === 'target_weight_inversion_advisor');
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
    assert.equal(inversionAdvisor?.enabled, true);
    assert.equal(inversionAdvisor?.advice[0]?.weightName, 'frequency_weight');
    assert.equal(inversionAdvisor?.advice[0]?.suggestedOffset, -0.03);
    assert.equal((inversionAdvisor?.controlVerdict as Record<string, unknown>)?.['passed'], true);
    assert.equal(status.qianKun.latest_issue, '2026068');
    assert.equal(status.qianKun.latest_pattern, '110010');
    assert.equal(status.qianKun.latest_label, '节卦');
    assert.equal(status.qianKun.total_draws, 3);
    assert.equal(status.qianKun.recent_window, 3);
    assert.equal(status.qianKun.qian_count, 1);
    assert.equal(status.qianKun.kun_count, 1);
    assert.equal(status.recentRounds[0].round, 2);
    assert.equal(status.recentRounds[0].best?.rank_quality.tail_over_750000_count, 33);
    assert.equal(status.recentRounds[0].rankMovement?.changedTargetCount, 31);
    assert.equal(status.recentRounds[0].rankMovement?.medianChangedAbsDelta, 1);
    assert.equal(status.recentRounds[0].prefilter?.searchBase?.source, 'search_challenger');
    assert.equal(status.recentRounds[0].prefilter?.searchBase?.rank_quality.tail_over_1000000_count, 8);
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

test('service status keeps completed summaries with errors as failed', async () => {
  const previousRoot = process.env.DEHPS_ROOT;
  const root = mkdtempSync(path.join(os.tmpdir(), 'dehps-service-status-'));
  mkdirSync(path.join(root, 'runtime/logs'), { recursive: true });
  writeFileSync(path.join(root, 'runtime/logs/api-dashboard.log'), 'api ready\n');
  writeFileSync(
    path.join(root, 'runtime/logs/web-dashboard.log'),
    [
      'Application bundle generation failed.',
      "ERROR TS2339: Property 'status' does not exist",
      'Build completed with errors=1.',
    ].join('\n'),
  );
  try {
    process.env.DEHPS_ROOT = root;
    const service = new ResearchService(repository);

    const status = await service.serviceStatus();
    const web = status.services.find((item) => item.name === 'web');

    assert.equal(web?.status, 'failed');
    assert.match(web?.recentError ?? '', /completed with errors=1/);
  } finally {
    if (previousRoot === undefined) {
      delete process.env.DEHPS_ROOT;
    } else {
      process.env.DEHPS_ROOT = previousRoot;
    }
  }
});

test('service status ignores transient web proxy errors while web is alive', async () => {
  const previousRoot = process.env.DEHPS_ROOT;
  const root = mkdtempSync(path.join(os.tmpdir(), 'dehps-service-status-'));
  mkdirSync(path.join(root, 'runtime/logs'), { recursive: true });
  writeFileSync(path.join(root, 'runtime/logs/api-dashboard.log'), 'api ready\n');
  writeFileSync(path.join(root, 'runtime/logs/web-dashboard.pid'), `${process.pid}\n`);
  writeFileSync(
    path.join(root, 'runtime/logs/web-dashboard.log'),
    [
      'Watch mode enabled. Watching for file changes.',
      '11:20:25 PM [vite] ws proxy error:',
      'Error: connect ECONNREFUSED 127.0.0.1:3000',
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
