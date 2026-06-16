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
      run_key: this.stringValue(row.run_key) ?? '',
      reward: this.rewardSummary({
        top100Hits,
        top1000Hits,
        top10000Hits,
        medianRank,
        worstRank,
        universeSize,
      }),
    };
  }

  private rewardSummary({
    top100Hits,
    top1000Hits,
    top10000Hits,
    medianRank,
    worstRank,
    universeSize,
  }: {
    top100Hits: number;
    top1000Hits: number;
    top10000Hits: number;
    medianRank: number;
    worstRank: number;
    universeSize: number | null;
  }) {
    const safeUniverse = universeSize && universeSize > 0 ? universeSize : 1_107_568;
    const hitReward = top100Hits * TOP_100_REWARD + top1000Hits * TOP_1000_REWARD + top10000Hits * TOP_10000_REWARD;
    const rankPenalty = medianRank / safeUniverse + worstRank / safeUniverse / 4;
    return {
      hitReward: Number(hitReward.toFixed(6)),
      rankPenalty: Number(rankPenalty.toFixed(6)),
      objectiveScore: Number((hitReward - rankPenalty).toFixed(6)),
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
