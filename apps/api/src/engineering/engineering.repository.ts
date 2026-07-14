import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { parseDbPort } from '../config';
import { EngineeringContractRecord, EngineeringPlanRecord, EngineeringReadRepository } from './engineering.types';

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

function iso(value: unknown): string {
  return value instanceof Date ? value.toISOString() : new Date(String(value)).toISOString();
}

@Injectable()
export class PostgresEngineeringReadRepository
  implements EngineeringReadRepository, OnModuleDestroy
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

  async listContracts(limit: number, offset: number): Promise<EngineeringContractRecord[]> {
    const { rows } = await this.pool.query(
      `${contractQuery()} ORDER BY r.created_at DESC, r.id DESC LIMIT $1 OFFSET $2`,
      [limit, offset],
    );
    return rows.map(mapEngineeringContract);
  }

  async latestPlan(): Promise<EngineeringPlanRecord | null> {
    const { rows } = await this.pool.query(
      `${planQuery()} ORDER BY h.created_at DESC, h.id DESC LIMIT 1`,
    );
    return rows[0] ? mapEngineeringPlan(rows[0]) : null;
  }

  async countContracts(): Promise<number> {
    const { rows } = await this.pool.query(
      `SELECT count(*)::int AS count FROM agent_requests WHERE request_type = 'engineering_experiment_tool'`,
    );
    return Number(rows[0]?.count ?? 0);
  }

  async countPlans(): Promise<number> {
    const { rows } = await this.pool.query(
      `SELECT count(*)::int AS count FROM research_hypotheses WHERE metadata_json ? 'experiment_plan'`,
    );
    return Number(rows[0]?.count ?? 0);
  }
}

function contractQuery() {
  return `SELECT r.*, h.hypothesis_key, e.experiment_key
          FROM agent_requests r
          LEFT JOIN research_hypotheses h ON h.id = r.hypothesis_id
          LEFT JOIN research_hypothesis_experiments e ON e.id = r.experiment_id
          WHERE r.request_type = 'engineering_experiment_tool'`;
}

function planQuery() {
  return `SELECT h.hypothesis_key, h.status AS hypothesis_status, h.metadata_json
          FROM research_hypotheses h
          WHERE h.metadata_json ? 'experiment_plan'`;
}

export function mapEngineeringContract(row: Row): EngineeringContractRecord {
  const payload = object(row.payload_json);
  const metadata = object(row.metadata_json);
  return {
    requestKey: String(row.request_key),
    status: String(row.status),
    requestedBy: String(row.requested_by),
    title: String(row.title),
    hypothesisKey: row.hypothesis_key == null ? null : String(row.hypothesis_key),
    experimentKey: row.experiment_key == null ? null : String(row.experiment_key),
    experimentPlanKey: String(payload.experiment_plan_key ?? metadata.experiment_plan_key ?? '') || null,
    planFingerprint: String(metadata.plan_fingerprint ?? '') || null,
    mechanism: String(payload.mechanism ?? '') || null,
    productionImpact: String(payload.production_impact ?? '') || null,
    payload,
    metadata,
    createdAt: iso(row.created_at),
    submittedAt: row.submitted_at == null ? null : iso(row.submitted_at),
  };
}

export function mapEngineeringPlan(row: Row): EngineeringPlanRecord {
  const metadata = object(row.metadata_json);
  const plan = object(metadata.experiment_plan);
  return {
    planKey: String(plan.plan_key ?? metadata.experiment_plan_key ?? ''),
    hypothesisKey: String(row.hypothesis_key),
    hypothesisStatus: String(row.hypothesis_status),
    planFingerprint: String(metadata.plan_fingerprint ?? plan.plan_fingerprint ?? '') || null,
    mechanism: String(plan.mechanism ?? '') || null,
    plan,
    metadata,
  };
}
