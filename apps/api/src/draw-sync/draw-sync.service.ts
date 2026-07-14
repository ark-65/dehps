import { BadRequestException, Inject, Injectable } from '@nestjs/common';
import { DrawSyncReadRepository } from './draw-sync.types';

@Injectable()
export class DrawSyncReadService {
  constructor(
    @Inject('DrawSyncReadRepository')
    private readonly repository: DrawSyncReadRepository,
  ) {}

  async status() {
    return {
      entity: 'draw_sync_status',
      ...(await this.repository.status()),
      writeRoutesEnabled: false,
      productionAccess: false,
    };
  }

  async runs(limit = 100, offset = 0) {
    this.pagination(limit, offset);
    return {
      entity: 'draw_sync_runs',
      items: await this.repository.listRuns(limit, offset),
      limit,
      offset,
      writeRoutesEnabled: false,
    };
  }

  async events(limit = 100, offset = 0) {
    this.pagination(limit, offset);
    return {
      entity: 'draw_issue_events',
      items: await this.repository.listEvents(limit, offset),
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
