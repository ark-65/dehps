import { Module } from '@nestjs/common';
import { ResearchDecisionController } from './research-decision.controller';
import { PostgresResearchDecisionReadRepository } from './research-decision.repository';
import { ResearchDecisionReadService } from './research-decision.service';

@Module({
  controllers: [ResearchDecisionController],
  providers: [
    ResearchDecisionReadService,
    {
      provide: 'ResearchDecisionReadRepository',
      useClass: PostgresResearchDecisionReadRepository,
    },
  ],
})
export class ResearchDecisionModule {}
