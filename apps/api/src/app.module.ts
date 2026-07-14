import { Module } from '@nestjs/common';
import { ResearchController } from './research.controller';
import { PostgresResearchRepository } from './research.repository';
import { ResearchService } from './research.service';
import { TrainingStatusHub } from './training-status.hub';
import { ResearchHypothesisModule } from './research-hypotheses/research-hypothesis.module';
import { AgentAuthorityModule } from './agent-authority/agent-authority.module';
import { ResearchAutonomyModule } from './research-autonomy/research-autonomy.module';
import { ResearchPlanningModule } from './research-planning/research-planning.module';

@Module({
  imports: [ResearchHypothesisModule, AgentAuthorityModule, ResearchAutonomyModule, ResearchPlanningModule],
  controllers: [ResearchController],
  providers: [
    ResearchService,
    TrainingStatusHub,
    {
      provide: 'ResearchRepository',
      useClass: PostgresResearchRepository,
    },
  ],
})
export class AppModule {}
