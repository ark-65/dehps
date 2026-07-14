import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { parseDbPort } from '../config';
import { ResearchDecisionReadRepository, ResearchDecisionRecord } from './research-decision.types';

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
  return Array.isArray(value) ? value : [];
}

function iso(value: unknown): string {
  return value instanceof Date ? value.toISOString() : new Date(String(value)).toISOString();
}

function optionalIso(value: unknown): string | null {
  return value === null || value === undefined ? null : iso(value);
}

@Injectable()
export class PostgresResearchDecisionReadRepository
  implements ResearchDecisionReadRepository, OnModuleDestroy
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

  async listDecisions(limit: number, offset: number): Promise<ResearchDecisionRecord[]> {
    const { rows } = await this.pool.query(
      `${baseQuery()} ORDER BY r.created_at DESC, r.id DESC LIMIT $1 OFFSET $2`,
      [limit, offset],
    );
    return rows.map(mapDecision);
  }

  async getDecision(key: string): Promise<ResearchDecisionRecord | null> {
    const { rows } = await this.pool.query(
      `${baseQuery()}
       WHERE r.request_key = $1 OR r.metadata_json->>'decision_key' = $1
       ORDER BY r.created_at DESC, r.id DESC LIMIT 1`,
      [key],
    );
    return rows[0] ? mapDecision(rows[0]) : null;
  }

  async reviewStatus(): Promise<{ pending: number; completed: number; rejected: number }> {
    const { rows } = await this.pool.query(
      `SELECT
         count(*) FILTER (WHERE status IN ('submitted', 'under_review', 'approved', 'executing'))::int AS pending,
         count(*) FILTER (WHERE status = 'completed')::int AS completed,
         count(*) FILTER (WHERE status = 'rejected')::int AS rejected
       FROM agent_requests
       WHERE request_type = 'research_decision_submission'`,
    );
    const row = rows[0] ?? {};
    return {
      pending: Number(row.pending ?? 0),
      completed: Number(row.completed ?? 0),
      rejected: Number(row.rejected ?? 0),
    };
  }
}

function baseQuery() {
  return `SELECT r.*, e.result_json
          FROM agent_requests r
          LEFT JOIN LATERAL (
            SELECT result_json FROM agent_request_executions e
            WHERE e.request_id = r.id
            ORDER BY e.started_at DESC, e.id DESC
            LIMIT 1
          ) e ON true
          WHERE r.request_type = 'research_decision_submission'`;
}

export function mapDecision(row: Row): ResearchDecisionRecord {
  const payload = object(row.payload_json);
  const metadata = object(row.metadata_json);
  return {
    key: String(metadata.decision_key ?? row.request_key),
    requestKey: String(row.request_key),
    status: String(row.status),
    proposedStatus: String(payload.proposed_status ?? ''),
    hypothesisKey: String(payload.hypothesis_key ?? ''),
    evidenceIds: array(payload.evidence_ids),
    payload,
    executionResult: object(row.result_json),
    createdAt: iso(row.created_at),
    resolvedAt: optionalIso(row.resolved_at),
  };
}
