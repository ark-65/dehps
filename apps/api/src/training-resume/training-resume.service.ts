import { BadRequestException, Inject, Injectable } from '@nestjs/common';
import { TrainingResumeReadRepository } from './training-resume.types';

@Injectable()
export class TrainingResumeReadService {
  constructor(
    @Inject('TrainingResumeReadRepository')
    private readonly repository: TrainingResumeReadRepository,
  ) {}

  async status() {
    return {
      entity: 'training_resume_status',
      ...(await this.repository.status()),
      writeRoutesEnabled: false,
      productionAccess: false,
    };
  }

  async history(limit = 100, offset = 0) {
    this.pagination(limit, offset);
    return {
      entity: 'training_resume_attempts',
      items: await this.repository.history(limit, offset),
      limit,
      offset,
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
