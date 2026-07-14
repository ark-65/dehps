import { Module } from '@nestjs/common';
import { DrawSyncController } from './draw-sync.controller';
import { PostgresDrawSyncReadRepository } from './draw-sync.repository';
import { DrawSyncReadService } from './draw-sync.service';

@Module({
  controllers: [DrawSyncController],
  providers: [
    DrawSyncReadService,
    {
      provide: 'DrawSyncReadRepository',
      useClass: PostgresDrawSyncReadRepository,
    },
  ],
})
export class DrawSyncModule {}
