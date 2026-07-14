import { Module } from '@nestjs/common';
import { ResearchPlanningController } from './research-planning.controller';
import { PostgresResearchPlanningReadRepository } from './research-planning.repository';
import { ResearchPlanningReadService } from './research-planning.service';

@Module({
  controllers: [ResearchPlanningController],
  providers: [
    ResearchPlanningReadService,
    {
      provide: 'ResearchPlanningReadRepository',
      useClass: PostgresResearchPlanningReadRepository,
    },
  ],
})
export class ResearchPlanningModule {}
