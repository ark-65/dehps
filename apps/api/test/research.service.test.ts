import assert from 'node:assert/strict';
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
