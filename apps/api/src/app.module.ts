import { Module } from '@nestjs/common';
import { ResearchController } from './research.controller';
import { PostgresResearchRepository } from './research.repository';
import { ResearchService } from './research.service';

@Module({
  controllers: [ResearchController],
  providers: [
    ResearchService,
    {
      provide: 'ResearchRepository',
      useClass: PostgresResearchRepository,
    },
  ],
})
export class AppModule {}
