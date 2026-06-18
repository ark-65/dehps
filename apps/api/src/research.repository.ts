import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import {
  ExperimentDetail,
  ExperimentSummary,
  FeatureDistribution,
  PipelineRunSummary,
  ResearchRepository,
  SsqHistorySummary,
  SyncRunSummary,
  TrainingRoundDetail,
  TrainingRoundListItem,
  SsqHistoryDraw,
  TrainingNextCandidatesPayload,
  TrainingWeightSignalSummary,
  TrainingWeightSignalPoint,
  TrainingWeightSignalSeries,
} from './research.types';

export const CANONICAL_WEIGHT_KDJ_SIGNAL_RUN_ID = 'weight-kdj-recent-1000-v1';

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
      WHERE history_draws >= 100
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
        AND e.history_draws >= 100
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
        label: '和值',
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
        label: '跨度',
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
        label: '奇数个数',
        expression: 'odd_count::text',
        orderExpression: 'odd_count',
      },
      {
        featureKey: 'consecutive_pair_count',
        label: '连号对数',
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

  async listTrainingRounds(limit: number): Promise<TrainingRoundListItem[]> {
    const { rows } = await this.pool.query(
      `
      SELECT run_id, round_index, phase, step, train_mode, train_window, eval_window, top_n,
             as_of_issue, improved, top_100_hits, top_1000_hits, top_10000_hits,
             red5_top_100_hits, red5_top_1000_hits, red5_top_10000_hits,
             median_rank, best_rank, worst_rank, objective_score, created_at
      FROM training_round_results
      ORDER BY created_at DESC, round_index DESC
      LIMIT $1
      `,
      [limit],
    );
    return rows.map((row) => this.trainingRoundListItem(row));
  }

  async getTrainingRoundDetail(runId: string, roundIndex: number): Promise<TrainingRoundDetail | null> {
    const { rows } = await this.pool.query(
      `
      SELECT run_id, round_index, phase, step, train_mode, train_window, eval_window, top_n,
             as_of_issue, history_fingerprint, improved, top_100_hits, top_1000_hits, top_10000_hits,
             red5_top_100_hits, red5_top_1000_hits, red5_top_10000_hits,
             median_rank, best_rank, worst_rank, objective_score, best_config, best_summary,
             top_results, target_results, prefilter, created_at
      FROM training_round_results
      WHERE run_id = $1 AND round_index = $2
      LIMIT 1
      `,
      [runId, roundIndex],
    );
    const row = rows[0];
    if (!row) {
      return null;
    }
    return {
      ...this.trainingRoundListItem(row),
      historyFingerprint: row.history_fingerprint,
      bestConfig: row.best_config ?? {},
      bestSummary: row.best_summary ?? null,
      topResults: Array.isArray(row.top_results) ? row.top_results : [],
      targetResults: Array.isArray(row.target_results) ? row.target_results : [],
      prefilter: row.prefilter ?? null,
    };
  }

  async listTrainingWeightSignals(
    signalRunId: string | null,
    weights: string[],
    limit: number,
  ): Promise<TrainingWeightSignalSeries[]> {
    const tableCheck = await this.pool.query("SELECT to_regclass('public.training_weight_signals') AS table_name");
    if (!tableCheck.rows[0]?.table_name) {
      return [];
    }

    const weightFilter = weights.length ? weights : null;
    const { rows } = await this.pool.query(
      `
      WITH selected_run AS (
        SELECT COALESCE(
          $1::text,
          (
            SELECT signal_run_id
            FROM training_weight_signals
            WHERE signal_run_id = $4
            LIMIT 1
          ),
          (
            SELECT signal_run_id
            FROM training_weight_signals
            ORDER BY created_at DESC, issue DESC
            LIMIT 1
          )
        ) AS signal_run_id
      ),
      ranked_points AS (
        SELECT s.signal_run_id, s.issue, s.draw_date, s.weight_name, s.source,
               s.train_mode, s.train_window, s.eval_window, s.top_n,
               s.base_value, s.close_value, s.issue_low_value, s.issue_high_value,
               s.rolling_low_value, s.rolling_high_value, s.rsv, s.k_value, s.d_value,
               s.j_value, s.recommended_offset, s.best_objective_score, s.objective_delta,
               s.sample_count,
               row_number() OVER (PARTITION BY s.weight_name ORDER BY s.issue DESC) AS row_number
        FROM training_weight_signals s
        JOIN selected_run r ON r.signal_run_id = s.signal_run_id
        WHERE r.signal_run_id IS NOT NULL
          AND ($2::text[] IS NULL OR s.weight_name = ANY($2::text[]))
      )
      SELECT *
      FROM ranked_points
      WHERE row_number <= $3
      ORDER BY weight_name ASC, issue ASC
      `,
      [signalRunId, weightFilter, limit, CANONICAL_WEIGHT_KDJ_SIGNAL_RUN_ID],
    );

    const byWeight = new Map<string, TrainingWeightSignalSeries>();
    for (const row of rows) {
      const weightName = row.weight_name;
      let series = byWeight.get(weightName);
      if (!series) {
        series = {
          signalRunId: row.signal_run_id,
          weightName,
          source: row.source,
          trainMode: row.train_mode,
          trainWindow: Number(row.train_window),
          evalWindow: Number(row.eval_window),
          topN: Number(row.top_n),
          points: [],
        };
      }
      series.points.push(this.trainingWeightSignalPoint(row));
      byWeight.set(weightName, series);
    }
    return [...byWeight.values()];
  }

  async getSsqHistorySummary(): Promise<SsqHistorySummary> {
    const tableCheck = await this.pool.query("SELECT to_regclass('public.ssq_history') AS table_name");
    if (!tableCheck.rows[0]?.table_name) {
      return {
        tablePresent: false,
        totalDraws: 0,
        minDrawDate: null,
        maxDrawDate: null,
        latestIssue: null,
        latestDrawDate: null,
        latestCreatedAt: null,
      };
    }

    const { rows } = await this.pool.query(
      `
      WITH summary AS (
        SELECT count(*)::int AS total_draws,
               min(draw_date) AS min_draw_date,
               max(draw_date) AS max_draw_date
        FROM ssq_history
      ),
      latest AS (
        SELECT issue, draw_date, created_at
        FROM ssq_history
        ORDER BY issue DESC
        LIMIT 1
      )
      SELECT summary.total_draws, summary.min_draw_date, summary.max_draw_date,
             latest.issue, latest.draw_date AS latest_draw_date, latest.created_at AS latest_created_at
      FROM summary
      LEFT JOIN latest ON true
      `,
    );
    const row = rows[0] ?? {};
    return {
      tablePresent: true,
      totalDraws: Number(row.total_draws ?? 0),
      minDrawDate: this.dateOnlyValue(row.min_draw_date),
      maxDrawDate: this.dateOnlyValue(row.max_draw_date),
      latestIssue: row.issue ?? null,
      latestDrawDate: this.dateOnlyValue(row.latest_draw_date),
      latestCreatedAt: row.latest_created_at ? row.latest_created_at.toISOString() : null,
    };
  }

  async listSsqHistoryDraws(): Promise<SsqHistoryDraw[]> {
    const tableCheck = await this.pool.query("SELECT to_regclass('public.ssq_history') AS table_name");
    if (!tableCheck.rows[0]?.table_name) {
      return [];
    }

    const { rows } = await this.pool.query(
      `
      SELECT issue, draw_date, red_numbers
      FROM ssq_history
      ORDER BY issue ASC
      `,
    );
    return rows.map((row) => ({
      issue: row.issue,
      drawDate: this.dateOnlyValue(row.draw_date),
      redNumbers: Array.isArray(row.red_numbers) ? row.red_numbers.map((value: unknown) => Number(value)) : [],
    }));
  }

  async getTrainingWeightSignalSummary(): Promise<TrainingWeightSignalSummary> {
    const tableCheck = await this.pool.query("SELECT to_regclass('public.training_weight_signals') AS table_name");
    if (!tableCheck.rows[0]?.table_name) {
      return {
        tablePresent: false,
        totalRows: 0,
        latestSignalRunId: null,
        latestIssue: null,
        latestDrawDate: null,
        latestCreatedAt: null,
        weights: [],
      };
    }

    const [summaryResult, weightsResult] = await Promise.all([
      this.pool.query(
        `
        WITH summary AS (
          SELECT count(*)::int AS total_rows
          FROM training_weight_signals
        ),
        latest AS (
          SELECT signal_run_id, issue, draw_date, created_at
          FROM training_weight_signals
          ORDER BY created_at DESC, issue DESC
          LIMIT 1
        )
        SELECT summary.total_rows, latest.signal_run_id, latest.issue,
               latest.draw_date, latest.created_at
        FROM summary
        LEFT JOIN latest ON true
        `,
      ),
      this.pool.query(
        `
        SELECT DISTINCT weight_name
        FROM training_weight_signals
        ORDER BY weight_name ASC
        LIMIT 50
        `,
      ),
    ]);
    const row = summaryResult.rows[0] ?? {};
    return {
      tablePresent: true,
      totalRows: Number(row.total_rows ?? 0),
      latestSignalRunId: row.signal_run_id ?? null,
      latestIssue: row.issue ?? null,
      latestDrawDate: this.dateOnlyValue(row.draw_date),
      latestCreatedAt: row.created_at ? row.created_at.toISOString() : null,
      weights: weightsResult.rows.map((weightRow) => weightRow.weight_name).filter(Boolean),
    };
  }

  async getTrainingNextCandidates(limit: number): Promise<TrainingNextCandidatesPayload> {
    const empty = (): TrainingNextCandidatesPayload => ({
      status: 'empty',
      snapshotKey: null,
      runId: null,
      sourceRoundIndex: null,
      asOfIssue: null,
      nextIssue: null,
      nextDrawDate: null,
      trainMode: null,
      trainWindow: null,
      evalWindow: null,
      topN: null,
      historyFingerprint: null,
      configHash: null,
      config: {},
      generatedAt: null,
      totalCount: 0,
      candidates: [],
      guardrail: '历史响应面候选清单，不代表预测能力或概率优势。',
    });
    const tableCheck = await this.pool.query("SELECT to_regclass('public.training_next_candidates_current') AS table_name");
    if (!tableCheck.rows[0]?.table_name) {
      return empty();
    }

    const countResult = await this.pool.query('SELECT count(*)::int AS total_count FROM training_next_candidates_current');
    const totalCount = Number(countResult.rows[0]?.total_count ?? 0);
    if (totalCount === 0) {
      return empty();
    }

    const { rows } = await this.pool.query(
      `
      SELECT snapshot_key, run_id, source_round_index, as_of_issue, next_issue, next_draw_date,
             train_mode, train_window, eval_window, top_n, history_fingerprint, config_hash,
             config, rank, red_numbers, score, generated_at
      FROM training_next_candidates_current
      ORDER BY rank ASC
      LIMIT $1
      `,
      [limit],
    );
    const first = rows[0];
    return {
      status: 'ready',
      snapshotKey: first.snapshot_key,
      runId: first.run_id,
      sourceRoundIndex: first.source_round_index === null ? null : Number(first.source_round_index),
      asOfIssue: first.as_of_issue,
      nextIssue: first.next_issue,
      nextDrawDate: this.dateOnlyValue(first.next_draw_date),
      trainMode: first.train_mode,
      trainWindow: Number(first.train_window),
      evalWindow: Number(first.eval_window),
      topN: Number(first.top_n),
      historyFingerprint: first.history_fingerprint,
      configHash: first.config_hash,
      config: this.numericRecordValue(first.config),
      generatedAt: first.generated_at instanceof Date ? first.generated_at.toISOString() : first.generated_at ? String(first.generated_at) : null,
      totalCount,
      candidates: rows.map((row) => ({
        rank: Number(row.rank),
        redNumbers: Array.isArray(row.red_numbers) ? row.red_numbers.map((value: unknown) => Number(value)) : [],
        score: Number(row.score),
      })),
      guardrail: '历史响应面候选清单，不代表预测能力或概率优势。',
    };
  }

  private trainingRoundListItem(row: Record<string, any>): TrainingRoundListItem {
    return {
      runId: row.run_id,
      roundIndex: Number(row.round_index),
      phase: row.phase,
      step: Number(row.step),
      trainMode: row.train_mode,
      trainWindow: Number(row.train_window),
      evalWindow: Number(row.eval_window),
      topN: Number(row.top_n),
      asOfIssue: row.as_of_issue,
      improved: Boolean(row.improved),
      top100Hits: Number(row.top_100_hits),
      top1000Hits: Number(row.top_1000_hits),
      top10000Hits: Number(row.top_10000_hits),
      red5Top100Hits: Number(row.red5_top_100_hits),
      red5Top1000Hits: Number(row.red5_top_1000_hits),
      red5Top10000Hits: Number(row.red5_top_10000_hits),
      medianRank: row.median_rank === null ? null : Number(row.median_rank),
      bestRank: row.best_rank === null ? null : Number(row.best_rank),
      worstRank: row.worst_rank === null ? null : Number(row.worst_rank),
      objectiveScore: row.objective_score === null ? null : Number(row.objective_score),
      createdAt: row.created_at.toISOString(),
    };
  }

  private trainingWeightSignalPoint(row: Record<string, any>): TrainingWeightSignalPoint {
    return {
      issue: row.issue,
      drawDate: this.dateOnlyValue(row.draw_date),
      baseValue: Number(row.base_value),
      closeValue: Number(row.close_value),
      issueLowValue: Number(row.issue_low_value),
      issueHighValue: Number(row.issue_high_value),
      rollingLowValue: Number(row.rolling_low_value),
      rollingHighValue: Number(row.rolling_high_value),
      rsv: Number(row.rsv),
      kValue: Number(row.k_value),
      dValue: Number(row.d_value),
      jValue: Number(row.j_value),
      recommendedOffset: Number(row.recommended_offset),
      bestObjectiveScore: Number(row.best_objective_score),
      objectiveDelta: Number(row.objective_delta),
      sampleCount: Number(row.sample_count),
    };
  }

  private dateOnlyValue(value: unknown): string | null {
    if (value instanceof Date) {
      const year = value.getFullYear();
      const month = String(value.getMonth() + 1).padStart(2, '0');
      const day = String(value.getDate()).padStart(2, '0');
      return `${year}-${month}-${day}`;
    }
    return value ? String(value).slice(0, 10) : null;
  }

  private numericRecordValue(value: unknown): Record<string, number> {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      return {};
    }
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .map(([key, rawValue]) => [key, Number(rawValue)] as const)
        .filter((entry): entry is readonly [string, number] => Number.isFinite(entry[1])),
    );
  }
}
