import { BadRequestException, Inject, Injectable, NotFoundException } from '@nestjs/common';
import { AgentRequestQuery, AgentRequestReadRepository } from './agent-authority.types';

const ROLES = ['research', 'engineering', 'reviewer', 'operator'] as const;
const ACTIONS = [
  'read_hypothesis', 'create_hypothesis_proposal', 'create_experiment_plan',
  'submit_preregistration', 'add_evidence_proposal', 'submit_hypothesis_decision',
  'create_engineering_request', 'modify_code', 'run_tests', 'run_isolated_experiment',
  'create_pull_request', 'review_request', 'approve_request', 'reject_request',
  'cancel_request', 'restart_production_supervisor', 'apply_database_migration',
  'publish_release', 'promote_production_strategy',
] as const;
const REQUEST_STATUSES = new Set([
  'draft', 'submitted', 'under_review', 'approved', 'rejected', 'cancelled',
  'executing', 'completed', 'failed', 'invalidated',
]);
const REQUEST_TYPES = new Set([
  'research_hypothesis_proposal', 'research_preregistration', 'research_experiment_plan',
  'research_evidence_submission', 'research_decision_submission', 'engineering_implementation',
  'engineering_bug_fix', 'engineering_test_addition', 'engineering_runtime_fix',
  'engineering_experiment_tool', 'operator_isolated_run', 'operator_database_migration',
  'operator_supervisor_restart', 'operator_release',
]);
const RISK_LEVELS = new Set(['low', 'medium', 'high', 'critical']);
const ROLE_ACTIONS: Record<(typeof ROLES)[number], string[]> = {
  research: [
    'read_hypothesis', 'create_hypothesis_proposal', 'create_experiment_plan',
    'submit_preregistration', 'add_evidence_proposal', 'submit_hypothesis_decision',
    'create_engineering_request', 'cancel_request',
  ],
  engineering: [
    'read_hypothesis', 'create_engineering_request', 'modify_code', 'run_tests',
    'create_pull_request', 'cancel_request',
  ],
  reviewer: ['read_hypothesis', 'review_request', 'approve_request', 'reject_request'],
  operator: [
    'read_hypothesis', 'run_isolated_experiment', 'restart_production_supervisor',
    'apply_database_migration', 'publish_release', 'cancel_request',
  ],
};

export type RawAgentRequestQuery = {
  status?: string;
  requestType?: string;
  requestedByRole?: string;
  riskLevel?: string;
  createdAfter?: string;
  createdBefore?: string;
  limit?: number;
  offset?: number;
};

@Injectable()
export class AgentAuthorityReadService {
  constructor(
    @Inject('AgentRequestReadRepository') private readonly repository: AgentRequestReadRepository,
  ) {}

  async listRequests(raw: RawAgentRequestQuery) {
    const query = this.query(raw);
    return { entity: 'agent_request', items: await this.repository.listRequests(query), limit: query.limit, offset: query.offset };
  }

  async getRequest(requestKey: string) {
    const item = await this.requireRequest(requestKey);
    return { entity: 'agent_request', data: item };
  }

  async listDecisions(requestKey: string) {
    await this.requireRequest(requestKey);
    return { entity: 'agent_request_decision', items: await this.repository.listDecisions(requestKey.trim()) };
  }

  async listExecutions(requestKey: string) {
    await this.requireRequest(requestKey);
    return { entity: 'agent_request_execution', items: await this.repository.listExecutions(requestKey.trim()) };
  }

  authority() {
    return {
      default: 'deny',
      roles: ROLES,
      actions: ACTIONS,
      permissions: ROLE_ACTIONS,
      productionStrategyPromotion: {
        agentAuthorized: false,
        authority: 'existing_promotion_gate',
      },
    };
  }

  private async requireRequest(key: string) {
    const item = await this.repository.getRequest(key.trim());
    if (!item) throw new NotFoundException(`agent request not found: ${key}`);
    return item;
  }

  private query(raw: RawAgentRequestQuery): AgentRequestQuery {
    const status = this.member(raw.status, REQUEST_STATUSES, 'status');
    const requestType = this.member(raw.requestType, REQUEST_TYPES, 'request_type');
    const requestedByRole = this.member(raw.requestedByRole, new Set(ROLES), 'requested_by_role');
    const riskLevel = this.member(raw.riskLevel, RISK_LEVELS, 'risk_level');
    const createdAfter = this.date(raw.createdAfter, 'created_after');
    const createdBefore = this.date(raw.createdBefore, 'created_before');
    if (createdAfter && createdBefore && createdAfter > createdBefore) {
      throw new BadRequestException('created_after must not be later than created_before');
    }
    const limit = raw.limit ?? 100;
    const offset = raw.offset ?? 0;
    if (!Number.isSafeInteger(limit) || limit < 1 || limit > 500) {
      throw new BadRequestException('limit must be an integer between 1 and 500');
    }
    if (!Number.isSafeInteger(offset) || offset < 0) {
      throw new BadRequestException('offset must be a non-negative integer');
    }
    return { status, requestType, requestedByRole, riskLevel, createdAfter, createdBefore, limit, offset };
  }

  private member(value: string | undefined, allowed: Set<string>, label: string) {
    const normalized = value?.trim() || undefined;
    if (normalized && !allowed.has(normalized)) {
      throw new BadRequestException(`invalid ${label}: ${normalized}`);
    }
    return normalized;
  }

  private date(value: string | undefined, label: string): Date | undefined {
    if (!value?.trim()) return undefined;
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) throw new BadRequestException(`${label} must be an ISO date-time`);
    return parsed;
  }
}
