import { Controller, Get, Inject, Param, Query } from '@nestjs/common';
import { ResearchService } from './research.service';

@Controller()
export class ResearchController {
  constructor(@Inject(ResearchService) private readonly researchService: ResearchService) {}

  @Get('health')
  health() {
    return this.researchService.health();
  }

  @Get('dashboard')
  dashboard(@Query('limit') limit?: string) {
    return this.researchService.dashboard(Number(limit));
  }

  @Get('experiments')
  experiments(@Query('limit') limit?: string) {
    return this.researchService.listExperiments(Number(limit));
  }

  @Get('experiments/:experimentKey')
  experimentDetail(@Param('experimentKey') experimentKey: string) {
    return this.researchService.getExperimentDetail(experimentKey);
  }

  @Get('pipeline-runs')
  pipelineRuns(@Query('limit') limit?: string) {
    return this.researchService.listPipelineRuns(Number(limit));
  }

  @Get('sync-runs')
  syncRuns(@Query('limit') limit?: string) {
    return this.researchService.listSyncRuns(Number(limit));
  }

  @Get('feature-distributions')
  featureDistributions() {
    return this.researchService.listFeatureDistributions();
  }

  @Get('training-status')
  trainingStatus(@Query('lines') lines?: string) {
    return this.researchService.trainingStatus(Number(lines));
  }
}
