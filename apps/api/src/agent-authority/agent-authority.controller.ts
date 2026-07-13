import { BadRequestException, Controller, Get, Param, Query } from '@nestjs/common';
import { AgentAuthorityReadService, RawAgentRequestQuery } from './agent-authority.service';

@Controller('agent')
export class AgentAuthorityController {
  constructor(private readonly service: AgentAuthorityReadService) {}

  @Get('requests')
  requests(@Query() query: Record<string, string | undefined>) {
    return this.service.listRequests(this.query(query));
  }

  @Get('requests/:key')
  request(@Param('key') key: string) {
    return this.service.getRequest(key);
  }

  @Get('requests/:key/decisions')
  decisions(@Param('key') key: string) {
    return this.service.listDecisions(key);
  }

  @Get('requests/:key/executions')
  executions(@Param('key') key: string) {
    return this.service.listExecutions(key);
  }

  @Get('authority')
  authority() {
    return this.service.authority();
  }

  private query(query: Record<string, string | undefined>): RawAgentRequestQuery {
    return {
      status: query.status,
      requestType: query.request_type,
      requestedByRole: query.requested_by_role,
      riskLevel: query.risk_level,
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
