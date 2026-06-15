import { Inject, Injectable } from '@nestjs/common';
import {
  DashboardPayload,
  ExperimentSummary,
  PipelineRunSummary,
  ResearchRepository,
  SyncRunSummary,
} from './research.types';

const DEFAULT_LIMIT = 20;

@Injectable()
export class ResearchService {
  constructor(@Inject('ResearchRepository') private readonly repository: ResearchRepository) {}

  health() {
    return {
      status: 'ok',
      service: 'dehps-api',
      mode: 'read-only',
    };
  }

  listExperiments(limit = DEFAULT_LIMIT): Promise<ExperimentSummary[]> {
    return this.repository.listExperiments(this.normalizeLimit(limit));
  }

  listPipelineRuns(limit = DEFAULT_LIMIT): Promise<PipelineRunSummary[]> {
    return this.repository.listPipelineRuns(this.normalizeLimit(limit));
  }

  listSyncRuns(limit = DEFAULT_LIMIT): Promise<SyncRunSummary[]> {
    return this.repository.listSyncRuns(this.normalizeLimit(limit));
  }

  async dashboard(limit = DEFAULT_LIMIT): Promise<DashboardPayload> {
    const normalizedLimit = this.normalizeLimit(limit);
    const [experiments, pipelineRuns, syncRuns] = await Promise.all([
      this.repository.listExperiments(normalizedLimit),
      this.repository.listPipelineRuns(normalizedLimit),
      this.repository.listSyncRuns(normalizedLimit),
    ]);
    return { experiments, pipelineRuns, syncRuns };
  }

  private normalizeLimit(limit: number): number {
    if (!Number.isFinite(limit)) {
      return DEFAULT_LIMIT;
    }
    return Math.min(Math.max(Math.trunc(limit), 1), 100);
  }
}
