import { Module } from '@nestjs/common';
import { EngineeringController } from './engineering.controller';
import { PostgresEngineeringReadRepository } from './engineering.repository';
import { EngineeringReadService } from './engineering.service';

@Module({
  controllers: [EngineeringController],
  providers: [
    EngineeringReadService,
    {
      provide: 'EngineeringReadRepository',
      useClass: PostgresEngineeringReadRepository,
    },
  ],
})
export class EngineeringModule {}
