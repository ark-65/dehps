import { BadRequestException, Controller, Get, Inject, Param, Query } from '@nestjs/common';
import { ResearchDecisionReadService } from './research-decision.service';

@Controller()
export class ResearchDecisionController {
  constructor(@Inject(ResearchDecisionReadService) private readonly service: ResearchDecisionReadService) {}

  @Get('research-decisions')
  decisions(@Query() query: Record<string, string | undefined>) {
    return this.service.decisions(
      this.integer(query.limit, 'limit') ?? 100,
      this.integer(query.offset, 'offset') ?? 0,
    );
  }

  @Get('research-decisions/:key')
  decision(@Param('key') key: string) {
    return this.service.decision(key);
  }

  @Get('research-review/status')
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
