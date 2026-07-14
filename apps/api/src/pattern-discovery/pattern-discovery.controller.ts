import { BadRequestException, Controller, Get, Inject, Param, Query } from '@nestjs/common';
import { PatternDiscoveryReadService } from './pattern-discovery.service';

@Controller('pattern-discovery')
export class PatternDiscoveryController {
  constructor(@Inject(PatternDiscoveryReadService) private readonly service: PatternDiscoveryReadService) {}

  @Get('patterns')
  patterns(@Query() query: Record<string, string | undefined>) {
    return this.service.patterns(
      this.integer(query.limit, 'limit') ?? 100,
      this.integer(query.offset, 'offset') ?? 0,
    );
  }

  @Get('patterns/:key')
  pattern(@Param('key') key: string) {
    return this.service.pattern(key);
  }

  @Get('families')
  families() {
    return this.service.families();
  }

  @Get('features')
  features(@Query() query: Record<string, string | undefined>) {
    return this.service.features(
      this.integer(query.limit, 'limit') ?? 100,
      this.integer(query.offset, 'offset') ?? 0,
    );
  }

  @Get('strategies')
  strategies(@Query() query: Record<string, string | undefined>) {
    return this.service.strategies(
      this.integer(query.limit, 'limit') ?? 100,
      this.integer(query.offset, 'offset') ?? 0,
    );
  }

  @Get('cycles')
  cycles(@Query() query: Record<string, string | undefined>) {
    return this.service.cycles(
      this.integer(query.limit, 'limit') ?? 100,
      this.integer(query.offset, 'offset') ?? 0,
    );
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
