import { BadRequestException, Inject, Injectable, NotFoundException } from '@nestjs/common';
import { ResearchExecutionReadRepository } from './research-execution.types';

@Injectable()
export class ResearchExecutionReadService {
  constructor(
    @Inject('ResearchExecutionReadRepository')
    private readonly repository: ResearchExecutionReadRepository,
  ) {}

  async runs(limit = 100, offset = 0) {
    this.pagination(limit, offset);
    return { entity: 'research_execution_run', items: await this.repository.listRuns(limit, offset), limit, offset };
  }

  async run(id: string) {
    const item = await this.repository.getRun(id.trim());
    if (!item) throw new NotFoundException(`research execution run not found: ${id}`);
    return { entity: 'research_execution_run', data: item };
  }

  async artifacts(id: string) {
    const item = await this.repository.getRun(id.trim());
    if (!item) throw new NotFoundException(`research execution run not found: ${id}`);
    return { entity: 'research_execution_artifact', runId: item.id, items: item.artifactPaths };
  }

  async results(id: string) {
    const item = await this.repository.getRun(id.trim());
    if (!item) throw new NotFoundException(`research execution run not found: ${id}`);
    return {
      entity: 'research_execution_result',
      runId: item.id,
      requestStatus: item.requestStatus,
      executionStatus: item.executionStatus,
      result: item.result,
      error: item.error,
    };
  }

  async status() {
    const latest = await this.repository.latestRun();
    const counts = await this.repository.countRuns();
    return {
      latestRunId: latest?.id ?? null,
      latestPlanKey: latest?.planKey ?? null,
      latestRequestStatus: latest?.requestStatus ?? null,
      latestExecutionStatus: latest?.executionStatus ?? null,
      totalRuns: counts.total,
      completedRuns: counts.completed,
      failedRuns: counts.failed,
      runningRuns: counts.running,
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
