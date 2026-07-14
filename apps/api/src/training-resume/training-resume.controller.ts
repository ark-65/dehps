import { BadRequestException, Controller, Get, Inject, Query } from '@nestjs/common';
import { TrainingResumeReadService } from './training-resume.service';

@Controller('training-resume')
export class TrainingResumeController {
  constructor(@Inject(TrainingResumeReadService) private readonly service: TrainingResumeReadService) {}

  @Get('status')
  status() {
    return this.service.status();
  }

  @Get('history')
  history(@Query() query: Record<string, string | undefined>) {
    return this.service.history(
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
