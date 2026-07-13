import { Module } from '@nestjs/common';
import { ResearchController } from './research.controller';
import { PostgresResearchRepository } from './research.repository';
import { ResearchService } from './research.service';
import { TrainingStatusHub } from './training-status.hub';
import { ResearchHypothesisModule } from './research-hypotheses/research-hypothesis.module';

@Module({
  imports: [ResearchHypothesisModule],
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
