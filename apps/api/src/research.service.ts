import { Inject, Injectable } from '@nestjs/common';
import { constants as fsConstants } from 'node:fs';
import { access, readFile, readdir, stat } from 'node:fs/promises';
import path from 'node:path';
import {
  DashboardPayload,
  ExperimentDetail,
  ExperimentSummary,
  FeatureDistribution,
  PipelineRunSummary,
  ResearchRepository,
  SyncRunSummary,
  TrainingProgress,
  TrainingResult,
  TrainingRoundSummary,
  TrainingStatusPayload,
} from './research.types';

const DEFAULT_LIMIT = 20;
const DEFAULT_LOG_TAIL_LINES = 80;
const OPTIMIZATION_OUTPUT_DIR = 'data/output/optimization';
const RUNTIME_LOG_DIR = 'runtime/logs';
const TOP_100_REWARD = 1000;
const TOP_1000_REWARD = 100;
const TOP_10000_REWARD = 10;
const RED5_TOP_100_REWARD = 5;
const RED5_TOP_1000_REWARD = 1;
const RED5_TOP_10000_REWARD = 0.2;
const RANK_TOP_50000_REWARD = 0.04;
const RANK_TOP_100000_REWARD = 0.02;
const RANK_TOP_250000_REWARD = 0.01;
const RANK_TOP_500000_REWARD = 0.005;
const WORST_RANK_REWARD = 3;
const MEDIAN_RANK_REWARD = 2;
const TAIL_OVER_750000_PENALTY = 0.15;
const TAIL_OVER_900000_PENALTY = 0.5;
const TAIL_OVER_1000000_PENALTY = 1.25;
const WORST_RANK_PENALTY_WEIGHT = 12;
const P95_RANK_PENALTY_WEIGHT = 6;
const MEDIAN_RANK_PENALTY_WEIGHT = 2;

@Injectable()
export class ResearchService {
  constructor(@Inject('ResearchRepository') private readonly repository: ResearchRepository) {}

  health() {
    return {
      status: 'ok',
      service: 'dehps-api',
      mode: 'read-only',
    };
  }

  listExperiments(limit = DEFAULT_LIMIT): Promise<ExperimentSummary[]> {
    return this.repository.listExperiments(this.normalizeLimit(limit));
  }

  getExperimentDetail(experimentKey: string): Promise<ExperimentDetail | null> {
    return this.repository.getExperimentDetail(experimentKey.trim());
  }

  listPipelineRuns(limit = DEFAULT_LIMIT): Promise<PipelineRunSummary[]> {
    return this.repository.listPipelineRuns(this.normalizeLimit(limit));
  }

  listSyncRuns(limit = DEFAULT_LIMIT): Promise<SyncRunSummary[]> {
    return this.repository.listSyncRuns(this.normalizeLimit(limit));
  }

  listFeatureDistributions(): Promise<FeatureDistribution[]> {
    return this.repository.listFeatureDistributions();
  }

  async trainingStatus(tailLines = DEFAULT_LOG_TAIL_LINES): Promise<TrainingStatusPayload> {
    const root = this.repoRoot();
    const normalizedTailLines = this.normalizeTailLines(tailLines);
    const optimizationDir = path.join(root, OPTIMIZATION_OUTPUT_DIR);
    const logDir = path.join(root, RUNTIME_LOG_DIR);
    const statusFile = await this.findLatestFile(optimizationDir, 'training-supervisor-', '.json');
    const rawStatus = statusFile ? await this.readJsonObject(statusFile) : null;
    const runId = this.stringValue(rawStatus?.run_id);
    const reportFile = this.stringValue(rawStatus?.report_path) ?? this.deriveReportPath(statusFile);
    const logFile =
      (runId ? await this.firstExistingPath(path.join(logDir, `training-supervisor-${runId}.log`)) : null) ??
      (await this.findLatestFile(logDir, 'training-supervisor-', '.log'));
    const logTail = logFile ? await this.readTailLines(logFile, normalizedTailLines) : [];
    const latestProgress = this.parseLatestProgress(logTail);
    const serviceUnit = await this.readOptionalText(path.join(logDir, 'training-supervisor.unit'));
    const universeSize = this.numberValue(rawStatus?.universe_size);
    const rounds = this.roundsValue(rawStatus?.rounds, universeSize);
    const best = this.resultValue(rawStatus?.best, universeSize);
    const pid = this.numberValue(rawStatus?.pid);
    const processAlive = pid === null ? null : this.isProcessAlive(pid);
    const status = this.stringValue(rawStatus?.status) ?? 'not_started';
    const active = status === 'running' && processAlive !== false;

    return {
      status,
      active,
      processAlive,
      runId,
      startedAt: this.stringValue(rawStatus?.started_at),
      updatedAt: this.stringValue(rawStatus?.updated_at),
      deadline: this.stringValue(rawStatus?.deadline),
      pid,
      historyScope: this.stringValue(rawStatus?.history_scope),
      regimeYears: this.numberValue(rawStatus?.regime_years),
      regimeStartDate: this.stringValue(rawStatus?.regime_start_date),
      trainMode: this.stringValue(rawStatus?.train_mode),
      trainWindow: this.numberValue(rawStatus?.train_window),
      evalWindow: this.numberValue(rawStatus?.eval_window),
      topN: this.numberValue(rawStatus?.top_n),
      workers: this.numberValue(rawStatus?.workers),
      memoryBudgetGb: this.numberValue(rawStatus?.memory_budget_gb),
      universeSize,
      qianKun: this.qianKunValue(rawStatus?.qian_kun),
      completedRounds: rounds.length,
      rounds,
      latestRound: rounds.at(-1) ?? null,
      recentRounds: rounds.slice(-10).reverse(),
      best,
      latestProgress,
      statusFile,
      reportFile: reportFile ? await this.firstExistingPath(reportFile) : null,
      logFile,
      serviceUnit,
      logTail,
      syncSchedule: {
        timezone: 'Asia/Shanghai',
        cron: '59 23 * * 2,4,0',
        description: '每周二、周四、周日 23:59 自动同步当期开奖数据',
      },
    };
  }

  async dashboard(limit = DEFAULT_LIMIT): Promise<DashboardPayload> {
    const normalizedLimit = this.normalizeLimit(limit);
    const [experiments, pipelineRuns, syncRuns, featureDistributions, trainingStatus] = await Promise.all([
      this.repository.listExperiments(normalizedLimit),
      this.repository.listPipelineRuns(normalizedLimit),
      this.repository.listSyncRuns(normalizedLimit),
      this.repository.listFeatureDistributions(),
      this.trainingStatus(),
    ]);
    return { experiments, pipelineRuns, syncRuns, featureDistributions, trainingStatus };
  }

  private normalizeLimit(limit: number): number {
    if (!Number.isFinite(limit)) {
      return DEFAULT_LIMIT;
    }
    return Math.min(Math.max(Math.trunc(limit), 1), 100);
  }

  private normalizeTailLines(lines: number): number {
    if (!Number.isFinite(lines)) {
      return DEFAULT_LOG_TAIL_LINES;
    }
    return Math.min(Math.max(Math.trunc(lines), 20), 300);
  }

  private repoRoot(): string {
    return process.env.DEHPS_ROOT ? path.resolve(process.env.DEHPS_ROOT) : path.resolve(__dirname, '../../..');
  }

  private async findLatestFile(directory: string, prefix: string, suffix: string): Promise<string | null> {
    try {
      const entries = await readdir(directory, { withFileTypes: true });
      const candidates = await Promise.all(
        entries
          .filter((entry) => entry.isFile() && entry.name.startsWith(prefix) && entry.name.endsWith(suffix))
          .map(async (entry) => {
            const filePath = path.join(directory, entry.name);
            const fileStat = await stat(filePath);
            return { filePath, mtimeMs: fileStat.mtimeMs };
          }),
      );
      candidates.sort((left, right) => right.mtimeMs - left.mtimeMs || right.filePath.localeCompare(left.filePath));
      return candidates[0]?.filePath ?? null;
    } catch (error) {
      if (this.isNotFoundError(error)) {
        return null;
      }
      throw error;
    }
  }

  private async firstExistingPath(filePath: string): Promise<string | null> {
    try {
      await access(filePath, fsConstants.R_OK);
      return filePath;
    } catch (error) {
      if (this.isNotFoundError(error)) {
        return null;
      }
      throw error;
    }
  }

  private async readJsonObject(filePath: string): Promise<Record<string, unknown> | null> {
    try {
      const content = await readFile(filePath, 'utf8');
      const parsed: unknown = JSON.parse(content);
      return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? (parsed as Record<string, unknown>) : null;
    } catch (error) {
      if (this.isNotFoundError(error) || error instanceof SyntaxError) {
        return null;
      }
      throw error;
    }
  }

  private async readOptionalText(filePath: string): Promise<string | null> {
    try {
      const content = await readFile(filePath, 'utf8');
      const trimmed = content.trim();
      return trimmed || null;
    } catch (error) {
      if (this.isNotFoundError(error)) {
        return null;
      }
      throw error;
    }
  }

  private async readTailLines(filePath: string, lineCount: number): Promise<string[]> {
    try {
      const content = await readFile(filePath, 'utf8');
      return content.split(/\r?\n/).filter(Boolean).slice(-lineCount);
    } catch (error) {
      if (this.isNotFoundError(error)) {
        return [];
      }
      throw error;
    }
  }

  private deriveReportPath(statusFile: string | null): string | null {
    return statusFile ? statusFile.replace(/\.json$/, '.md') : null;
  }

  private parseLatestProgress(lines: string[]): TrainingProgress | null {
    const progressPattern =
      /^\[supervisor\]\s+(\S+)\s+round=(\d+)\s+target=(\d+)\/(\d+)\s+issue=(\d+)\s+train_draws=(\d+)\s+elapsed=([\d.]+)s$/;
    for (const line of [...lines].reverse()) {
      const match = progressPattern.exec(line);
      if (!match) {
        continue;
      }
      return {
        loggedAt: match[1],
        round: Number(match[2]),
        targetIndex: Number(match[3]),
        targetTotal: Number(match[4]),
        issue: match[5],
        trainDraws: Number(match[6]),
        elapsedSeconds: Number(match[7]),
      };
    }
    return null;
  }

  private roundsValue(value: unknown, universeSize: number | null): TrainingRoundSummary[] {
    if (!Array.isArray(value)) {
      return [];
    }
    return value
      .map((item) => this.roundValue(item, universeSize))
      .filter((item): item is TrainingRoundSummary => item !== null);
  }

  private roundValue(value: unknown, universeSize: number | null): TrainingRoundSummary | null {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      return null;
    }
    const row = value as Record<string, unknown>;
    const round = this.numberValue(row.round);
    const step = this.numberValue(row.step);
    const configCount = this.numberValue(row.config_count);
    if (round === null || step === null || configCount === null) {
      return null;
    }
    return {
      round,
      phase: this.stringValue(row.phase) ?? 'unknown',
      step,
      config_count: configCount,
      improved: Boolean(row.improved),
      best: this.resultValue(row.best, universeSize),
      topResults: this.resultsValue(row.top_results, universeSize),
    };
  }

  private resultsValue(value: unknown, universeSize: number | null): TrainingResult[] {
    if (!Array.isArray(value)) {
      return [];
    }
    return value
      .map((item) => this.resultValue(item, universeSize))
      .filter((item): item is TrainingResult => item !== null);
  }

  private resultValue(value: unknown, universeSize: number | null): TrainingResult | null {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      return null;
    }
    const row = value as Record<string, unknown>;
    const evaluatedDraws = this.numberValue(row.evaluated_draws);
    const top100Hits = this.numberValue(row.top_100_hits);
    const top1000Hits = this.numberValue(row.top_1000_hits);
    const top10000Hits = this.numberValue(row.top_10000_hits);
    const medianRank = this.numberValue(row.median_rank);
    const bestRank = this.numberValue(row.best_rank);
    const worstRank = this.numberValue(row.worst_rank);
    const red5 = this.redFiveValue(row.red5);
    const rankQuality = this.rankQualityValue(row.rank_quality, {
      medianRank,
      worstRank,
      universeSize,
    });
    if (
      evaluatedDraws === null ||
      top100Hits === null ||
      top1000Hits === null ||
      top10000Hits === null ||
      medianRank === null ||
      bestRank === null ||
      worstRank === null
    ) {
      return null;
    }
    return {
      config: this.numericRecordValue(row.config),
      as_of_issue: this.stringValue(row.as_of_issue) ?? '',
      history_fingerprint: this.stringValue(row.history_fingerprint) ?? '',
      config_hash: this.stringValue(row.config_hash) ?? '',
      evaluated_draws: evaluatedDraws,
      top_100_hits: top100Hits,
      top_1000_hits: top1000Hits,
      top_10000_hits: top10000Hits,
      median_rank: medianRank,
      best_rank: bestRank,
      worst_rank: worstRank,
      red5,
      rank_quality: rankQuality,
      run_key: this.stringValue(row.run_key) ?? '',
      reward: this.rewardSummary({
        top100Hits,
        top1000Hits,
        top10000Hits,
        red5,
        rankQuality,
        medianRank,
        worstRank,
        universeSize,
      }),
    };
  }

  private redFiveValue(value: unknown) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      return this.emptyRedFive();
    }
    const row = value as Record<string, unknown>;
    return {
      top_100_hits: this.numberValue(row.top_100_hits) ?? 0,
      top_1000_hits: this.numberValue(row.top_1000_hits) ?? 0,
      top_10000_hits: this.numberValue(row.top_10000_hits) ?? 0,
      median_rank: this.numberValue(row.median_rank),
      best_rank: this.numberValue(row.best_rank),
      missing_counts: this.numericRecordValue(row.missing_counts),
      extra_counts: this.numericRecordValue(row.extra_counts),
      pairs: this.redFivePairsValue(row.pairs),
      examples: this.redFiveExamplesValue(row.examples),
    };
  }

  private qianKunValue(value: unknown) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      return {
        total_draws: 0,
        recent_window: 0,
        latest_issue: '',
        latest_numbers: [],
        latest_pattern: '',
        latest_label: '',
        latest_lines: [],
        qian_count: 0,
        kun_count: 0,
        patterns: [],
      };
    }
    const row = value as Record<string, unknown>;
    return {
      total_draws: this.numberValue(row.total_draws) ?? 0,
      recent_window: this.numberValue(row.recent_window) ?? 0,
      latest_issue: this.stringValue(row.latest_issue) ?? '',
      latest_numbers: this.numberArrayValue(row.latest_numbers),
      latest_pattern: this.stringValue(row.latest_pattern) ?? '',
      latest_label: this.stringValue(row.latest_label) ?? '',
      latest_lines: this.stringArrayValue(row.latest_lines),
      qian_count: this.numberValue(row.qian_count) ?? 0,
      kun_count: this.numberValue(row.kun_count) ?? 0,
      patterns: this.qianKunPatternsValue(row.patterns),
    };
  }

  private qianKunPatternsValue(value: unknown) {
    if (!Array.isArray(value)) {
      return [];
    }
    return value
      .map((item) => {
        if (!item || typeof item !== 'object' || Array.isArray(item)) {
          return null;
        }
        const row = item as Record<string, unknown>;
        const pattern = this.stringValue(row.pattern);
        if (!pattern) {
          return null;
        }
        return {
          pattern,
          label: this.stringValue(row.label) ?? pattern,
          lines: this.stringArrayValue(row.lines),
          count: this.numberValue(row.count) ?? 0,
          rate: this.numberValue(row.rate) ?? 0,
          recent_count: this.numberValue(row.recent_count) ?? 0,
          recent_rate: this.numberValue(row.recent_rate) ?? 0,
        };
      })
      .filter(
        (item): item is {
          pattern: string;
          label: string;
          lines: string[];
          count: number;
          rate: number;
          recent_count: number;
          recent_rate: number;
        } => item !== null,
      );
  }

  private emptyRedFive() {
    return {
      top_100_hits: 0,
      top_1000_hits: 0,
      top_10000_hits: 0,
      median_rank: null,
      best_rank: null,
      missing_counts: {},
      extra_counts: {},
      pairs: [],
      examples: [],
    };
  }

  private redFivePairsValue(value: unknown) {
    if (!Array.isArray(value)) {
      return [];
    }
    return value
      .map((item) => {
        if (!item || typeof item !== 'object' || Array.isArray(item)) {
          return null;
        }
        const row = item as Record<string, unknown>;
        const missingNumber = this.numberValue(row.missing_number);
        const extraNumber = this.numberValue(row.extra_number);
        const count = this.numberValue(row.count);
        return missingNumber === null || extraNumber === null || count === null
          ? null
          : { missing_number: missingNumber, extra_number: extraNumber, count };
      })
      .filter((item): item is { missing_number: number; extra_number: number; count: number } => item !== null);
  }

  private redFiveExamplesValue(value: unknown) {
    if (!Array.isArray(value)) {
      return [];
    }
    return value
      .map((item) => {
        if (!item || typeof item !== 'object' || Array.isArray(item)) {
          return null;
        }
        const row = item as Record<string, unknown>;
        const issue = this.stringValue(row.issue);
        const rank = this.numberValue(row.rank);
        const score = this.numberValue(row.score);
        const missingNumber = this.numberValue(row.missing_number);
        const extraNumber = this.numberValue(row.extra_number);
        const numbers = this.numberArrayValue(row.numbers);
        return issue === null || rank === null || missingNumber === null || extraNumber === null
          ? null
          : { issue, rank, score, numbers, missing_number: missingNumber, extra_number: extraNumber };
      })
      .filter(
        (item): item is {
          issue: string;
          rank: number;
          score: number | null;
          numbers: number[];
          missing_number: number;
          extra_number: number;
        } => item !== null,
      );
  }

  private rankQualityValue(
    value: unknown,
    fallback: { medianRank: number | null; worstRank: number | null; universeSize: number | null },
  ) {
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      const row = value as Record<string, unknown>;
      const p95Rank = this.numberValue(row.p95_rank) ?? fallback.worstRank;
      const tailOver750000 =
        this.numberValue(row.tail_over_750000_count) ??
        (fallback.worstRank !== null && fallback.worstRank > 750_000 ? 1 : 0);
      const tailOver900000 =
        this.numberValue(row.tail_over_900000_count) ??
        (fallback.worstRank !== null && fallback.worstRank > 900_000 ? 1 : 0);
      const tailOver1000000 =
        this.numberValue(row.tail_over_1000000_count) ??
        (fallback.worstRank !== null && fallback.worstRank > 1_000_000 ? 1 : 0);
      const parsedTailRiskPenalty = this.numberValue(row.tail_risk_penalty);
      return {
        top_50000_hits: this.numberValue(row.top_50000_hits) ?? 0,
        top_100000_hits: this.numberValue(row.top_100000_hits) ?? 0,
        top_250000_hits: this.numberValue(row.top_250000_hits) ?? 0,
        top_500000_hits: this.numberValue(row.top_500000_hits) ?? 0,
        p90_rank: this.numberValue(row.p90_rank) ?? fallback.medianRank,
        p95_rank: p95Rank,
        tail_over_750000_count: tailOver750000,
        tail_over_900000_count: tailOver900000,
        tail_over_1000000_count: tailOver1000000,
        worst_rank_reward: this.numberValue(row.worst_rank_reward) ?? 0,
        median_rank_reward: this.numberValue(row.median_rank_reward) ?? 0,
        band_reward: this.numberValue(row.band_reward) ?? 0,
        tail_risk_penalty: parsedTailRiskPenalty && parsedTailRiskPenalty > 0
          ? parsedTailRiskPenalty
          : this.tailRiskPenalty({
            medianRank: fallback.medianRank,
            worstRank: fallback.worstRank,
            p95Rank,
            tailOver750000,
            tailOver900000,
            tailOver1000000,
            universeSize: fallback.universeSize,
          }),
        reward: this.numberValue(row.reward) ?? 0,
      };
    }
    const safeUniverse = fallback.universeSize && fallback.universeSize > 0 ? fallback.universeSize : 1_107_568;
    const worstRankReward =
      fallback.worstRank === null ? 0 : Math.max(0, 1 - fallback.worstRank / safeUniverse) * WORST_RANK_REWARD;
    const medianRankReward =
      fallback.medianRank === null ? 0 : Math.max(0, 1 - fallback.medianRank / safeUniverse) * MEDIAN_RANK_REWARD;
    return {
      top_50000_hits: 0,
      top_100000_hits: 0,
      top_250000_hits: 0,
      top_500000_hits: 0,
      p90_rank: fallback.medianRank,
      p95_rank: fallback.worstRank,
      tail_over_750000_count: fallback.worstRank !== null && fallback.worstRank > 750_000 ? 1 : 0,
      tail_over_900000_count: fallback.worstRank !== null && fallback.worstRank > 900_000 ? 1 : 0,
      tail_over_1000000_count: fallback.worstRank !== null && fallback.worstRank > 1_000_000 ? 1 : 0,
      worst_rank_reward: Number(worstRankReward.toFixed(6)),
      median_rank_reward: Number(medianRankReward.toFixed(6)),
      band_reward: 0,
      tail_risk_penalty: this.tailRiskPenalty({
        medianRank: fallback.medianRank,
        worstRank: fallback.worstRank,
        p95Rank: fallback.worstRank,
        tailOver750000: fallback.worstRank !== null && fallback.worstRank > 750_000 ? 1 : 0,
        tailOver900000: fallback.worstRank !== null && fallback.worstRank > 900_000 ? 1 : 0,
        tailOver1000000: fallback.worstRank !== null && fallback.worstRank > 1_000_000 ? 1 : 0,
        universeSize: fallback.universeSize,
      }),
      reward: Number((worstRankReward + medianRankReward).toFixed(6)),
    };
  }

  private tailRiskPenalty({
    medianRank,
    worstRank,
    p95Rank,
    tailOver750000,
    tailOver900000,
    tailOver1000000,
    universeSize,
  }: {
    medianRank: number | null;
    worstRank: number | null;
    p95Rank: number | null;
    tailOver750000: number;
    tailOver900000: number;
    tailOver1000000: number;
    universeSize: number | null;
  }) {
    const safeUniverse = universeSize && universeSize > 0 ? universeSize : 1_107_568;
    const normalize = (value: number | null) => Math.min(1, Math.max(0, (value ?? safeUniverse) / safeUniverse));
    const normalizedMedian = normalize(medianRank);
    const normalizedWorst = normalize(worstRank);
    const normalizedP95 = normalize(p95Rank ?? worstRank);
    const countPenalty =
      tailOver750000 * TAIL_OVER_750000_PENALTY +
      tailOver900000 * TAIL_OVER_900000_PENALTY +
      tailOver1000000 * TAIL_OVER_1000000_PENALTY;
    const shapePenalty =
      normalizedWorst ** 2 * WORST_RANK_PENALTY_WEIGHT +
      normalizedP95 ** 2 * P95_RANK_PENALTY_WEIGHT +
      normalizedMedian ** 2 * MEDIAN_RANK_PENALTY_WEIGHT;
    return Number((countPenalty + shapePenalty).toFixed(6));
  }

  private rewardSummary({
    top100Hits,
    top1000Hits,
    top10000Hits,
    red5,
    rankQuality,
    medianRank,
    worstRank,
    universeSize,
  }: {
    top100Hits: number;
    top1000Hits: number;
    top10000Hits: number;
    red5: {
      top_100_hits: number;
      top_1000_hits: number;
      top_10000_hits: number;
    };
    rankQuality: {
      top_50000_hits: number;
      top_100000_hits: number;
      top_250000_hits: number;
      top_500000_hits: number;
      p95_rank: number | null;
      tail_over_750000_count: number;
      tail_over_900000_count: number;
      tail_over_1000000_count: number;
      tail_risk_penalty: number;
      reward: number;
    };
    medianRank: number;
    worstRank: number;
    universeSize: number | null;
  }) {
    const safeUniverse = universeSize && universeSize > 0 ? universeSize : 1_107_568;
    const hitReward = top100Hits * TOP_100_REWARD + top1000Hits * TOP_1000_REWARD + top10000Hits * TOP_10000_REWARD;
    const red5Reward =
      red5.top_100_hits * RED5_TOP_100_REWARD +
      red5.top_1000_hits * RED5_TOP_1000_REWARD +
      red5.top_10000_hits * RED5_TOP_10000_REWARD;
    const rankQualityReward =
      rankQuality.reward ||
      rankQuality.top_50000_hits * RANK_TOP_50000_REWARD +
        rankQuality.top_100000_hits * RANK_TOP_100000_REWARD +
        rankQuality.top_250000_hits * RANK_TOP_250000_REWARD +
        rankQuality.top_500000_hits * RANK_TOP_500000_REWARD;
    const rankPenalty = medianRank / safeUniverse + worstRank / safeUniverse / 4;
    const tailRiskPenalty =
      rankQuality.tail_risk_penalty ||
      this.tailRiskPenalty({
        medianRank,
        worstRank,
        p95Rank: rankQuality.p95_rank,
        tailOver750000: rankQuality.tail_over_750000_count,
        tailOver900000: rankQuality.tail_over_900000_count,
        tailOver1000000: rankQuality.tail_over_1000000_count,
        universeSize,
      });
    return {
      hitReward: Number(hitReward.toFixed(6)),
      red5Reward: Number(red5Reward.toFixed(6)),
      rankQualityReward: Number(rankQualityReward.toFixed(6)),
      rankPenalty: Number(rankPenalty.toFixed(6)),
      tailRiskPenalty: Number(tailRiskPenalty.toFixed(6)),
      objectiveScore: Number((hitReward + red5Reward + rankQualityReward - rankPenalty - tailRiskPenalty).toFixed(6)),
    };
  }

  private numericRecordValue(value: unknown): Record<string, number> {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      return {};
    }
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .map(([key, rawValue]) => [key, this.numberValue(rawValue)] as const)
        .filter((entry): entry is readonly [string, number] => entry[1] !== null),
    );
  }

  private stringValue(value: unknown): string | null {
    return typeof value === 'string' && value.length > 0 ? value : null;
  }

  private numberValue(value: unknown): number | null {
    return typeof value === 'number' && Number.isFinite(value) ? value : null;
  }

  private numberArrayValue(value: unknown): number[] {
    if (!Array.isArray(value)) {
      return [];
    }
    return value
      .map((item) => this.numberValue(item))
      .filter((item): item is number => item !== null);
  }

  private stringArrayValue(value: unknown): string[] {
    if (!Array.isArray(value)) {
      return [];
    }
    return value.filter((item): item is string => typeof item === 'string');
  }

  private isProcessAlive(pid: number): boolean {
    try {
      process.kill(pid, 0);
      return true;
    } catch {
      return false;
    }
  }

  private isNotFoundError(error: unknown): boolean {
    return (
      error instanceof Error &&
      'code' in error &&
      ((error as NodeJS.ErrnoException).code === 'ENOENT' || (error as NodeJS.ErrnoException).code === 'ENOTDIR')
    );
  }
}
