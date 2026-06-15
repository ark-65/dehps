import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import {
  ExperimentSummary,
  PipelineRunSummary,
  ResearchRepository,
  SyncRunSummary,
} from './research.types';

@Injectable()
export class PostgresResearchRepository implements ResearchRepository, OnModuleDestroy {
  private readonly pool = new Pool({
    host: process.env.DB_HOST ?? 'localhost',
    port: Number(process.env.DB_PORT ?? 54329),
    database: process.env.DB_NAME ?? 'dehps',
    user: process.env.DB_USER ?? 'dehps',
    password: process.env.DB_PASSWORD ?? 'dehps_password',
  });

  async onModuleDestroy() {
    await this.pool.end();
  }

  async listExperiments(limit: number): Promise<ExperimentSummary[]> {
    const { rows } = await this.pool.query(
      `
      SELECT experiment_key, strategy_key, total_combinations, kept_combinations,
             keep_rate, history_draws, covered_draws, coverage_rate, lift,
             config, summary, created_at
      FROM dehps_experiments
      ORDER BY created_at DESC
      LIMIT $1
      `,
      [limit],
    );
    return rows.map((row) => ({
      experimentKey: row.experiment_key,
      strategyKey: row.strategy_key,
      totalCombinations: Number(row.total_combinations),
      keptCombinations: Number(row.kept_combinations),
      keepRate: Number(row.keep_rate),
      historyDraws: Number(row.history_draws),
      coveredDraws: Number(row.covered_draws),
      coverageRate: Number(row.coverage_rate),
      lift: Number(row.lift),
      config: row.config ?? {},
      summary: row.summary,
      createdAt: row.created_at.toISOString(),
    }));
  }

  async listPipelineRuns(limit: number): Promise<PipelineRunSummary[]> {
    const { rows } = await this.pool.query(
      `
      SELECT run_key, status, started_at, finished_at, sync_run_key,
             experiment_key, git_commit_sha, error_message
      FROM pipeline_runs
      ORDER BY started_at DESC
      LIMIT $1
      `,
      [limit],
    );
    return rows.map((row) => ({
      runKey: row.run_key,
      status: row.status,
      startedAt: row.started_at.toISOString(),
      finishedAt: row.finished_at ? row.finished_at.toISOString() : null,
      syncRunKey: row.sync_run_key,
      experimentKey: row.experiment_key,
      gitCommitSha: row.git_commit_sha,
      errorMessage: row.error_message,
    }));
  }

  async listSyncRuns(limit: number): Promise<SyncRunSummary[]> {
    const { rows } = await this.pool.query(
      `
      SELECT run_key, source, status, started_at, finished_at,
             fetched_count, inserted_count, updated_count, skipped_count,
             conflict_count, error_message
      FROM ssq_sync_runs
      ORDER BY started_at DESC
      LIMIT $1
      `,
      [limit],
    );
    return rows.map((row) => ({
      runKey: row.run_key,
      source: row.source,
      status: row.status,
      startedAt: row.started_at.toISOString(),
      finishedAt: row.finished_at ? row.finished_at.toISOString() : null,
      fetchedCount: Number(row.fetched_count),
      insertedCount: Number(row.inserted_count),
      updatedCount: Number(row.updated_count),
      skippedCount: Number(row.skipped_count),
      conflictCount: Number(row.conflict_count),
      errorMessage: row.error_message,
    }));
  }
}
