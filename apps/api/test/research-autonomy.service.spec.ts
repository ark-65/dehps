import assert from 'node:assert/strict';
import { test } from 'node:test';
import { BadRequestException, NotFoundException } from '@nestjs/common';
import { mapProposal } from '../src/research-autonomy/research-autonomy.repository';
import { ResearchAutonomyReadService } from '../src/research-autonomy/research-autonomy.service';
import {
  ResearchAutonomyReadRepository,
  ResearchProposalRecord,
} from '../src/research-autonomy/research-autonomy.types';

const proposal: ResearchProposalRecord = {
  requestKey: 'research-proposal-1', requestStatus: 'submitted', requestedBy: 'agent:research',
  submittedAt: '2026-07-13T00:00:00.000Z', engineVersion: 'autonomous-hypothesis-proposal-v1',
  contextFingerprint: 'context-hash', proposal: { proposal_key: 'proposal-1' },
  noveltyReport: { accepted: true }, proposalScore: { total: 0.91 },
  validationReport: { valid: true }, sourceEvidenceIds: ['evidence-1'],
  sourceHypothesisKeys: ['hypothesis-1'], sourceTrainingRunIds: ['run-1'],
};

function repository(): ResearchAutonomyReadRepository {
  return {
    async listProposals() { return [proposal]; },
    async getProposal(key) { return ['research-proposal-1', 'proposal-1'].includes(key) ? proposal : null; },
    async latestProposal() { return proposal; },
  };
}

test('research autonomy service exposes context, proposals, and inert engine state', async () => {
  const service = new ResearchAutonomyReadService(repository());
  const context = await service.context();
  const list = await service.proposals(25, 3);
  const status = await service.engineStatus();

  assert.equal(context.contextFingerprint, 'context-hash');
  assert.deepEqual(context.sourceEvidenceIds, ['evidence-1']);
  assert.equal(list.items[0].proposal.proposal_key, 'proposal-1');
  assert.deepEqual({ limit: list.limit, offset: list.offset }, { limit: 25, offset: 3 });
  assert.equal(status.executionStarted, false);
  assert.equal(status.hypothesisCreated, false);
  assert.equal(status.writeRoutesEnabled, false);
});

test('research autonomy service rejects missing proposals and invalid pagination', async () => {
  const service = new ResearchAutonomyReadService(repository());
  await assert.rejects(() => service.proposal('missing'), NotFoundException);
  await assert.rejects(() => service.proposals(0, 0), BadRequestException);
  await assert.rejects(() => service.proposals(10, -1), BadRequestException);
});

test('postgres proposal mapping parses the complete submitted payload', () => {
  const mapped = mapProposal({
    request_key: 'research-proposal-1', status: 'submitted', requested_by: 'agent:research',
    submitted_at: '2026-07-13T00:00:00Z',
    payload_json: JSON.stringify({
      engine_version: 'autonomous-hypothesis-proposal-v1', context_fingerprint: 'context-hash',
      proposal: { proposal_key: 'proposal-1' }, novelty_report: { accepted: true },
      proposal_score: { total: 0.91 }, validation_report: { valid: true },
      source_evidence_ids: ['evidence-1'], source_hypothesis_keys: ['hypothesis-1'],
      source_training_run_ids: ['run-1'],
    }),
  });
  assert.equal(mapped.proposal.proposal_key, 'proposal-1');
  assert.equal(mapped.contextFingerprint, 'context-hash');
  assert.equal(mapped.validationReport.valid, true);
});
