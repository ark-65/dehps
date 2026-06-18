import { Body, Controller, ForbiddenException, Get, Inject, Param, Post, Query, Req } from '@nestjs/common';
import { ResearchService } from './research.service';
import { TrainingStatusHub } from './training-status.hub';

type LocalRequest = {
  ip?: string;
  socket?: { remoteAddress?: string };
  connection?: { remoteAddress?: string };
};

@Controller()
export class ResearchController {
  constructor(
    @Inject(ResearchService) private readonly researchService: ResearchService,
    @Inject(TrainingStatusHub)
    private readonly trainingStatusHub: TrainingStatusHub,
  ) {}

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

  @Get('training-rounds')
  trainingRounds(@Query('limit') limit?: string) {
    return this.researchService.listTrainingRounds(Number(limit));
  }

  @Get('training-rounds/:runId/:roundIndex')
  trainingRoundDetail(@Param('runId') runId: string, @Param('roundIndex') roundIndex: string) {
    return this.researchService.getTrainingRoundDetail(runId, Number(roundIndex));
  }

  @Get('training-weight-signals')
  trainingWeightSignals(
    @Query('runId') runId?: string,
    @Query('weights') weights?: string,
    @Query('limit') limit?: string,
  ) {
    return this.researchService.listTrainingWeightSignals(runId, weights, Number(limit));
  }

  @Post('training-events/status')
  async trainingStatusEvent(@Req() request: LocalRequest, @Body() _body: unknown) {
    if (!this.isLocalRequest(request)) {
      throw new ForbiddenException('training events only accept local requests');
    }
    const payload = await this.researchService.trainingStatus();
    this.trainingStatusHub.publishStatus(payload);
    return {
      status: 'accepted',
      runId: payload.runId,
      emittedAt: new Date().toISOString(),
    };
  }

  private isLocalRequest(request: LocalRequest): boolean {
    const address = request.ip ?? request.socket?.remoteAddress ?? request.connection?.remoteAddress ?? '';
    return ['127.0.0.1', '::1', '::ffff:127.0.0.1', 'localhost'].includes(address);
  }
}
