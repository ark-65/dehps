import { BadRequestException, Controller, Get, Inject, Param, Query } from '@nestjs/common';
import { ResearchPlanningReadService } from './research-planning.service';

@Controller('research-planning')
export class ResearchPlanningController {
  constructor(@Inject(ResearchPlanningReadService) private readonly service: ResearchPlanningReadService) {}

  @Get('plans')
  plans(@Query() query: Record<string, string | undefined>) {
    return this.service.plans(
      this.integer(query.limit, 'limit') ?? 100,
      this.integer(query.offset, 'offset') ?? 0,
    );
  }

  @Get('plans/:key')
  plan(@Param('key') key: string) {
    return this.service.plan(key);
  }

  @Get('plans/:key/stages')
  stages(@Param('key') key: string) {
    return this.service.stages(key);
  }

  @Get('plans/:key/requests')
  requests(@Param('key') key: string) {
    return this.service.requests(key);
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
