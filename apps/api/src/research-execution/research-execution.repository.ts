import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { parseDbPort } from '../config';
import { ResearchExecutionReadRepository, ResearchExecutionRunRecord } from './research-execution.types';

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

function optionalIso(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  return value instanceof Date ? value.toISOString() : new Date(String(value)).toISOString();
}

@Injectable()
export class PostgresResearchExecutionReadRepository
  implements ResearchExecutionReadRepository, OnModuleDestroy
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

  async listRuns(limit: number, offset: number): Promise<ResearchExecutionRunRecord[]> {
    const { rows } = await this.pool.query(
      `${baseQuery()}
       ORDER BY COALESCE(e.started_at, r.created_at) DESC, r.id DESC
       LIMIT $1 OFFSET $2`,
      [limit, offset],
    );
    return rows.map(mapRun);
  }

  async getRun(id: string): Promise<ResearchExecutionRunRecord | null> {
    const { rows } = await this.pool.query(
      `${baseQuery()}
       AND (r.request_key = $1 OR e.run_id = $1 OR e.id::text = $1)
       ORDER BY COALESCE(e.started_at, r.created_at) DESC, r.id DESC
       LIMIT 1`,
      [id],
    );
    return rows[0] ? mapRun(rows[0]) : null;
  }

  async latestRun(): Promise<ResearchExecutionRunRecord | null> {
    const items = await this.listRuns(1, 0);
    return items[0] ?? null;
  }

  async countRuns(): Promise<{ total: number; completed: number; failed: number; running: number }> {
    const { rows } = await this.pool.query(
      `SELECT
         count(*)::int AS total,
         count(*) FILTER (WHERE r.status = 'completed')::int AS completed,
         count(*) FILTER (WHERE r.status = 'failed')::int AS failed,
         count(*) FILTER (WHERE r.status = 'executing')::int AS running
       FROM agent_requests r
       WHERE r.request_type = 'operator_isolated_run'`,
    );
    const row = rows[0] ?? {};
    return {
      total: Number(row.total ?? 0),
      completed: Number(row.completed ?? 0),
      failed: Number(row.failed ?? 0),
      running: Number(row.running ?? 0),
    };
  }
}

function baseQuery() {
  return `SELECT r.request_key, r.status AS request_status, r.payload_json, r.metadata_json,
                 e.id AS execution_id, e.status AS execution_status, e.run_id, e.environment,
                 e.started_at, e.completed_at, e.result_json, e.artifact_paths_json, e.error_json
          FROM agent_requests r
          LEFT JOIN LATERAL (
            SELECT * FROM agent_request_executions e
            WHERE e.request_id = r.id
            ORDER BY e.started_at DESC, e.id DESC
            LIMIT 1
          ) e ON true
          WHERE r.request_type = 'operator_isolated_run'`;
}

export function mapRun(row: Row): ResearchExecutionRunRecord {
  const payload = object(row.payload_json);
  const result = object(row.result_json);
  const runContract = object(payload.run_contract);
  const planKey = String(payload.experiment_plan_key ?? result.plan_key ?? '');
  const runId = row.run_id == null ? null : String(row.run_id);
  return {
    id: runId ?? String(row.request_key),
    requestKey: String(row.request_key),
    requestStatus: String(row.request_status),
    executionId: row.execution_id == null ? null : Number(row.execution_id),
    executionStatus: row.execution_status == null ? null : String(row.execution_status),
    runId,
    planKey,
    planFingerprint: String(runContract.plan_fingerprint ?? result.plan_fingerprint ?? ''),
    experimentKey: String(payload.experiment_key ?? ''),
    environment: String(row.environment ?? payload.environment ?? 'isolated'),
    productionAccess: payload.production_access === true || result.production_access === true,
    startedAt: optionalIso(row.started_at),
    completedAt: optionalIso(row.completed_at),
    artifactPaths: array(row.artifact_paths_json),
    result,
    error: object(row.error_json),
  };
}
