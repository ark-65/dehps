import { BadRequestException, Controller, Get, Inject, Query } from '@nestjs/common';
import { EngineeringReadService } from './engineering.service';

@Controller('engineering')
export class EngineeringController {
  constructor(@Inject(EngineeringReadService) private readonly service: EngineeringReadService) {}

  @Get('contracts')
  contracts(@Query() query: Record<string, string | undefined>) {
    return this.service.contracts(
      this.integer(query.limit, 'limit') ?? 100,
      this.integer(query.offset, 'offset') ?? 0,
    );
  }

  @Get('plan')
  plan() {
    return this.service.plan();
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
