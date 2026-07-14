import { BadRequestException, Inject, Injectable, NotFoundException } from '@nestjs/common';
import { PatternDiscoveryReadRepository } from './pattern-discovery.types';

@Injectable()
export class PatternDiscoveryReadService {
  constructor(
    @Inject('PatternDiscoveryReadRepository')
    private readonly repository: PatternDiscoveryReadRepository,
  ) {}

  async patterns(limit = 100, offset = 0) {
    this.pagination(limit, offset);
    return {
      entity: 'discovered_patterns',
      items: await this.repository.listPatterns(limit, offset),
      limit,
      offset,
      writeRoutesEnabled: false,
    };
  }

  async pattern(key: string) {
    const item = await this.repository.getPattern(key);
    if (!item) throw new NotFoundException('pattern not found');
    return { entity: 'discovered_pattern', data: item, writeRoutesEnabled: false };
  }

  async families() {
    return {
      entity: 'pattern_families',
      items: await this.repository.listFamilies(),
      writeRoutesEnabled: false,
    };
  }

  async features(limit = 100, offset = 0) {
    this.pagination(limit, offset);
    return {
      entity: 'synthesized_features',
      items: await this.repository.listFeatures(limit, offset),
      limit,
      offset,
      writeRoutesEnabled: false,
    };
  }

  async strategies(limit = 100, offset = 0) {
    this.pagination(limit, offset);
    return {
      entity: 'synthesized_strategies',
      items: await this.repository.listStrategies(limit, offset),
      limit,
      offset,
      writeRoutesEnabled: false,
    };
  }

  async cycles(limit = 100, offset = 0) {
    this.pagination(limit, offset);
    return {
      entity: 'pattern_search_cycles',
      items: await this.repository.listCycles(limit, offset),
      limit,
      offset,
      writeRoutesEnabled: false,
    };
  }

  async status() {
    return {
      entity: 'pattern_discovery_status',
      ...(await this.repository.status()),
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
