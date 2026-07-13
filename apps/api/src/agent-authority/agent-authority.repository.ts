import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { parseDbPort } from '../config';
import {
  AgentRequestDecisionRecord,
  AgentRequestExecutionRecord,
  AgentRequestQuery,
  AgentRequestReadRepository,
  AgentRequestRecord,
} from './agent-authority.types';

type Row = Record<string, any>;

function object(value: unknown): Record<string, unknown> {
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value);
      return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
    } catch {
      return {};
    }
  }
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function array(value: unknown): unknown[] {
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }
  return Array.isArray(value) ? value : [];
}

function iso(value: unknown): string {
  return value instanceof Date ? value.toISOString() : new Date(String(value)).toISOString();
}

function optionalIso(value: unknown): string | null {
  return value === null || value === undefined ? null : iso(value);
}

@Injectable()
export class PostgresAgentRequestReadRepository
  implements AgentRequestReadRepository, OnModuleDestroy
{
  private readonly pool = new Pool({
    host: process.env.DB_HOST ?? 'localhost',
    port: parseDbPort(process.env.DB_PORT),
    database: process.env.DB_NAME ?? 'dehps',
    user: process.env.DB_USER ?? 'dehps',
    password: process.env.DB_PASSWORD ?? 'dehps_password',
  });

  async onModuleDestroy() {
    await this.pool.end();
  }

  async listRequests(query: AgentRequestQuery): Promise<AgentRequestRecord[]> {
    const clauses: string[] = [];
    const values: unknown[] = [];
    const add = (column: string, value: unknown, operator = '=') => {
      values.push(value);
      clauses.push(`${column} ${operator} $${values.length}`);
    };
    if (query.status) add('status', query.status);
    if (query.requestType) add('request_type', query.requestType);
    if (query.requestedByRole) add('requested_by_role', query.requestedByRole);
    if (query.riskLevel) add('risk_level', query.riskLevel);
    if (query.createdAfter) add('created_at', query.createdAfter, '>=');
    if (query.createdBefore) add('created_at', query.createdBefore, '<=');
    values.push(query.limit, query.offset);
    const { rows } = await this.pool.query(
      `SELECT * FROM agent_requests
       ${clauses.length ? `WHERE ${clauses.join(' AND ')}` : ''}
       ORDER BY created_at DESC, id DESC
       LIMIT $${values.length - 1} OFFSET $${values.length}`,
      values,
    );
    return rows.map(mapRequest);
  }

  async getRequest(requestKey: string): Promise<AgentRequestRecord | null> {
    const { rows } = await this.pool.query(
      'SELECT * FROM agent_requests WHERE request_key = $1 LIMIT 1',
      [requestKey],
    );
    return rows[0] ? mapRequest(rows[0]) : null;
  }

  async listDecisions(requestKey: string): Promise<AgentRequestDecisionRecord[]> {
    const { rows } = await this.pool.query(
      `SELECT d.* FROM agent_request_decisions d
       JOIN agent_requests r ON r.id = d.request_id
       WHERE r.request_key = $1 ORDER BY d.decided_at, d.id`,
      [requestKey],
    );
    return rows.map(mapDecision);
  }

  async listExecutions(requestKey: string): Promise<AgentRequestExecutionRecord[]> {
    const { rows } = await this.pool.query(
      `SELECT e.* FROM agent_request_executions e
       JOIN agent_requests r ON r.id = e.request_id
       WHERE r.request_key = $1 ORDER BY e.started_at, e.id`,
      [requestKey],
    );
    return rows.map(mapExecution);
  }
}

export function mapRequest(row: Row): AgentRequestRecord {
  return {
    id: Number(row.id), requestKey: row.request_key, requestType: row.request_type,
    requestedByRole: row.requested_by_role, requestedBy: row.requested_by,
    hypothesisId: row.hypothesis_id == null ? null : Number(row.hypothesis_id),
    experimentId: row.experiment_id == null ? null : Number(row.experiment_id),
    parentRequestId: row.parent_request_id == null ? null : Number(row.parent_request_id),
    title: row.title, summary: row.summary, payload: object(row.payload_json), status: row.status,
    riskLevel: row.risk_level, requiresReview: Boolean(row.requires_review),
    createdAt: iso(row.created_at), updatedAt: iso(row.updated_at),
    submittedAt: optionalIso(row.submitted_at), resolvedAt: optionalIso(row.resolved_at),
    metadata: object(row.metadata_json),
  };
}

function mapDecision(row: Row): AgentRequestDecisionRecord {
  return {
    id: Number(row.id), requestId: Number(row.request_id), previousStatus: row.previous_status,
    newStatus: row.new_status, decisionCode: row.decision_code, summary: row.summary,
    reason: object(row.reason_json), decidedByRole: row.decided_by_role, decidedBy: row.decided_by,
    decidedAt: iso(row.decided_at), createdAt: iso(row.created_at),
  };
}

function mapExecution(row: Row): AgentRequestExecutionRecord {
  return {
    id: Number(row.id), requestId: Number(row.request_id), executorRole: row.executor_role,
    executorId: row.executor_id, executionType: row.execution_type, status: row.status,
    environment: row.environment, runId: row.run_id ?? null, startedAt: iso(row.started_at),
    completedAt: optionalIso(row.completed_at), result: object(row.result_json),
    artifactPaths: array(row.artifact_paths_json), error: object(row.error_json),
    createdAt: iso(row.created_at),
  };
}
