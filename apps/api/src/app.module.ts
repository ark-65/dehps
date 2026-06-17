import { Module } from '@nestjs/common';
import { ResearchController } from './research.controller';
import { PostgresResearchRepository } from './research.repository';
import { ResearchService } from './research.service';
import { TrainingStatusHub } from './training-status.hub';

@Module({
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
