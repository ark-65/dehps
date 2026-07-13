import { BadRequestException, Inject, Injectable, NotFoundException } from '@nestjs/common';
import { ResearchAutonomyReadRepository } from './research-autonomy.types';

@Injectable()
export class ResearchAutonomyReadService {
  constructor(
    @Inject('ResearchAutonomyReadRepository')
    private readonly repository: ResearchAutonomyReadRepository,
  ) {}

  async context() {
    const latest = await this.repository.latestProposal();
    return {
      entity: 'research_context',
      contextFingerprint: latest?.contextFingerprint ?? null,
      sourceEvidenceIds: latest?.sourceEvidenceIds ?? [],
      sourceHypothesisKeys: latest?.sourceHypothesisKeys ?? [],
      sourceTrainingRunIds: latest?.sourceTrainingRunIds ?? [],
      submittedRequestKey: latest?.requestKey ?? null,
    };
  }

  async proposals(limit = 100, offset = 0) {
    this.pagination(limit, offset);
    return {
      entity: 'research_proposal',
      items: await this.repository.listProposals(limit, offset),
      limit,
      offset,
    };
  }

  async proposal(key: string) {
    const item = await this.repository.getProposal(key.trim());
    if (!item) throw new NotFoundException(`research proposal not found: ${key}`);
    return { entity: 'research_proposal', data: item };
  }

  async engineStatus() {
    const latest = await this.repository.latestProposal();
    return {
      engineVersion: latest?.engineVersion ?? null,
      contextFingerprint: latest?.contextFingerprint ?? null,
      selected: Boolean(latest),
      requestStatus: latest?.requestStatus ?? null,
      submittedRequestKey: latest?.requestKey ?? null,
      executionStarted: false,
      hypothesisCreated: false,
      writeRoutesEnabled: false,
    };
  }

  private pagination(limit: number, offset: number) {
    if (!Number.isSafeInteger(limit) || limit < 1 || limit > 500) {
      throw new BadRequestException('limit must be an integer between 1 and 500');
    }
    if (!Number.isSafeInteger(offset) || offset < 0) {
      throw new BadRequestException('offset must be a non-negative integer');
    }
  }
}
