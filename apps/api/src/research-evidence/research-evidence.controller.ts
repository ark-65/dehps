import { BadRequestException, Controller, Get, Inject, Param, Query } from '@nestjs/common';
import { ResearchEvidenceReadService } from './research-evidence.service';

@Controller('research-evidence')
export class ResearchEvidenceController {
  constructor(@Inject(ResearchEvidenceReadService) private readonly service: ResearchEvidenceReadService) {}

  @Get()
  evidence(@Query() query: Record<string, string | undefined>) {
    return this.service.evidence(
      this.integer(query.limit, 'limit') ?? 100,
      this.integer(query.offset, 'offset') ?? 0,
    );
  }

  @Get(':key')
  evidenceByKey(@Param('key') key: string) {
    return this.service.evidenceByKey(key);
  }

  private integer(value: string | undefined, label: string): number | undefined {
    if (value === undefined || value.trim() === '') return undefined;
    if (!/^\d+$/.test(value.trim())) throw new BadRequestException(`${label} must be a decimal integer`);
    const parsed = Number(value);
    if (!Number.isSafeInteger(parsed)) throw new BadRequestException(`${label} is outside the safe integer range`);
    return parsed;
  }
}
