import { BadRequestException, Inject, Injectable, NotFoundException } from '@nestjs/common';
import { EngineeringReadRepository } from './engineering.types';

@Injectable()
export class EngineeringReadService {
  constructor(
    @Inject('EngineeringReadRepository')
    private readonly repository: EngineeringReadRepository,
  ) {}

  async contracts(limit = 100, offset = 0) {
    this.pagination(limit, offset);
    return {
      entity: 'engineering_contract',
      items: await this.repository.listContracts(limit, offset),
      limit,
      offset,
    };
  }

  async plan() {
    const plan = await this.repository.latestPlan();
    if (!plan) throw new NotFoundException('engineering plan not found');
    return { entity: 'engineering_plan', data: plan, generatedByApi: false, writeRoutesEnabled: false };
  }

  async status() {
    return {
      entity: 'engineering_status',
      contractCount: await this.repository.countContracts(),
      planCount: await this.repository.countPlans(),
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
