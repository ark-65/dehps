import { Module } from '@nestjs/common';
import { ResearchExecutionController } from './research-execution.controller';
import { PostgresResearchExecutionReadRepository } from './research-execution.repository';
import { ResearchExecutionReadService } from './research-execution.service';

@Module({
  controllers: [ResearchExecutionController],
  providers: [
    ResearchExecutionReadService,
    {
      provide: 'ResearchExecutionReadRepository',
      useClass: PostgresResearchExecutionReadRepository,
    },
  ],
})
export class ResearchExecutionModule {}
