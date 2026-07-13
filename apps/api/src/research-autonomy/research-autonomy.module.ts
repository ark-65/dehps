import { Module } from '@nestjs/common';
import { ResearchAutonomyController } from './research-autonomy.controller';
import { PostgresResearchAutonomyReadRepository } from './research-autonomy.repository';
import { ResearchAutonomyReadService } from './research-autonomy.service';

@Module({
  controllers: [ResearchAutonomyController],
  providers: [
    ResearchAutonomyReadService,
    {
      provide: 'ResearchAutonomyReadRepository',
      useClass: PostgresResearchAutonomyReadRepository,
    },
  ],
})
export class ResearchAutonomyModule {}
