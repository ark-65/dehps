import { Module } from '@nestjs/common';
import { PatternDiscoveryController } from './pattern-discovery.controller';
import { PostgresPatternDiscoveryReadRepository } from './pattern-discovery.repository';
import { PatternDiscoveryReadService } from './pattern-discovery.service';

@Module({
  controllers: [PatternDiscoveryController],
  providers: [
    PatternDiscoveryReadService,
    {
      provide: 'PatternDiscoveryReadRepository',
      useClass: PostgresPatternDiscoveryReadRepository,
    },
  ],
})
export class PatternDiscoveryModule {}
