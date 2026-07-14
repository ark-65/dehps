import { BadRequestException, Controller, Get, Inject, Param, Query } from '@nestjs/common';
import { ResearchExecutionReadService } from './research-execution.service';

@Controller('research-execution')
export class ResearchExecutionController {
  constructor(@Inject(ResearchExecutionReadService) private readonly service: ResearchExecutionReadService) {}

  @Get('runs')
  runs(@Query() query: Record<string, string | undefined>) {
    return this.service.runs(
      this.integer(query.limit, 'limit') ?? 100,
      this.integer(query.offset, 'offset') ?? 0,
    );
  }

  @Get('runs/:id')
  run(@Param('id') id: string) {
    return this.service.run(id);
  }

  @Get('runs/:id/artifacts')
  artifacts(@Param('id') id: string) {
    return this.service.artifacts(id);
  }

  @Get('runs/:id/results')
  results(@Param('id') id: string) {
    return this.service.results(id);
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
