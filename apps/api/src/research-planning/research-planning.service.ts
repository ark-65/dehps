import { BadRequestException, Inject, Injectable, NotFoundException } from '@nestjs/common';
import { ResearchPlanningReadRepository } from './research-planning.types';

@Injectable()
export class ResearchPlanningReadService {
  constructor(
    @Inject('ResearchPlanningReadRepository')
    private readonly repository: ResearchPlanningReadRepository,
  ) {}

  async plans(limit = 100, offset = 0) {
    this.pagination(limit, offset);
    return {
      entity: 'experiment_plan',
      items: await this.repository.listPlans(limit, offset),
      limit,
      offset,
    };
  }

  async plan(key: string) {
    const item = await this.repository.getPlan(key.trim());
    if (!item) throw new NotFoundException(`experiment plan not found: ${key}`);
    return { entity: 'experiment_plan', data: item };
  }

  async stages(key: string) {
    const item = await this.repository.getPlan(key.trim());
    if (!item) throw new NotFoundException(`experiment plan not found: ${key}`);
    return {
      entity: 'experiment_plan_stage',
      planKey: item.planKey,
      items: await this.repository.listStages(item.planKey),
    };
  }

  async requests(key: string) {
    const item = await this.repository.getPlan(key.trim());
    if (!item) throw new NotFoundException(`experiment plan not found: ${key}`);
    return {
      entity: 'experiment_plan_request',
      planKey: item.planKey,
      items: await this.repository.listRequests(item.planKey),
    };
  }

  async status() {
    const latest = await this.repository.latestPlan();
    const requests = latest ? await this.repository.listRequests(latest.planKey) : [];
    return {
      latestPlanKey: latest?.planKey ?? null,
      latestPlanFingerprint: latest?.planFingerprint ?? null,
      hypothesisCreated: Boolean(latest),
      hypothesisStatus: latest?.hypothesisStatus ?? null,
      plannedExperimentCount: latest
        ? (await this.repository.listStages(latest.planKey)).filter((item) => item.status === 'planned').length
        : 0,
      engineeringRequestSubmitted: requests.some(
        (item) => item.requestType === 'engineering_experiment_tool' && item.status === 'submitted',
      ),
      operatorRequestDraft: requests.some(
        (item) => item.requestType === 'operator_isolated_run' && item.status === 'draft',
      ),
      executionStarted: false,
      evidenceCreated: false,
      productionAccess: false,
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
