import assert from 'node:assert/strict';
import { test } from 'node:test';
import { BadRequestException, NotFoundException } from '@nestjs/common';
import { mapRun } from '../src/research-execution/research-execution.repository';
import { ResearchExecutionReadService } from '../src/research-execution/research-execution.service';
import { ResearchExecutionReadRepository, ResearchExecutionRunRecord } from '../src/research-execution/research-execution.types';

const run: ResearchExecutionRunRecord = {
  id: 'run-1',
  requestKey: 'operator-1',
  requestStatus: 'completed',
  executionId: 7,
  executionStatus: 'completed',
  runId: 'run-1',
  planKey: 'plan-1',
  planFingerprint: 'hash',
  experimentKey: 'ranking_disagreement_feasibility_v1',
  environment: 'isolated',
  productionAccess: false,
  startedAt: '2026-07-14T00:00:00.000Z',
  completedAt: '2026-07-14T00:01:00.000Z',
  artifactPaths: ['manifest.json'],
  result: { status: 'completed' },
  error: {},
};

function repository(): ResearchExecutionReadRepository {
  return {
    async listRuns() { return [run]; },
    async getRun(id) { return ['run-1', 'operator-1'].includes(id) ? run : null; },
    async latestRun() { return run; },
    async countRuns() { return { total: 1, completed: 1, failed: 0, running: 0 }; },
  };
}

test('research execution service exposes runs, artifacts, results, and inert status', async () => {
  const service = new ResearchExecutionReadService(repository());

  const runs = await service.runs(25, 4);
  const artifacts = await service.artifacts('run-1');
  const results = await service.results('operator-1');
  const status = await service.status();

  assert.equal(runs.items[0].id, 'run-1');
  assert.deepEqual({ limit: runs.limit, offset: runs.offset }, { limit: 25, offset: 4 });
  assert.deepEqual(artifacts.items, ['manifest.json']);
  assert.equal(results.result.status, 'completed');
  assert.equal(status.writeRoutesEnabled, false);
  assert.equal(status.productionAccess, false);
});

test('research execution service rejects missing runs and invalid pagination', async () => {
  const service = new ResearchExecutionReadService(repository());

  await assert.rejects(() => service.run('missing'), NotFoundException);
  await assert.rejects(() => service.artifacts('missing'), NotFoundException);
  await assert.rejects(() => service.results('missing'), NotFoundException);
  await assert.rejects(() => service.runs(0, 0), BadRequestException);
  await assert.rejects(() => service.runs(10, -1), BadRequestException);
});

test('postgres execution mapper parses operator execution rows', () => {
  const mapped = mapRun({
    request_key: 'operator-1',
    request_status: 'completed',
    payload_json: {
      experiment_plan_key: 'plan-1',
      experiment_key: 'experiment-1',
      production_access: false,
      run_contract: { plan_fingerprint: 'hash' },
    },
    execution_id: 3,
    execution_status: 'completed',
    run_id: 'run-1',
    environment: 'isolated',
    started_at: new Date('2026-07-14T00:00:00Z'),
    completed_at: null,
    result_json: { status: 'completed' },
    artifact_paths_json: ['manifest.json'],
    error_json: {},
  });

  assert.equal(mapped.id, 'run-1');
  assert.equal(mapped.planKey, 'plan-1');
  assert.equal(mapped.productionAccess, false);
});
