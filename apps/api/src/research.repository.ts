import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import {
  ExperimentDetail,
  ExperimentSummary,
  FeatureDistribution,
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
             hypothesis, keep_rate, history_draws, covered_draws, coverage_rate,
             lift, config, summary, created_at
      FROM dehps_experiments
      ORDER BY created_at DESC
      LIMIT $1
      `,
      [limit],
    );
    return rows.map((row) => ({
      experimentKey: row.experiment_key,
      strategyKey: row.strategy_key,
      hypothesis: row.hypothesis,
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

  async getExperimentDetail(experimentKey: string): Promise<ExperimentDetail | null> {
    const { rows } = await this.pool.query(
      `
      SELECT e.experiment_key, e.strategy_key, e.hypothesis, e.total_combinations,
             e.kept_combinations, e.keep_rate, e.history_draws, e.covered_draws,
             e.coverage_rate, e.lift, e.config, e.summary, e.created_at,
             r.report_markdown, r.created_at AS report_created_at
      FROM dehps_experiments e
      LEFT JOIN LATERAL (
        SELECT report_markdown, created_at
        FROM dehps_experiment_reports
        WHERE experiment_key = e.experiment_key
        ORDER BY created_at DESC
        LIMIT 1
      ) r ON true
      WHERE e.experiment_key = $1
      LIMIT 1
      `,
      [experimentKey],
    );
    const row = rows[0];
    if (!row) {
      return null;
    }
    return {
      experimentKey: row.experiment_key,
      strategyKey: row.strategy_key,
      hypothesis: row.hypothesis,
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
      reportMarkdown: row.report_markdown ?? null,
      reportCreatedAt: row.report_created_at ? row.report_created_at.toISOString() : null,
    };
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

  async listFeatureDistributions(): Promise<FeatureDistribution[]> {
    const definitions = [
      {
        featureKey: 'sum_value',
        label: 'Sum Value',
        expression: `
          CASE
            WHEN sum_value < 70 THEN '<70'
            WHEN sum_value < 90 THEN '70-89'
            WHEN sum_value < 110 THEN '90-109'
            WHEN sum_value < 130 THEN '110-129'
            ELSE '130+'
          END
        `,
        orderExpression: `
          CASE
            WHEN sum_value < 70 THEN 1
            WHEN sum_value < 90 THEN 2
            WHEN sum_value < 110 THEN 3
            WHEN sum_value < 130 THEN 4
            ELSE 5
          END
        `,
      },
      {
        featureKey: 'span_value',
        label: 'Span Value',
        expression: `
          CASE
            WHEN span_value < 12 THEN '<12'
            WHEN span_value < 18 THEN '12-17'
            WHEN span_value < 24 THEN '18-23'
            WHEN span_value < 30 THEN '24-29'
            ELSE '30+'
          END
        `,
        orderExpression: `
          CASE
            WHEN span_value < 12 THEN 1
            WHEN span_value < 18 THEN 2
            WHEN span_value < 24 THEN 3
            WHEN span_value < 30 THEN 4
            ELSE 5
          END
        `,
      },
      {
        featureKey: 'odd_count',
        label: 'Odd Count',
        expression: 'odd_count::text',
        orderExpression: 'odd_count',
      },
      {
        featureKey: 'consecutive_pair_count',
        label: 'Consecutive Pairs',
        expression: 'consecutive_pair_count::text',
        orderExpression: 'consecutive_pair_count',
      },
    ];

    return Promise.all(
      definitions.map(async (definition) => {
        const { rows } = await this.pool.query(
          `
          WITH buckets AS (
            SELECT ${definition.expression} AS label,
                   ${definition.orderExpression} AS bucket_order,
                   count(*)::int AS count
            FROM ssq_red_combinations
            GROUP BY label, bucket_order
          ),
          totals AS (
            SELECT COALESCE(sum(count), 0)::int AS total_count FROM buckets
          )
          SELECT buckets.label,
                 buckets.count,
                 totals.total_count,
                 CASE
                   WHEN totals.total_count = 0 THEN 0
                   ELSE buckets.count::float / totals.total_count
                 END AS rate
          FROM buckets
          CROSS JOIN totals
          ORDER BY buckets.bucket_order
          `,
        );
        const totalCount = rows[0] ? Number(rows[0].total_count) : 0;
        return {
          featureKey: definition.featureKey,
          label: definition.label,
          totalCount,
          bins: rows.map((row) => ({
            label: row.label,
            count: Number(row.count),
            rate: Number(row.rate),
          })),
        };
      }),
    );
  }
}
