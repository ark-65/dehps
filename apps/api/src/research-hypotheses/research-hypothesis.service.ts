import { BadRequestException, Inject, Injectable, NotFoundException } from '@nestjs/common';
import { HypothesisReadRepository, RegistryQuery } from './research-hypothesis.types';

const FAMILY_STATUSES = new Set(['active', 'partially_rejected', 'rejected', 'exhausted', 'reopened']);
const HYPOTHESIS_STATUSES = new Set([
  'proposed', 'preregistered', 'running', 'accepted_for_followup', 'rejected', 'inconclusive', 'invalidated',
]);
const EXPERIMENT_STATUSES = new Set(['planned', 'running', 'completed', 'failed', 'invalidated', 'cancelled']);

export type RawRegistryQuery = {
  status?: string;
  familyKey?: string;
  createdAfter?: string;
  createdBefore?: string;
  limit?: number;
  offset?: number;
};

@Injectable()
export class ResearchHypothesisReadService {
  constructor(
    @Inject('HypothesisReadRepository') private readonly repository: HypothesisReadRepository,
  ) {}

  async listFamilies(raw: RawRegistryQuery) {
    const query = this.query(raw, FAMILY_STATUSES);
    return { entity: 'hypothesis_family', items: await this.repository.listFamilies(query), limit: query.limit, offset: query.offset };
  }

  async getFamily(familyKey: string) {
    const item = await this.repository.getFamily(familyKey.trim());
    if (!item) throw new NotFoundException(`hypothesis family not found: ${familyKey}`);
    return { entity: 'hypothesis_family', data: item };
  }

  async listHypotheses(raw: RawRegistryQuery) {
    const query = this.query(raw, HYPOTHESIS_STATUSES);
    return { entity: 'hypothesis', items: await this.repository.listHypotheses(query), limit: query.limit, offset: query.offset };
  }

  async getHypothesis(hypothesisKey: string) {
    const item = await this.repository.getHypothesis(hypothesisKey.trim());
    if (!item) throw new NotFoundException(`hypothesis not found: ${hypothesisKey}`);
    return { entity: 'hypothesis', data: item };
  }

  async listExperiments(hypothesisKey: string, raw: RawRegistryQuery) {
    await this.requireHypothesis(hypothesisKey);
    const query = this.query(raw, EXPERIMENT_STATUSES);
    return { entity: 'hypothesis_experiment', items: await this.repository.listExperiments(hypothesisKey.trim(), query), limit: query.limit, offset: query.offset };
  }

  async listEvidence(hypothesisKey: string, raw: RawRegistryQuery) {
    await this.requireHypothesis(hypothesisKey);
    const query = this.query({ ...raw, status: undefined });
    return { entity: 'hypothesis_evidence', items: await this.repository.listEvidence(hypothesisKey.trim(), query), limit: query.limit, offset: query.offset };
  }

  async listDecisions(hypothesisKey: string, raw: RawRegistryQuery) {
    await this.requireHypothesis(hypothesisKey);
    const query = this.query({ ...raw, status: undefined });
    return { entity: 'hypothesis_decision', items: await this.repository.listDecisions(hypothesisKey.trim(), query), limit: query.limit, offset: query.offset };
  }

  private async requireHypothesis(key: string) {
    if (!(await this.repository.getHypothesis(key.trim()))) {
      throw new NotFoundException(`hypothesis not found: ${key}`);
    }
  }

  private query(raw: RawRegistryQuery, allowedStatuses?: Set<string>): RegistryQuery {
    const status = raw.status?.trim() || undefined;
    if (status && allowedStatuses && !allowedStatuses.has(status)) {
      throw new BadRequestException(`invalid registry status: ${status}`);
    }
    const createdAfter = this.date(raw.createdAfter, 'created_after');
    const createdBefore = this.date(raw.createdBefore, 'created_before');
    if (createdAfter && createdBefore && createdAfter > createdBefore) {
      throw new BadRequestException('created_after must not be later than created_before');
    }
    const limit = raw.limit ?? 100;
    const offset = raw.offset ?? 0;
    if (!Number.isSafeInteger(limit) || limit < 1 || limit > 500) {
      throw new BadRequestException('limit must be an integer between 1 and 500');
    }
    if (!Number.isSafeInteger(offset) || offset < 0) {
      throw new BadRequestException('offset must be a non-negative integer');
    }
    return { status, familyKey: raw.familyKey?.trim() || undefined, createdAfter, createdBefore, limit, offset };
  }

  private date(value: string | undefined, label: string): Date | undefined {
    if (!value?.trim()) return undefined;
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) throw new BadRequestException(`${label} must be an ISO date-time`);
    return parsed;
  }
}
