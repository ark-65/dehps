import { BadRequestException, Controller, Get, Inject, Query } from '@nestjs/common';
import { DrawSyncReadService } from './draw-sync.service';

@Controller('draw-sync')
export class DrawSyncController {
  constructor(@Inject(DrawSyncReadService) private readonly service: DrawSyncReadService) {}

  @Get('status')
  status() {
    return this.service.status();
  }

  @Get('runs')
  runs(@Query() query: Record<string, string | undefined>) {
    return this.service.runs(
      this.integer(query.limit, 'limit') ?? 100,
      this.integer(query.offset, 'offset') ?? 0,
    );
  }

  @Get('events')
  events(@Query() query: Record<string, string | undefined>) {
    return this.service.events(
      this.integer(query.limit, 'limit') ?? 100,
      this.integer(query.offset, 'offset') ?? 0,
    );
  }

  private integer(value: string | undefined, label: string): number | undefined {
    if (value === undefined || value.trim() === '') return undefined;
    if (!/^\d+$/.test(value.trim())) throw new BadRequestException(`${label} must be a decimal integer`);
    const parsed = Number(value);
    if (!Number.isSafeInteger(parsed)) throw new BadRequestException(`${label} is outside the safe integer range`);
    return parsed;
  }
}
