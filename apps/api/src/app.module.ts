import { Module } from '@nestjs/common';
import { ResearchController } from './research.controller';
import { PostgresResearchRepository } from './research.repository';
import { ResearchService } from './research.service';
import { TrainingStatusHub } from './training-status.hub';
import { ResearchHypothesisModule } from './research-hypotheses/research-hypothesis.module';
import { AgentAuthorityModule } from './agent-authority/agent-authority.module';
import { ResearchAutonomyModule } from './research-autonomy/research-autonomy.module';
import { ResearchPlanningModule } from './research-planning/research-planning.module';
import { ResearchExecutionModule } from './research-execution/research-execution.module';
import { ResearchEvidenceModule } from './research-evidence/research-evidence.module';
import { ResearchDecisionModule } from './research-decision/research-decision.module';
import { ResearchSchedulerModule } from './research-scheduler/research-scheduler.module';

@Module({
  imports: [
    ResearchHypothesisModule,
    AgentAuthorityModule,
    ResearchAutonomyModule,
    ResearchPlanningModule,
    ResearchExecutionModule,
    ResearchEvidenceModule,
    ResearchDecisionModule,
    ResearchSchedulerModule,
  ],
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
