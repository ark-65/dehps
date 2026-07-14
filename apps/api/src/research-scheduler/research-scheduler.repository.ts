import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { parseDbPort } from '../config';
import { ResearchSchedulerQueueRecord, ResearchSchedulerReadRepository } from './research-scheduler.types';

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
export class PostgresResearchSchedulerReadRepository
  implements ResearchSchedulerReadRepository, OnModuleDestroy
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

  async listQueue(limit: number, offset: number): Promise<ResearchSchedulerQueueRecord[]> {
    const { rows } = await this.pool.query(
      `${baseQuery()} ORDER BY q.created_at DESC, q.id DESC LIMIT $1 OFFSET $2`,
      [limit, offset],
    );
    return rows.map(mapSchedulerQueue);
  }

  async latestQueueItem(): Promise<ResearchSchedulerQueueRecord | null> {
    const { rows } = await this.pool.query(`${baseQuery()} ORDER BY q.created_at DESC, q.id DESC LIMIT 1`);
    return rows[0] ? mapSchedulerQueue(rows[0]) : null;
  }

  async countOpenQueue(): Promise<number> {
    const { rows } = await this.pool.query(
      `SELECT count(*)::int AS count
       FROM research_scheduler_queue
       WHERE queue_status NOT IN ('completed', 'blocked')`,
    );
    return Number(rows[0]?.count ?? 0);
  }

  async countSchedulerRequests(): Promise<number> {
    const { rows } = await this.pool.query(
      `SELECT count(*)::int AS count
       FROM agent_requests
       WHERE request_type = 'research_scheduler_request'`,
    );
    return Number(rows[0]?.count ?? 0);
  }
}

function baseQuery() {
  return `SELECT q.*, r.status AS request_status
          FROM research_scheduler_queue q
          LEFT JOIN agent_requests r ON r.request_key = q.request_key`;
}

export function mapSchedulerQueue(row: Row): ResearchSchedulerQueueRecord {
  return {
    id: Number(row.id),
    queueKey: String(row.queue_key),
    queueStatus: String(row.queue_status),
    action: String(row.action),
    priorityScore: Number(row.priority_score),
    targetHypothesisKey: row.target_hypothesis_key == null ? null : String(row.target_hypothesis_key),
    targetFamilyKey: row.target_family_key == null ? null : String(row.target_family_key),
    targetExperimentKey: row.target_experiment_key == null ? null : String(row.target_experiment_key),
    requestKey: row.request_key == null ? null : String(row.request_key),
    requestStatus: row.request_status == null ? null : String(row.request_status),
    contextFingerprint: String(row.context_fingerprint),
    reason: object(row.reason_json),
    budget: object(row.budget_json),
    policy: object(row.policy_json),
    createdBy: String(row.created_by),
    createdAt: iso(row.created_at),
    updatedAt: iso(row.updated_at),
    completedAt: row.completed_at == null ? null : iso(row.completed_at),
    metadata: object(row.metadata_json),
  };
}
