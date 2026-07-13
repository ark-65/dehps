import { BadRequestException, Controller, Get, Param, Query } from '@nestjs/common';
import { ResearchAutonomyReadService } from './research-autonomy.service';

@Controller('research-autonomy')
export class ResearchAutonomyController {
  constructor(private readonly service: ResearchAutonomyReadService) {}

  @Get('context')
  context() {
    return this.service.context();
  }

  @Get('proposals')
  proposals(@Query() query: Record<string, string | undefined>) {
    return this.service.proposals(
      this.integer(query.limit, 'limit') ?? 100,
      this.integer(query.offset, 'offset') ?? 0,
    );
  }

  @Get('proposals/:key')
  proposal(@Param('key') key: string) {
    return this.service.proposal(key);
  }

  @Get('engine-status')
  engineStatus() {
    return this.service.engineStatus();
  }

  private integer(value: string | undefined, label: string): number | undefined {
    if (value === undefined || value.trim() === '') return undefined;
    if (!/^\d+$/.test(value.trim())) throw new BadRequestException(`${label} must be a decimal integer`);
    const parsed = Number(value);
    if (!Number.isSafeInteger(parsed)) throw new BadRequestException(`${label} is outside the safe integer range`);
    return parsed;
  }
}
