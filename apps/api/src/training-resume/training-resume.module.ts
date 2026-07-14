import { Module } from '@nestjs/common';
import { TrainingResumeController } from './training-resume.controller';
import { PostgresTrainingResumeReadRepository } from './training-resume.repository';
import { TrainingResumeReadService } from './training-resume.service';

@Module({
  controllers: [TrainingResumeController],
  providers: [
    TrainingResumeReadService,
    {
      provide: 'TrainingResumeReadRepository',
      useClass: PostgresTrainingResumeReadRepository,
    },
  ],
})
export class TrainingResumeModule {}
