import { BadRequestException, Controller, Get, Param, Query } from '@nestjs/common';
import { RawRegistryQuery, ResearchHypothesisReadService } from './research-hypothesis.service';

@Controller('research')
export class ResearchHypothesisController {
  constructor(private readonly service: ResearchHypothesisReadService) {}

  @Get('hypothesis-families')
  families(@Query() query: Record<string, string | undefined>) {
    return this.service.listFamilies(this.query(query));
  }

  @Get('hypothesis-families/:key')
  family(@Param('key') key: string) {
    return this.service.getFamily(key);
  }

  @Get('hypotheses')
  hypotheses(@Query() query: Record<string, string | undefined>) {
    return this.service.listHypotheses(this.query(query));
  }

  @Get('hypotheses/:key')
  hypothesis(@Param('key') key: string) {
    return this.service.getHypothesis(key);
  }

  @Get('hypotheses/:key/experiments')
  experiments(@Param('key') key: string, @Query() query: Record<string, string | undefined>) {
    return this.service.listExperiments(key, this.query(query));
  }

  @Get('hypotheses/:key/evidence')
  evidence(@Param('key') key: string, @Query() query: Record<string, string | undefined>) {
    return this.service.listEvidence(key, this.query(query));
  }

  @Get('hypotheses/:key/decisions')
  decisions(@Param('key') key: string, @Query() query: Record<string, string | undefined>) {
    return this.service.listDecisions(key, this.query(query));
  }

  private query(query: Record<string, string | undefined>): RawRegistryQuery {
    return {
      status: query.status,
      familyKey: query.family_key,
      createdAfter: query.created_after,
      createdBefore: query.created_before,
      limit: this.integer(query.limit, 'limit'),
      offset: this.integer(query.offset, 'offset'),
    };
  }

  private integer(value: string | undefined, label: string): number | undefined {
    if (value === undefined || value.trim() === '') return undefined;
    if (!/^\d+$/.test(value.trim())) throw new BadRequestException(`${label} must be a decimal integer`);
    const parsed = Number(value);
    if (!Number.isSafeInteger(parsed)) throw new BadRequestException(`${label} is outside the safe integer range`);
    return parsed;
  }
}
