import { Module } from '@nestjs/common';
import { ResearchEvidenceController } from './research-evidence.controller';
import { PostgresResearchEvidenceReadRepository } from './research-evidence.repository';
import { ResearchEvidenceReadService } from './research-evidence.service';

@Module({
  controllers: [ResearchEvidenceController],
  providers: [
    ResearchEvidenceReadService,
    {
      provide: 'ResearchEvidenceReadRepository',
      useClass: PostgresResearchEvidenceReadRepository,
    },
  ],
})
export class ResearchEvidenceModule {}
