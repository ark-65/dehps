import { BadRequestException, Inject, Injectable } from '@nestjs/common';
import { ResearchSchedulerReadRepository } from './research-scheduler.types';

@Injectable()
export class ResearchSchedulerReadService {
  constructor(
    @Inject('ResearchSchedulerReadRepository')
    private readonly repository: ResearchSchedulerReadRepository,
  ) {}

  async scheduler() {
    return this.status();
  }

  async queue(limit = 100, offset = 0) {
    this.pagination(limit, offset);
    return {
      entity: 'research_scheduler_queue',
      items: await this.repository.listQueue(limit, offset),
      limit,
      offset,
    };
  }

  async next() {
    return {
      entity: 'research_scheduler_next',
      data: await this.repository.latestQueueItem(),
      computedByApi: false,
      writeRoutesEnabled: false,
    };
  }

  async status() {
    return {
      entity: 'research_scheduler_status',
      openQueueCount: await this.repository.countOpenQueue(),
      schedulerRequestCount: await this.repository.countSchedulerRequests(),
      latestQueueItem: await this.repository.latestQueueItem(),
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
