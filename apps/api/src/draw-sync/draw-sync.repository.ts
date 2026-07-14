import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { parseDbPort } from '../config';
import {
  DrawIssueEventRecord,
  DrawSyncReadRepository,
  DrawSyncRunRecord,
  DrawSyncStatusRecord,
} from './draw-sync.types';

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

function nullableIso(value: unknown): string | null {
  return value == null ? null : iso(value);
}

@Injectable()
export class PostgresDrawSyncReadRepository implements DrawSyncReadRepository, OnModuleDestroy {
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

  async listRuns(limit: number, offset: number): Promise<DrawSyncRunRecord[]> {
    const { rows } = await this.pool.query(
      `SELECT *
       FROM draw_sync_runs
       ORDER BY started_at DESC, id DESC
       LIMIT $1 OFFSET $2`,
      [limit, offset],
    );
    return rows.map(mapDrawSyncRun);
  }

  async listEvents(limit: number, offset: number): Promise<DrawIssueEventRecord[]> {
    const { rows } = await this.pool.query(
      `SELECT *
       FROM draw_issue_events
       ORDER BY created_at DESC, id DESC
       LIMIT $1 OFFSET $2`,
      [limit, offset],
    );
    return rows.map(mapDrawIssueEvent);
  }

  async status(): Promise<DrawSyncStatusRecord> {
    const latestRun = await this.pool.query(
      `SELECT * FROM draw_sync_runs ORDER BY started_at DESC, id DESC LIMIT 1`,
    );
    const latestEvent = await this.pool.query(
      `SELECT * FROM draw_issue_events ORDER BY created_at DESC, id DESC LIMIT 1`,
    );
    const pending = await this.pool.query(
      `SELECT count(*)::int AS count FROM draw_issue_events WHERE status IN ('pending', 'failed')`,
    );
    return {
      latestRun: latestRun.rows[0] ? mapDrawSyncRun(latestRun.rows[0]) : null,
      latestEvent: latestEvent.rows[0] ? mapDrawIssueEvent(latestEvent.rows[0]) : null,
      pendingEventCount: Number(pending.rows[0]?.count ?? 0),
    };
  }
}

export function mapDrawSyncRun(row: Row): DrawSyncRunRecord {
  return {
    id: Number(row.id),
    runKey: String(row.run_key),
    startedAt: iso(row.started_at),
    completedAt: nullableIso(row.completed_at),
    status: String(row.status),
    previousLatestIssue: row.previous_latest_issue == null ? null : String(row.previous_latest_issue),
    currentLatestIssue: row.current_latest_issue == null ? null : String(row.current_latest_issue),
    insertedIssues: array(row.inserted_issues_json),
    updatedIssues: array(row.updated_issues_json),
    auditPassed: Boolean(row.audit_passed),
    fingerprintBefore: row.fingerprint_before == null ? null : String(row.fingerprint_before),
    fingerprintAfter: row.fingerprint_after == null ? null : String(row.fingerprint_after),
    eventKey: row.event_key == null ? null : String(row.event_key),
    warnings: array(row.warnings_json),
    error: object(row.error_json),
    metadata: object(row.metadata_json),
  };
}

export function mapDrawIssueEvent(row: Row): DrawIssueEventRecord {
  return {
    id: Number(row.id),
    eventKey: String(row.event_key),
    previousIssue: String(row.previous_issue),
    newIssue: String(row.new_issue),
    historyFingerprint: String(row.history_fingerprint),
    auditReportHash: String(row.audit_report_hash),
    source: String(row.source),
    status: String(row.status),
    syncedAt: iso(row.synced_at),
    consumedAt: nullableIso(row.consumed_at),
    consumerRunId: row.consumer_run_id == null ? null : String(row.consumer_run_id),
    createdAt: iso(row.created_at),
    metadata: object(row.metadata_json),
  };
}
