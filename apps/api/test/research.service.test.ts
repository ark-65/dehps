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
};

test('dashboard returns experiments, pipeline runs, and sync runs', async () => {
  const service = new ResearchService(repository);

  const dashboard = await service.dashboard(500);

  assert.equal(dashboard.experiments[0].experimentKey, 'experiment-100');
  assert.equal(dashboard.pipelineRuns[0].runKey, 'pipeline-100');
  assert.equal(dashboard.syncRuns[0].runKey, 'sync-100');
});

test('health reports read-only API mode', () => {
  const service = new ResearchService(repository);

  assert.deepEqual(service.health(), {
    status: 'ok',
    service: 'dehps-api',
    mode: 'read-only',
  });
});
