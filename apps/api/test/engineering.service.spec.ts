import assert from 'node:assert/strict';
import { test } from 'node:test';
import { BadRequestException, NotFoundException } from '@nestjs/common';
import { mapEngineeringContract, mapEngineeringPlan } from '../src/engineering/engineering.repository';
import { EngineeringReadService } from '../src/engineering/engineering.service';
import { EngineeringContractRecord, EngineeringPlanRecord, EngineeringReadRepository } from '../src/engineering/engineering.types';

const contract: EngineeringContractRecord = {
  requestKey: 'engineering-experiment-tool-1',
  status: 'submitted',
  requestedBy: 'research:planner',
  title: 'Implement isolated tool',
  hypothesisKey: 'hypothesis-1',
  experimentKey: 'experiment-1',
  experimentPlanKey: 'plan-1',
  planFingerprint: 'fingerprint',
  mechanism: 'ranking_model_disagreement',
  productionImpact: 'none',
  payload: { production_impact: 'none' },
  metadata: { plan_fingerprint: 'fingerprint' },
  createdAt: '2026-07-14T00:00:00.000Z',
  submittedAt: '2026-07-14T00:00:00.000Z',
};

const plan: EngineeringPlanRecord = {
  planKey: 'plan-1',
  hypothesisKey: 'hypothesis-1',
  hypothesisStatus: 'preregistered',
  planFingerprint: 'fingerprint',
  mechanism: 'ranking_model_disagreement',
  plan: { plan_key: 'plan-1' },
  metadata: { plan_fingerprint: 'fingerprint' },
};

function repository(hasPlan = true): EngineeringReadRepository {
  return {
    async listContracts() { return [contract]; },
    async latestPlan() { return hasPlan ? plan : null; },
    async countContracts() { return 1; },
    async countPlans() { return hasPlan ? 1 : 0; },
  };
}

test('engineering service exposes read-only contracts plan and status', async () => {
  const service = new EngineeringReadService(repository());

  const contracts = await service.contracts(25, 3);
  const latestPlan = await service.plan();
  const status = await service.status();

  assert.equal(contracts.items[0].requestKey, contract.requestKey);
  assert.deepEqual({ limit: contracts.limit, offset: contracts.offset }, { limit: 25, offset: 3 });
  assert.equal(latestPlan.generatedByApi, false);
  assert.equal(status.writeRoutesEnabled, false);
});

test('engineering service rejects invalid pagination and missing plan', async () => {
  await assert.rejects(() => new EngineeringReadService(repository()).contracts(0, 0), BadRequestException);
  await assert.rejects(() => new EngineeringReadService(repository()).contracts(10, -1), BadRequestException);
  await assert.rejects(() => new EngineeringReadService(repository(false)).plan(), NotFoundException);
});

test('postgres engineering mappers normalize contract and plan payloads', () => {
  const mappedContract = mapEngineeringContract({
    request_key: 'eng-1',
    status: 'submitted',
    requested_by: 'research:planner',
    title: 'title',
    hypothesis_key: 'hypothesis-1',
    experiment_key: 'experiment-1',
    payload_json: { experiment_plan_key: 'plan-1', mechanism: 'ranking_model_disagreement', production_impact: 'none' },
    metadata_json: { plan_fingerprint: 'fingerprint' },
    created_at: new Date('2026-07-14T00:00:00Z'),
    submitted_at: new Date('2026-07-14T00:00:00Z'),
  });
  const mappedPlan = mapEngineeringPlan({
    hypothesis_key: 'hypothesis-1',
    hypothesis_status: 'preregistered',
    metadata_json: {
      plan_fingerprint: 'fingerprint',
      experiment_plan: { plan_key: 'plan-1', mechanism: 'ranking_model_disagreement' },
    },
  });

  assert.equal(mappedContract.experimentPlanKey, 'plan-1');
  assert.equal(mappedContract.productionImpact, 'none');
  assert.equal(mappedPlan.planKey, 'plan-1');
  assert.equal(mappedPlan.mechanism, 'ranking_model_disagreement');
});
