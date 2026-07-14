import { BadRequestException, Controller, Get, Inject, Query } from '@nestjs/common';
import { ResearchSchedulerReadService } from './research-scheduler.service';

@Controller('scheduler')
export class ResearchSchedulerController {
  constructor(@Inject(ResearchSchedulerReadService) private readonly service: ResearchSchedulerReadService) {}

  @Get()
  scheduler() {
    return this.service.scheduler();
  }

  @Get('queue')
  queue(@Query() query: Record<string, string | undefined>) {
    return this.service.queue(
      this.integer(query.limit, 'limit') ?? 100,
      this.integer(query.offset, 'offset') ?? 0,
    );
  }

  @Get('next')
  next() {
    return this.service.next();
  }

  @Get('status')
  status() {
    return this.service.status();
  }

  private integer(value: string | undefined, label: string): number | undefined {
    if (value === undefined || value.trim() === '') return undefined;
    if (!/^\d+$/.test(value.trim())) throw new BadRequestException(`${label} must be a decimal integer`);
    const parsed = Number(value);
    if (!Number.isSafeInteger(parsed)) throw new BadRequestException(`${label} is outside the safe integer range`);
    return parsed;
  }
}
