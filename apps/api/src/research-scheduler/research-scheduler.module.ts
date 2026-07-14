import { Module } from '@nestjs/common';
import { ResearchSchedulerController } from './research-scheduler.controller';
import { PostgresResearchSchedulerReadRepository } from './research-scheduler.repository';
import { ResearchSchedulerReadService } from './research-scheduler.service';

@Module({
  controllers: [ResearchSchedulerController],
  providers: [
    ResearchSchedulerReadService,
    {
      provide: 'ResearchSchedulerReadRepository',
      useClass: PostgresResearchSchedulerReadRepository,
    },
  ],
})
export class ResearchSchedulerModule {}
