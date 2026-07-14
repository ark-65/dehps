import { BadRequestException, Inject, Injectable, NotFoundException } from '@nestjs/common';
import { ResearchDecisionReadRepository } from './research-decision.types';

@Injectable()
export class ResearchDecisionReadService {
  constructor(
    @Inject('ResearchDecisionReadRepository')
    private readonly repository: ResearchDecisionReadRepository,
  ) {}

  async decisions(limit = 100, offset = 0) {
    this.pagination(limit, offset);
    return { entity: 'research_decision', items: await this.repository.listDecisions(limit, offset), limit, offset };
  }

  async decision(key: string) {
    const item = await this.repository.getDecision(key.trim());
    if (!item) throw new NotFoundException(`research decision not found: ${key}`);
    return { entity: 'research_decision', data: item };
  }

  async status() {
    return {
      ...(await this.repository.reviewStatus()),
      writeRoutesEnabled: false,
      productionAccess: false,
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
