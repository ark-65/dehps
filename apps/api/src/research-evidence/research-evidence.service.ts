import { BadRequestException, Inject, Injectable, NotFoundException } from '@nestjs/common';
import { ResearchEvidenceReadRepository } from './research-evidence.types';

@Injectable()
export class ResearchEvidenceReadService {
  constructor(
    @Inject('ResearchEvidenceReadRepository')
    private readonly repository: ResearchEvidenceReadRepository,
  ) {}

  async evidence(limit = 100, offset = 0) {
    this.pagination(limit, offset);
    return { entity: 'research_evidence', items: await this.repository.listEvidence(limit, offset), limit, offset };
  }

  async evidenceByKey(key: string) {
    const item = await this.repository.getEvidence(key.trim());
    if (!item) throw new NotFoundException(`research evidence not found: ${key}`);
    return { entity: 'research_evidence', data: item };
  }

  async status() {
    return {
      evidenceCount: await this.repository.countEvidence(),
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
