import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { parseDbPort } from '../config';
import { mapDrawIssueEvent } from '../draw-sync/draw-sync.repository';
import { mapTrainingResumeAttempt } from '../training-resume/training-resume.repository';
import { ForwardStateReadRepository, ForwardStateRecord } from './forward-state.types';

@Injectable()
export class PostgresForwardStateReadRepository implements ForwardStateReadRepository, OnModuleDestroy {
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

  async status(): Promise<ForwardStateRecord> {
    const latestIssue = await this.pool.query(`SELECT max(issue) AS latest_issue FROM ssq_history`);
    const pending = await this.pool.query(
      `SELECT *
       FROM draw_issue_events
       WHERE status IN ('pending', 'failed')
       ORDER BY created_at, id
       LIMIT 1`,
    );
    const consumed = await this.pool.query(
      `SELECT count(*)::int AS count FROM draw_issue_events WHERE status = 'consumed'`,
    );
    const latestAttempt = await this.pool.query(
      `SELECT * FROM training_resume_attempts ORDER BY started_at DESC, id DESC LIMIT 1`,
    );
    return {
      latestIssue: latestIssue.rows[0]?.latest_issue == null ? null : String(latestIssue.rows[0].latest_issue),
      pendingEvent: pending.rows[0] ? mapDrawIssueEvent(pending.rows[0]) : null,
      consumedForwardCount: Number(consumed.rows[0]?.count ?? 0),
      latestTrainingResumeAttempt: latestAttempt.rows[0] ? mapTrainingResumeAttempt(latestAttempt.rows[0]) : null,
    };
  }
}
