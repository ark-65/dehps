import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { parseDbPort } from '../config';
import {
  TrainingResumeAttemptRecord,
  TrainingResumeReadRepository,
  TrainingResumeStatusRecord,
} from './training-resume.types';

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

function nullableIso(value: unknown): string | null {
  return value == null ? null : iso(value);
}

@Injectable()
export class PostgresTrainingResumeReadRepository
  implements TrainingResumeReadRepository, OnModuleDestroy
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

  async history(limit: number, offset: number): Promise<TrainingResumeAttemptRecord[]> {
    const { rows } = await this.pool.query(
      `SELECT *
       FROM training_resume_attempts
       ORDER BY started_at DESC, id DESC
       LIMIT $1 OFFSET $2`,
      [limit, offset],
    );
    return rows.map(mapTrainingResumeAttempt);
  }

  async status(): Promise<TrainingResumeStatusRecord> {
    const latest = await this.pool.query(
      `SELECT * FROM training_resume_attempts ORDER BY started_at DESC, id DESC LIMIT 1`,
    );
    const retryable = await this.pool.query(
      `SELECT count(*)::int AS count FROM draw_issue_events WHERE status IN ('pending', 'failed')`,
    );
    return {
      latestAttempt: latest.rows[0] ? mapTrainingResumeAttempt(latest.rows[0]) : null,
      retryableEventCount: Number(retryable.rows[0]?.count ?? 0),
    };
  }
}

export function mapTrainingResumeAttempt(row: Row): TrainingResumeAttemptRecord {
  return {
    id: Number(row.id),
    attemptKey: String(row.attempt_key),
    eventKey: row.event_key == null ? null : String(row.event_key),
    decision: String(row.decision),
    reasonCode: String(row.reason_code),
    oldRunId: row.old_run_id == null ? null : String(row.old_run_id),
    newRunId: row.new_run_id == null ? null : String(row.new_run_id),
    startedAt: iso(row.started_at),
    completedAt: nullableIso(row.completed_at),
    result: object(row.result_json),
  };
}
