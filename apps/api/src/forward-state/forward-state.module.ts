import { Module } from '@nestjs/common';
import { ForwardStateController } from './forward-state.controller';
import { PostgresForwardStateReadRepository } from './forward-state.repository';
import { ForwardStateReadService } from './forward-state.service';

@Module({
  controllers: [ForwardStateController],
  providers: [
    ForwardStateReadService,
    {
      provide: 'ForwardStateReadRepository',
      useClass: PostgresForwardStateReadRepository,
    },
  ],
})
export class ForwardStateModule {}
