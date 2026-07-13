import { Module } from '@nestjs/common';
import { ResearchHypothesisController } from './research-hypothesis.controller';
import { PostgresHypothesisReadRepository } from './research-hypothesis.repository';
import { ResearchHypothesisReadService } from './research-hypothesis.service';

@Module({
  controllers: [ResearchHypothesisController],
  providers: [
    ResearchHypothesisReadService,
    { provide: 'HypothesisReadRepository', useClass: PostgresHypothesisReadRepository },
  ],
})
export class ResearchHypothesisModule {}
