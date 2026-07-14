import assert from 'node:assert/strict';
import { test } from 'node:test';
import { BadRequestException, NotFoundException } from '@nestjs/common';
import { mapPlan, mapRequest, mapStage } from '../src/research-planning/research-planning.repository';
import { ResearchPlanningReadService } from '../src/research-planning/research-planning.service';
import {
  ExperimentPlanRecord,
  ResearchPlanningReadRepository,
} from '../src/research-planning/research-planning.types';

const plan: ExperimentPlanRecord = {
  planKey: 'plan-1',
  planVersion: 'autonomous-experiment-planner-v1',
  proposalKey: 'proposal-1',
  hypothesisKey: 'hypothesis-1',
  familyKey: 'ranking_model_disagreement',
  mechanism: 'ranking_model_disagreement',
  planFingerprint: 'plan-hash',
  proposalFingerprint: 'proposal-hash',
  hypothesisStatus: 'preregistered',
  plan: { plan_key: 'plan-1' },
};

function repository(): ResearchPlanningReadRepository {
  return {
    async listPlans() { return [plan]; },
    async getPlan(key) { return ['plan-1', 'hypothesis-1'].includes(key) ? plan : null; },
    async listStages() {
      return [
        { experimentKey: 'ranking_disagreement_feasibility_v1', experimentType: 'feasibility', status: 'planned', artifactPaths: [], configSnapshot: {}, metadata: {} },
        { experimentKey: 'ranking_disagreement_historical_search_v1', experimentType: 'historical_search', status: 'planned', artifactPaths: [], configSnapshot: {}, metadata: {} },
      ];
    },
    async listRequests() {
      return [
        { requestKey: 'engineering-1', requestType: 'engineering_experiment_tool', status: 'submitted', requestedByRole: 'research', requestedBy: 'research:planner', title: '', summary: '', payload: {}, metadata: {}, submittedAt: '2026-07-13T00:00:00.000Z' },
        { requestKey: 'operator-1', requestType: 'operator_isolated_run', status: 'draft', requestedByRole: 'research', requestedBy: 'research:planner', title: '', summary: '', payload: {}, metadata: {}, submittedAt: null },
      ];
    },
    async latestPlan() { return plan; },
  };
}

test('research planning service exposes plans, stages, requests, and inert status', async () => {
  const service = new ResearchPlanningReadService(repository());

  const plans = await service.plans(25, 4);
  const stages = await service.stages('plan-1');
  const requests = await service.requests('plan-1');
  const status = await service.status();

  assert.equal(plans.items[0].planKey, 'plan-1');
  assert.deepEqual({ limit: plans.limit, offset: plans.offset }, { limit: 25, offset: 4 });
  assert.equal(stages.items.length, 2);
  assert.equal(requests.items[0].requestType, 'engineering_experiment_tool');
  assert.equal(status.hypothesisCreated, true);
  assert.equal(status.plannedExperimentCount, 2);
  assert.equal(status.engineeringRequestSubmitted, true);
  assert.equal(status.operatorRequestDraft, true);
  assert.equal(status.executionStarted, false);
  assert.equal(status.evidenceCreated, false);
  assert.equal(status.writeRoutesEnabled, false);
});

test('research planning service rejects missing plans and invalid pagination', async () => {
  const service = new ResearchPlanningReadService(repository());

  await assert.rejects(() => service.plan('missing'), NotFoundException);
  await assert.rejects(() => service.stages('missing'), NotFoundException);
  await assert.rejects(() => service.requests('missing'), NotFoundException);
  await assert.rejects(() => service.plans(0, 0), BadRequestException);
  await assert.rejects(() => service.plans(10, -1), BadRequestException);
});

test('postgres planning mappers parse plan, stage, and request rows', () => {
  const mappedPlan = mapPlan({
    hypothesis_key: 'hypothesis-1',
    hypothesis_status: 'preregistered',
    metadata_json: JSON.stringify({ experiment_plan: {
      plan_key: 'plan-1', plan_version: 'v1', proposal_key: 'proposal-1',
      family_key: 'family', mechanism: 'ranking_model_disagreement',
      plan_fingerprint: 'plan-hash', proposal_fingerprint: 'proposal-hash',
    } }),
  });
  const mappedStage = mapStage({
    experiment_key: 'exp-1', experiment_type: 'feasibility', status: 'planned',
    artifact_paths_json: ['a.json'], config_snapshot_json: { stage_key: 'feasibility' },
    metadata_json: { experiment_plan_key: 'plan-1' },
  });
  const mappedRequest = mapRequest({
    request_key: 'req-1', request_type: 'operator_isolated_run', status: 'draft',
    requested_by_role: 'research', requested_by: 'research:planner', title: 'title',
    summary: '', payload_json: { experiment_plan_key: 'plan-1' },
    metadata_json: {}, submitted_at: null,
  });

  assert.equal(mappedPlan.planKey, 'plan-1');
  assert.equal(mappedStage.artifactPaths[0], 'a.json');
  assert.equal(mappedRequest.submittedAt, null);
});
