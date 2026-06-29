import { Inject, Injectable } from '@nestjs/common';
import { constants as fsConstants } from 'node:fs';
import { access, readFile, readdir, stat } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {
  DashboardPayload,
  ExperimentDetail,
  ExperimentSummary,
  FeatureDistribution,
  PipelineRunSummary,
  ResearchRepository,
  ServiceStatusItem,
  ServiceStatusLevel,
  ServiceStatusPayload,
  ServiceStatusName,
  SsqHistoryDraw,
  SyncRunSummary,
  TrainingAdvisorAdviceRow,
  TrainingAdvisorSource,
  TrainingAdvisorSummary,
  TrainingMatrixCache,
  TrainingNextCandidatesPayload,
  TrainingPrefilterRun,
  TrainingPrefilterStatus,
  TrainingProgress,
  TrainingQianKunSummary,
  TrainingRankMovementSummary,
  TrainingResult,
  TrainingRoundDetail,
  TrainingRoundListItem,
  TrainingRoundSummary,
  TrainingSearchBaseSummary,
  TrainingStatusPayload,
  TrainingTargetResult,
  TrainingWeightSignalSeries,
} from './research.types';

const DEFAULT_LIMIT = 20;
const DEFAULT_LOG_TAIL_LINES = 80;
const DEFAULT_HEAVY_TASK_WORKERS = 16;
const OPTIMIZATION_OUTPUT_DIR = 'data/output/optimization';
const RUNTIME_LOG_DIR = 'runtime/logs';
const HEAVY_JOB_INACTIVE_STATUSES = new Set([
  'released',
  'finished',
  'completed',
  'success',
  'failed',
  'error',
  'cancelled',
  'interrupted',
]);
const SYNC_SCHEDULE = {
  timezone: 'Asia/Shanghai',
  cron: '59 23 * * 2,4,0',
  description: '每周二、周四、周日 23:59 自动同步当期开奖数据',
};
const SYNC_STALE_SECONDS = 4 * 24 * 60 * 60;
const KDJ_STALE_SECONDS = 14 * 24 * 60 * 60;
const TRAINING_STALE_SECONDS = 24 * 60 * 60;
const STATUS_READ_ERROR_KEY = '__dehps_status_read_error';
const TERMINAL_TRAINING_STATUSES = new Set(['completed', 'failed', 'interrupted']);
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
const ADVISOR_SOURCES: readonly TrainingAdvisorSource[] = [
  'weight_kdj_advisor',
  'ridge_kdj_advisor',
  'neural_kdj_advisor',
  'target_weight_inversion_advisor',
];
const HEXAGRAMS_BY_PATTERN: Record<string, { number: number; label: string }> = {
  '111111': { number: 1, label: '乾卦' },
  '000000': { number: 2, label: '坤卦' },
  '100010': { number: 3, label: '屯卦' },
  '010001': { number: 4, label: '蒙卦' },
  '111010': { number: 5, label: '需卦' },
  '010111': { number: 6, label: '讼卦' },
  '010000': { number: 7, label: '师卦' },
  '000010': { number: 8, label: '比卦' },
  '111011': { number: 9, label: '小畜卦' },
  '110111': { number: 10, label: '履卦' },
  '111000': { number: 11, label: '泰卦' },
  '000111': { number: 12, label: '否卦' },
  '101111': { number: 13, label: '同人卦' },
  '111101': { number: 14, label: '大有卦' },
  '001000': { number: 15, label: '谦卦' },
  '000100': { number: 16, label: '豫卦' },
  '100110': { number: 17, label: '随卦' },
  '011001': { number: 18, label: '蛊卦' },
  '110000': { number: 19, label: '临卦' },
  '000011': { number: 20, label: '观卦' },
  '100101': { number: 21, label: '噬嗑卦' },
  '101001': { number: 22, label: '贲卦' },
  '000001': { number: 23, label: '剥卦' },
  '100000': { number: 24, label: '复卦' },
  '100111': { number: 25, label: '无妄卦' },
  '111001': { number: 26, label: '大畜卦' },
  '100001': { number: 27, label: '颐卦' },
  '011110': { number: 28, label: '大过卦' },
  '010010': { number: 29, label: '坎卦' },
  '101101': { number: 30, label: '离卦' },
  '001110': { number: 31, label: '咸卦' },
  '011100': { number: 32, label: '恒卦' },
  '001111': { number: 33, label: '遁卦' },
  '111100': { number: 34, label: '大壮卦' },
  '000101': { number: 35, label: '晋卦' },
  '101000': { number: 36, label: '明夷卦' },
  '101011': { number: 37, label: '家人卦' },
  '110101': { number: 38, label: '睽卦' },
  '001010': { number: 39, label: '蹇卦' },
  '010100': { number: 40, label: '解卦' },
  '110001': { number: 41, label: '损卦' },
  '100011': { number: 42, label: '益卦' },
  '111110': { number: 43, label: '夬卦' },
  '011111': { number: 44, label: '姤卦' },
  '000110': { number: 45, label: '萃卦' },
  '011000': { number: 46, label: '升卦' },
  '010110': { number: 47, label: '困卦' },
  '011010': { number: 48, label: '井卦' },
  '101110': { number: 49, label: '革卦' },
  '011101': { number: 50, label: '鼎卦' },
  '100100': { number: 51, label: '震卦' },
  '001001': { number: 52, label: '艮卦' },
  '001011': { number: 53, label: '渐卦' },
  '110100': { number: 54, label: '归妹卦' },
  '101100': { number: 55, label: '丰卦' },
  '001101': { number: 56, label: '旅卦' },
  '011011': { number: 57, label: '巽卦' },
  '110110': { number: 58, label: '兑卦' },
  '010011': { number: 59, label: '涣卦' },
  '110010': { number: 60, label: '节卦' },
  '110011': { number: 61, label: '中孚卦' },
  '001100': { number: 62, label: '小过卦' },
  '101010': { number: 63, label: '既济卦' },
  '010101': { number: 64, label: '未济卦' },
};
const HEXAGRAM_UNICODE_BASE = 0x4dbf;
const QIAN_PATTERN = '111111';
const KUN_PATTERN = '000000';
const QIAN_KUN_RECENT_WINDOW = 100;
const YANG_LINE = '—';
const YIN_LINE = '- -';

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

  async listTrainingRounds(limit = 50): Promise<TrainingRoundListItem[]> {
    const rounds = await this.repository.listTrainingRounds(this.normalizeLimit(limit));
    return rounds.map((round) => ({
      ...round,
      bestRankQuality: this.rankQualityValue(round.bestRankQuality, {
        medianRank: round.medianRank,
        worstRank: round.worstRank,
        universeSize: 1107568,
      }),
      prefilter: this.prefilterRunValue(round.prefilter),
    }));
  }

  async getTrainingRoundDetail(runId: string, roundIndex: number): Promise<TrainingRoundDetail | null> {
    const normalizedRunId = runId.trim();
    const normalizedRoundIndex = Number.isFinite(roundIndex) ? Math.trunc(roundIndex) : 0;
    if (!normalizedRunId || normalizedRoundIndex < 1) {
      return null;
    }
    const detail = await this.repository.getTrainingRoundDetail(normalizedRunId, normalizedRoundIndex);
    if (!detail) {
      return null;
    }
    const universeSize = 1107568;
    return {
      ...detail,
      bestConfig: this.numericRecordValue(detail.bestConfig),
      bestRankQuality: this.rankQualityValue(detail.bestRankQuality, {
        medianRank: detail.medianRank,
        worstRank: detail.worstRank,
        universeSize,
      }),
      bestSummary: this.resultValue(detail.bestSummary, universeSize),
      topResults: this.resultsValue(detail.topResults, universeSize),
      targetResults: this.targetResultsValue(detail.targetResults),
      prefilter: this.prefilterRunValue(detail.prefilter),
      rankMovement: detail.rankMovement ?? null,
    };
  }

  listTrainingWeightSignals(
    signalRunId: string | undefined,
    weights: string | undefined,
    limit = 1000,
  ): Promise<TrainingWeightSignalSeries[]> {
    const normalizedRunId = signalRunId?.trim() || null;
    const normalizedWeights = (weights ?? '')
      .split(',')
      .map((weight) => weight.trim())
      .filter((weight) => /^[a-z0-9_]+$/i.test(weight));
    return this.repository.listTrainingWeightSignals(normalizedRunId, [...new Set(normalizedWeights)], this.normalizeSignalLimit(limit));
  }

  getTrainingNextCandidates(limit = 10000): Promise<TrainingNextCandidatesPayload> {
    return this.repository.getTrainingNextCandidates(this.normalizeCandidateLimit(limit));
  }

  async trainingStatus(tailLines = DEFAULT_LOG_TAIL_LINES): Promise<TrainingStatusPayload> {
    const root = this.repoRoot();
    const normalizedTailLines = this.normalizeTailLines(tailLines);
    const optimizationDir = path.join(root, OPTIMIZATION_OUTPUT_DIR);
    const logDir = path.join(root, RUNTIME_LOG_DIR);
    const latestStatusFile = await this.findLatestFile(optimizationDir, 'training-supervisor-', '.json');
    const latestRawStatus = latestStatusFile ? await this.readJsonObject(latestStatusFile) : null;
    const latestStatusRunId = this.stringValue(latestRawStatus?.run_id);
    const latestStatusText = this.stringValue(latestRawStatus?.status);
    const latestStatusPid = this.numberValue(latestRawStatus?.pid);
    const latestStatusProcessAlive = latestStatusPid === null ? null : this.isProcessAlive(latestStatusPid);
    const latestLogFile = await this.findLatestFile(logDir, 'training-supervisor-', '.log');
    const dbRounds = await this.repository.listTrainingRounds(100).catch(() => []);
    const dbRunId = dbRounds[0]?.runId ?? null;
    const latestStatusIsLiveDifferentRun =
      dbRunId !== null &&
      latestStatusRunId !== null &&
      latestStatusRunId !== dbRunId &&
      latestStatusText === 'running' &&
      latestStatusProcessAlive !== false;
    if (dbRounds.length > 0 && !latestStatusIsLiveDifferentRun) {
      const runId = dbRounds[0].runId;
      const runRounds = dbRounds
        .filter((round) => round.runId === runId)
        .sort((left, right) => left.roundIndex - right.roundIndex);
      const latestRoundItem = runRounds.at(-1) ?? null;
      const bestRoundItem = [...runRounds].reverse().find((round) => round.improved) ?? latestRoundItem;
      const bestDetail = bestRoundItem
        ? await this.repository.getTrainingRoundDetail(bestRoundItem.runId, bestRoundItem.roundIndex).catch(() => null)
        : null;
      const latestDetail = latestRoundItem
        ? await this.repository.getTrainingRoundDetail(latestRoundItem.runId, latestRoundItem.roundIndex).catch(() => null)
        : null;
      const runStatusFile = runId
        ? await this.firstExistingPath(path.join(optimizationDir, `training-supervisor-${runId}.json`))
        : null;
      const statusFile = runStatusFile ?? (latestStatusRunId === runId ? latestStatusFile : null);
      const rawStatus =
        statusFile === latestStatusFile ? latestRawStatus : statusFile ? await this.readJsonObject(statusFile) : null;
      const rawStatusText = this.stringValue(rawStatus?.status);
      const rawProgress = this.progressValue(rawStatus?.latest_progress);
      const pid = this.numberValue(rawStatus?.pid);
      const processAlive = pid === null ? null : this.isProcessAlive(pid);
      const runLogFile = runId ? await this.firstExistingPath(path.join(logDir, `training-supervisor-${runId}.log`)) : null;
      const logFile = runLogFile ?? (latestStatusRunId === runId ? latestLogFile : null);
      const statusReadError = this.statusReadError(rawStatus);
      const logTail = this.appendStatusReadError(
        logFile ? await this.readTailLines(logFile, normalizedTailLines) : [],
        statusReadError,
        normalizedTailLines,
      );
      const latestProgress = rawProgress ?? this.parseLatestProgress(logTail);
      const serviceUnit = await this.readOptionalText(path.join(logDir, 'training-supervisor.unit'));
      const latestRound = latestRoundItem ? this.roundSummaryFromListItem(latestRoundItem, latestDetail) : null;
      const rounds = runRounds.map((round) =>
        this.roundSummaryFromListItem(round, round.roundIndex === latestRoundItem?.roundIndex ? latestDetail : null),
      );
      const completedRounds = latestRoundItem?.roundIndex ?? 0;
      const progressActive = latestProgress
        ? latestProgress.round > completedRounds || latestProgress.targetIndex < latestProgress.targetTotal
        : false;
      const active = statusReadError ? false : rawStatusText === 'running' && processAlive !== false ? true : progressActive;
      const latestPrefilter = this.prefilterRunValue(latestDetail?.prefilter ?? latestRoundItem?.prefilter);
      const advisorSummaries = this.advisorSummariesValue(null, latestDetail?.prefilter ?? latestRoundItem?.prefilter);
      const qianKun = await this.qianKunFromStatusOrHistory(null);

      return {
        status: statusReadError ? 'failed' : active ? 'running' : rawStatusText ?? 'completed',
        active,
        processAlive,
        runId,
        startedAt: this.stringValue(rawStatus?.started_at) ?? runRounds[0]?.createdAt ?? null,
        updatedAt: this.stringValue(rawStatus?.updated_at) ?? latestRoundItem?.createdAt ?? null,
        deadline: this.stringValue(rawStatus?.deadline),
        pid,
        historyScope: this.stringValue(rawStatus?.history_scope),
        regimeYears: this.numberValue(rawStatus?.regime_years),
        regimeStartDate: this.stringValue(rawStatus?.regime_start_date),
        trainMode: latestRoundItem?.trainMode ?? null,
        trainWindow: latestRoundItem?.trainWindow ?? null,
        evalWindow: latestRoundItem?.evalWindow ?? null,
        topN: latestRoundItem?.topN ?? null,
        workers: this.numberValue(rawStatus?.workers),
        memoryBudgetGb: this.numberValue(rawStatus?.memory_budget_gb),
        universeSize: 1107568,
        matrixBackend: this.stringValue(rawStatus?.matrix_backend),
        featureMatrixCache: this.matrixCacheValue(rawStatus?.feature_matrix_cache),
        red5RankMode: this.stringValue(rawStatus?.red5_rank_mode),
        prefilter: latestPrefilter ? { mode: latestPrefilter.mode, description: null, latest: latestPrefilter } : null,
        advisorSummaries,
        qianKun,
        completedRounds,
        rounds,
        latestRound,
        recentRounds: rounds.slice(-10).reverse(),
        best: this.resultValue(bestDetail?.bestSummary, 1107568) ?? (bestRoundItem ? this.resultFromRoundListItem(bestRoundItem) : null),
        latestProgress,
        statusFile,
        reportFile: this.stringValue(rawStatus?.report_path) ?? (statusFile ? this.deriveReportPath(statusFile) : null),
        logFile,
        serviceUnit,
        logTail,
        syncSchedule: SYNC_SCHEDULE,
      };
    }

    const statusFile = latestStatusFile;
    const rawStatus = latestRawStatus;
    const runId = this.stringValue(rawStatus?.run_id);
    const reportFile = this.stringValue(rawStatus?.report_path) ?? this.deriveReportPath(statusFile);
    const logFile =
      (runId ? await this.firstExistingPath(path.join(logDir, `training-supervisor-${runId}.log`)) : null) ??
      latestLogFile;
    const statusReadError = this.statusReadError(rawStatus);
    const logTail = this.appendStatusReadError(
      logFile ? await this.readTailLines(logFile, normalizedTailLines) : [],
      statusReadError,
      normalizedTailLines,
    );
    const latestProgress = this.progressValue(rawStatus?.latest_progress) ?? this.parseLatestProgress(logTail);
    const serviceUnit = await this.readOptionalText(path.join(logDir, 'training-supervisor.unit'));
    const universeSize = this.numberValue(rawStatus?.universe_size);
    const rounds = this.roundsValue(rawStatus?.rounds, universeSize);
    const best = this.resultValue(rawStatus?.best, universeSize);
    const pid = this.numberValue(rawStatus?.pid);
    const processAlive = pid === null ? null : this.isProcessAlive(pid);
    const status = statusReadError ? 'failed' : this.stringValue(rawStatus?.status) ?? 'not_started';
    const active = !statusReadError && status === 'running' && processAlive !== false;
    const prefilterStatus = this.prefilterStatusValue(rawStatus?.prefilter);
    const advisorSummaries = this.advisorSummariesValue(rawStatus, this.prefilterLatestValue(rawStatus?.prefilter));
    const qianKun = await this.qianKunFromStatusOrHistory(rawStatus?.qian_kun);

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
      matrixBackend: this.stringValue(rawStatus?.matrix_backend),
      featureMatrixCache: this.matrixCacheValue(rawStatus?.feature_matrix_cache),
      red5RankMode: this.stringValue(rawStatus?.red5_rank_mode),
      prefilter: prefilterStatus,
      advisorSummaries,
      qianKun,
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
      syncSchedule: SYNC_SCHEDULE,
    };
  }

  async trainingStatusFromEvent(event: unknown, basePayload?: TrainingStatusPayload | null): Promise<TrainingStatusPayload> {
    const payload = basePayload ? this.cloneTrainingStatusPayload(basePayload) : await this.trainingStatus();
    if (!event || typeof event !== 'object' || Array.isArray(event)) {
      return payload;
    }
    const row = event as Record<string, unknown>;
    const progress = this.progressValue(row.latest_progress ?? row.latestProgress);
    const eventStatus = this.stringValue(row.status);
    const updatedAt = this.stringValue(row.updated_at ?? row.updatedAt);
    const eventRunId = this.stringValue(row.run_id ?? row.runId);
    const eventTimestamp = updatedAt ?? progress?.loggedAt ?? null;
    if (
      eventRunId &&
      payload.runId &&
      eventRunId !== payload.runId &&
      this.isOlderTimestamp(eventTimestamp, payload.updatedAt)
    ) {
      return payload;
    }
    const eventPid = this.numberValue(row.pid);
    const rawProcessAlive = row.process_alive ?? row.processAlive;
    const eventProcessAlive =
      typeof rawProcessAlive === 'boolean' ? rawProcessAlive : eventPid === null ? null : this.isProcessAlive(eventPid);
    const eventIsTerminal = eventStatus !== null && TERMINAL_TRAINING_STATUSES.has(eventStatus);
    if (progress) {
      payload.latestProgress = progress;
      payload.updatedAt = updatedAt ?? progress.loggedAt;
      payload.active = eventIsTerminal ? false : progress.targetIndex < progress.targetTotal || eventStatus === 'running';
      payload.status = eventIsTerminal ? eventStatus : payload.active ? 'running' : eventStatus ?? payload.status;
    } else if (eventStatus) {
      payload.status = eventStatus;
      payload.active = eventStatus === 'running';
      payload.updatedAt = updatedAt ?? payload.updatedAt;
    }
    payload.runId = eventRunId ?? payload.runId;
    if (eventPid !== null) {
      payload.pid = eventPid;
    }
    if (eventProcessAlive !== null) {
      payload.processAlive = eventProcessAlive;
      if (eventProcessAlive === false && payload.status === 'running') {
        payload.active = false;
      }
    }
    payload.statusFile = this.stringValue(row.status_path ?? row.statusPath) ?? payload.statusFile;
    payload.reportFile = this.stringValue(row.report_path ?? row.reportPath) ?? payload.reportFile;
    return payload;
  }

  private cloneTrainingStatusPayload(payload: TrainingStatusPayload): TrainingStatusPayload {
    return {
      ...payload,
      advisorSummaries: [...payload.advisorSummaries],
      rounds: [...payload.rounds],
      recentRounds: [...payload.recentRounds],
      logTail: [...payload.logTail],
      syncSchedule: { ...payload.syncSchedule },
    };
  }

  async serviceStatus(): Promise<ServiceStatusPayload> {
    const generatedAt = new Date();
    const root = this.repoRoot();
    const logDir = path.join(root, RUNTIME_LOG_DIR);
    const heavyJobLock = await this.heavyJobLockStatus(logDir);
    const [trainingStatus, historySummary, weightSignalSummary, pipelineRuns, syncRuns] = await Promise.all([
      this.trainingStatus(40).catch((error) => this.failedTrainingStatus(error)),
      this.repository.getSsqHistorySummary().catch((error) => ({ error })),
      this.repository.getTrainingWeightSignalSummary().catch((error) => ({ error })),
      this.repository.listPipelineRuns(1).catch(() => []),
      this.repository.listSyncRuns(1).catch(() => []),
    ]);

    const services: ServiceStatusItem[] = [
      await this.apiServiceStatus(generatedAt, logDir),
      await this.webServiceStatus(generatedAt, logDir),
      this.dbServiceStatus(generatedAt, historySummary),
      await this.syncServiceStatus(generatedAt, logDir, pipelineRuns[0] ?? null, syncRuns[0] ?? null),
      this.kdjServiceStatus(generatedAt, weightSignalSummary),
      await this.trainingServiceStatus(generatedAt, trainingStatus),
    ];
    const cpuCount = os.cpus().length;
    const activeTrainingWorkers = trainingStatus.active ? trainingStatus.workers ?? null : 0;
    return {
      generatedAt: generatedAt.toISOString(),
      overall: this.overallServiceStatus(services),
      services,
      heavyTaskLimits: {
        cpuCount,
        defaultWorkers: DEFAULT_HEAVY_TASK_WORKERS,
        recommendedInteractiveMax: Math.max(1, Math.min(DEFAULT_HEAVY_TASK_WORKERS, Math.floor(cpuCount / 2) || 1)),
        activeTrainingWorkers,
        heavyJobLock,
      },
    };
  }

  private async heavyJobLockStatus(logDir: string): Promise<Record<string, unknown> | null> {
    const lockPath = path.join(logDir, 'dehps-heavy-job.lock');
    const metadataPath = `${lockPath}.json`;
    try {
      const parsed: unknown = JSON.parse(await readFile(metadataPath, 'utf8'));
      const payload = this.objectValue(parsed);
      if (!payload) {
        throw new Error(`Invalid heavy-job metadata JSON at ${metadataPath}: expected object root`);
      }
      const pid = this.numberValue(payload.pid);
      const pidActive = pid === null ? null : this.isProcessAlive(pid);
      const status = this.stringValue(payload.status);
      const normalizedStatus = status?.toLowerCase() ?? null;
      const statusInactive = normalizedStatus !== null && HEAVY_JOB_INACTIVE_STATUSES.has(normalizedStatus);
      const active = pidActive === true && !statusInactive;
      return {
        lockPath,
        metadataPath,
        owner: this.stringValue(payload.owner),
        pid,
        active,
        pidActive,
        status,
        startedAt: this.stringValue(payload.started_at ?? payload.startedAt),
        heartbeatAt: this.stringValue(payload.heartbeat_at ?? payload.heartbeatAt),
        command: Array.isArray(payload.command) ? payload.command : null,
        context: payload.context && typeof payload.context === 'object' && !Array.isArray(payload.context) ? payload.context : null,
        reason: statusInactive
          ? `status_${normalizedStatus}`
          : active
            ? 'pid_running'
            : pidActive === false
              ? 'pid_not_running'
              : 'pid_unknown',
      };
    } catch (error) {
      const code = typeof error === 'object' && error !== null ? (error as { code?: unknown }).code : null;
      if (code === 'ENOENT') {
        return {
          lockPath,
          metadataPath,
          active: false,
          reason: 'metadata_missing',
        };
      }
      return {
        lockPath,
        metadataPath,
        active: false,
        reason: 'metadata_unreadable',
        error: error instanceof Error ? error.message : String(error),
      };
    }
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

  private async apiServiceStatus(generatedAt: Date, logDir: string): Promise<ServiceStatusItem> {
    const logFile = await this.firstExistingPath(path.join(logDir, 'api-dashboard.log'));
    const logTail = logFile ? await this.readTailLines(logFile, 40) : [];
    const recentError = this.latestErrorLine(logTail);
    return this.serviceStatusItem({
      name: 'api',
      label: 'API',
      status: recentError ? 'failed' : logFile ? 'ok' : 'warning',
      pid: process.pid,
      processAlive: true,
      heartbeatAt: generatedAt.toISOString(),
      generatedAt,
      recentError,
      logFile,
      metrics: {
        mode: 'read-only',
        uptimeSeconds: Math.floor(process.uptime()),
        nodeVersion: process.version,
      },
    });
  }

  private async webServiceStatus(generatedAt: Date, logDir: string): Promise<ServiceStatusItem> {
    const pid = await this.readPidFile(path.join(logDir, 'web-dashboard.pid'));
    const processAlive = pid === null ? null : this.isProcessAlive(pid);
    const logFile = await this.firstExistingPath(path.join(logDir, 'web-dashboard.log'));
    const logStat = logFile ? await this.safeStat(logFile) : null;
    const logTail = logFile ? await this.readTailLines(logFile, 40) : [];
    const heartbeatAt = logStat ? new Date(logStat.mtimeMs).toISOString() : null;
    const rawRecentError = this.latestErrorLine(logTail);
    const recentError =
      processAlive === true && rawRecentError && /ECONNREFUSED\s+127\.0\.0\.1:3000/i.test(rawRecentError)
        ? null
        : rawRecentError;
    const status = processAlive === false || recentError ? 'failed' : logFile ? 'ok' : 'warning';
    return this.serviceStatusItem({
      name: 'web',
      label: 'Web',
      status,
      pid,
      processAlive,
      heartbeatAt,
      generatedAt,
      recentError: logFile ? recentError : 'runtime/logs/web-dashboard.log 未找到',
      logFile,
      metrics: {
        pidFile: path.join(logDir, 'web-dashboard.pid'),
        schedule: SYNC_SCHEDULE.description,
      },
    });
  }

  private dbServiceStatus(generatedAt: Date, summary: unknown): ServiceStatusItem {
    if (this.hasError(summary)) {
      return this.serviceStatusItem({
        name: 'db',
        label: 'Postgres',
        status: 'failed',
        pid: null,
        processAlive: null,
        heartbeatAt: null,
        generatedAt,
        recentError: this.errorMessage(summary.error),
        logFile: null,
        metrics: {},
      });
    }
    const typed = summary as Awaited<ReturnType<ResearchRepository['getSsqHistorySummary']>>;
    const status = typed.tablePresent && typed.totalDraws > 0 ? 'ok' : typed.tablePresent ? 'warning' : 'failed';
    return this.serviceStatusItem({
      name: 'db',
      label: '数据库',
      status,
      pid: null,
      processAlive: null,
      heartbeatAt: generatedAt.toISOString(),
      generatedAt,
      recentError: typed.tablePresent ? null : 'ssq_history 表不存在',
      logFile: null,
      metrics: {
        tablePresent: typed.tablePresent,
        totalDraws: typed.totalDraws,
        minDrawDate: typed.minDrawDate,
        maxDrawDate: typed.maxDrawDate,
        latestIssue: typed.latestIssue,
        latestDrawDate: typed.latestDrawDate,
        latestCreatedAt: typed.latestCreatedAt,
      },
    });
  }

  private async syncServiceStatus(
    generatedAt: Date,
    logDir: string,
    pipelineRun: PipelineRunSummary | null,
    syncRun: SyncRunSummary | null,
  ): Promise<ServiceStatusItem> {
    const logFile = await this.firstExistingPath(path.join(logDir, 'ssq_draw_sync.log'));
    const logStat = logFile ? await this.safeStat(logFile) : null;
    const logTail = logFile ? await this.readTailLines(logFile, 40) : [];
    const lastStartedAt = syncRun?.startedAt ?? pipelineRun?.startedAt ?? null;
    const lastFinishedAt = syncRun?.finishedAt ?? pipelineRun?.finishedAt ?? null;
    const heartbeatAt = lastFinishedAt ?? lastStartedAt ?? (logStat ? new Date(logStat.mtimeMs).toISOString() : null);
    const recentError = syncRun?.errorMessage ?? pipelineRun?.errorMessage ?? this.latestErrorLine(logTail);
    const latestStatus = syncRun?.status ?? pipelineRun?.status ?? null;
    const stale = this.isStale(generatedAt, heartbeatAt, SYNC_STALE_SECONDS);
    const status: ServiceStatusLevel =
      latestStatus === 'failed' || recentError
        ? 'failed'
        : !syncRun && !pipelineRun
          ? 'warning'
          : stale
            ? 'warning'
            : 'ok';
    return this.serviceStatusItem({
      name: 'sync',
      label: '开奖同步',
      status,
      pid: null,
      processAlive: null,
      heartbeatAt,
      generatedAt,
      lastStartedAt,
      lastFinishedAt,
      recentError,
      logFile,
      metrics: {
        schedule: SYNC_SCHEDULE,
        latestPipelineRun: pipelineRun,
        latestSyncRun: syncRun,
        stale,
      },
    });
  }

  private kdjServiceStatus(generatedAt: Date, summary: unknown): ServiceStatusItem {
    if (this.hasError(summary)) {
      return this.serviceStatusItem({
        name: 'kdj',
        label: '权重KDJ',
        status: 'failed',
        pid: null,
        processAlive: null,
        heartbeatAt: null,
        generatedAt,
        recentError: this.errorMessage(summary.error),
        logFile: null,
        metrics: {},
      });
    }
    const typed = summary as Awaited<ReturnType<ResearchRepository['getTrainingWeightSignalSummary']>>;
    const heartbeatAt = typed.latestCreatedAt ?? typed.latestDrawDate;
    const stale = this.isStale(generatedAt, heartbeatAt, KDJ_STALE_SECONDS);
    const status: ServiceStatusLevel =
      !typed.tablePresent || typed.totalRows === 0 ? 'warning' : stale ? 'warning' : 'ok';
    return this.serviceStatusItem({
      name: 'kdj',
      label: '权重KDJ',
      status,
      pid: null,
      processAlive: null,
      heartbeatAt,
      generatedAt,
      recentError: !typed.tablePresent
        ? 'training_weight_signals 表不存在'
        : typed.totalRows === 0
          ? 'training_weight_signals 暂无数据'
          : null,
      logFile: null,
      metrics: {
        tablePresent: typed.tablePresent,
        totalRows: typed.totalRows,
        latestSignalRunId: typed.latestSignalRunId,
        latestIssue: typed.latestIssue,
        latestDrawDate: typed.latestDrawDate,
        latestCreatedAt: typed.latestCreatedAt,
        weights: typed.weights,
        stale,
      },
    });
  }

  private async trainingServiceStatus(generatedAt: Date, status: TrainingStatusPayload): Promise<ServiceStatusItem> {
    const logFile = status.logFile;
    const logStat = logFile ? await this.safeStat(logFile) : null;
    const heartbeatAt =
      status.latestProgress?.loggedAt ??
      status.updatedAt ??
      (logStat ? new Date(logStat.mtimeMs).toISOString() : status.startedAt);
    const recentError =
      status.status === 'failed'
        ? this.latestErrorLine(status.logTail) ?? status.logTail.at(-1) ?? 'training failed'
        : this.latestErrorLine(status.logTail);
    const stale = !status.active && this.isStale(generatedAt, heartbeatAt, TRAINING_STALE_SECONDS);
    const serviceStatus: ServiceStatusLevel =
      status.status === 'failed' || status.processAlive === false
        ? 'failed'
        : status.active || status.status === 'completed'
          ? stale
            ? 'warning'
            : 'ok'
          : 'warning';
    return this.serviceStatusItem({
      name: 'training',
      label: '训练',
      status: serviceStatus,
      pid: status.pid,
      processAlive: status.processAlive,
      heartbeatAt,
      generatedAt,
      lastStartedAt: status.startedAt,
      lastFinishedAt: status.active ? null : status.updatedAt,
      recentError,
      logFile,
      metrics: {
        runId: status.runId,
        active: status.active,
        rawStatus: status.status,
        completedRounds: status.completedRounds,
        workers: status.workers,
        trainWindow: status.trainWindow,
        evalWindow: status.evalWindow,
        topN: status.topN,
        latestProgress: status.latestProgress,
        stale,
      },
    });
  }

  private serviceStatusItem(
    item: Omit<ServiceStatusItem, 'heartbeatAgeSeconds' | 'lastStartedAt' | 'lastFinishedAt'> & {
      generatedAt: Date;
      lastStartedAt?: string | null;
      lastFinishedAt?: string | null;
    },
  ): ServiceStatusItem {
    return {
      name: item.name,
      label: item.label,
      status: item.status,
      pid: item.pid,
      processAlive: item.processAlive,
      heartbeatAt: item.heartbeatAt,
      heartbeatAgeSeconds: this.ageSeconds(item.generatedAt, item.heartbeatAt),
      lastStartedAt: item.lastStartedAt ?? null,
      lastFinishedAt: item.lastFinishedAt ?? null,
      recentError: item.recentError,
      logFile: item.logFile,
      metrics: item.metrics,
    };
  }

  private failedTrainingStatus(error: unknown): TrainingStatusPayload {
    return {
      status: 'failed',
      active: false,
      processAlive: null,
      runId: null,
      startedAt: null,
      updatedAt: null,
      deadline: null,
      pid: null,
      historyScope: null,
      regimeYears: null,
      regimeStartDate: null,
      trainMode: null,
      trainWindow: null,
      evalWindow: null,
      topN: null,
      workers: null,
      memoryBudgetGb: null,
      universeSize: null,
      matrixBackend: null,
      featureMatrixCache: null,
      red5RankMode: null,
      prefilter: null,
      advisorSummaries: [],
      qianKun: this.qianKunValue(null),
      completedRounds: 0,
      rounds: [],
      latestRound: null,
      recentRounds: [],
      best: null,
      latestProgress: null,
      statusFile: null,
      reportFile: null,
      logFile: null,
      serviceUnit: null,
      logTail: [this.errorMessage(error)],
      syncSchedule: SYNC_SCHEDULE,
    };
  }

  private overallServiceStatus(services: ServiceStatusItem[]): ServiceStatusLevel {
    const rank: Record<ServiceStatusLevel, number> = { ok: 0, unknown: 1, warning: 2, failed: 3 };
    return services.reduce<ServiceStatusLevel>(
      (overall, service) => (rank[service.status] > rank[overall] ? service.status : overall),
      'ok',
    );
  }

  private async readPidFile(filePath: string): Promise<number | null> {
    try {
      const content = await readFile(filePath, 'utf8');
      const trimmed = content.trim();
      if (!/^\d+$/.test(trimmed)) {
        return null;
      }
      const pid = Number(trimmed);
      return Number.isFinite(pid) && pid > 0 ? pid : null;
    } catch (error) {
      if (this.isNotFoundError(error)) {
        return null;
      }
      throw error;
    }
  }

  private async safeStat(filePath: string): Promise<{ mtimeMs: number } | null> {
    try {
      return await stat(filePath);
    } catch (error) {
      if (this.isNotFoundError(error)) {
        return null;
      }
      throw error;
    }
  }

  private latestErrorLine(lines: string[]): string | null {
    const errorPattern = /\b(errors?|exception|failed|traceback)\b/i;
    const unhandledRejectionPattern = /\bunhandled\s+(?:promise\s+)?rejection\b|\bunhandled(?:promise)?rejection(?:warning)?\b/i;
    const zeroErrorPattern =
      /\b(?:0|no)\s+(?:errors?|fail(?:ed|ures?)?)\b|\b(?:errors?|fail(?:ed|ures?)?)\s*[:=]\s*0\b/gi;
    const recoveryPattern = /\b(ready|listening|started|success|successful|complete|completed)\b/i;
    let latestErrorIndex = -1;
    let latestRecoveryIndex = -1;
    lines.forEach((line, index) => {
      const lineWithoutZeroSummaries = line.replace(zeroErrorPattern, ' ');
      if (errorPattern.test(lineWithoutZeroSummaries) || unhandledRejectionPattern.test(lineWithoutZeroSummaries)) {
        latestErrorIndex = index;
      }
      if (recoveryPattern.test(line)) {
        latestRecoveryIndex = index;
      }
    });
    if (latestErrorIndex < 0 || latestRecoveryIndex > latestErrorIndex) {
      return null;
    }
    return lines[latestErrorIndex].slice(0, 500);
  }

  private ageSeconds(now: Date, isoValue: string | null): number | null {
    if (!isoValue) {
      return null;
    }
    const value = Date.parse(isoValue);
    if (!Number.isFinite(value)) {
      return null;
    }
    return Math.max(0, Math.floor((now.getTime() - value) / 1000));
  }

  private isStale(now: Date, isoValue: string | null, maxAgeSeconds: number): boolean {
    const age = this.ageSeconds(now, isoValue);
    return age !== null && age > maxAgeSeconds;
  }

  private isOlderTimestamp(candidate: string | null, baseline: string | null): boolean {
    if (!candidate || !baseline) {
      return false;
    }
    const candidateTime = Date.parse(candidate);
    const baselineTime = Date.parse(baseline);
    return Number.isFinite(candidateTime) && Number.isFinite(baselineTime) && candidateTime < baselineTime;
  }

  private hasError(value: unknown): value is { error: unknown } {
    return value !== null && typeof value === 'object' && 'error' in value;
  }

  private errorMessage(error: unknown): string {
    return error instanceof Error ? error.message : String(error);
  }

  private statusReadError(rawStatus: Record<string, unknown> | null): string | null {
    return this.stringValue(rawStatus?.[STATUS_READ_ERROR_KEY]);
  }

  private appendStatusReadError(lines: string[], error: string | null, lineCount: number): string[] {
    if (!error) {
      return lines;
    }
    return [...lines, error].slice(-lineCount);
  }

  private normalizeLimit(limit: number): number {
    if (!Number.isFinite(limit)) {
      return DEFAULT_LIMIT;
    }
    return Math.min(Math.max(Math.trunc(limit), 1), 100);
  }

  private normalizeSignalLimit(limit: number): number {
    if (!Number.isFinite(limit)) {
      return 1000;
    }
    return Math.min(Math.max(Math.trunc(limit), 1), 1000);
  }

  private normalizeCandidateLimit(limit: number): number {
    if (!Number.isFinite(limit)) {
      return 10000;
    }
    return Math.min(Math.max(Math.trunc(limit), 1), 10000);
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
      return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
        ? (parsed as Record<string, unknown>)
        : this.statusReadErrorObject(filePath, 'expected object root');
    } catch (error) {
      if (this.isNotFoundError(error)) {
        return null;
      }
      if (error instanceof SyntaxError) {
        return this.statusReadErrorObject(filePath, error.message);
      }
      throw error;
    }
  }

  private statusReadErrorObject(filePath: string, reason: string): Record<string, unknown> {
    return {
      status: 'failed',
      [STATUS_READ_ERROR_KEY]: `failed to read training status JSON ${filePath}: ${reason}`,
    };
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
      return [`failed to read log file ${filePath}: ${this.errorMessage(error)}`].slice(-lineCount);
    }
  }

  private deriveReportPath(statusFile: string | null): string | null {
    return statusFile ? statusFile.replace(/\.json$/, '.md') : null;
  }

  private parseLatestProgress(lines: string[]): TrainingProgress | null {
    const progressPattern =
      /^\[supervisor\]\s+(\S+)\s+round=(\d+)\s+target=(\d+)\/(\d+)\s+issue=(\d+)\s+train_draws=(\d+)\s+elapsed=([\d.]+)s(?:\s+.*)?$/;
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

  private progressValue(value: unknown): TrainingProgress | null {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      return null;
    }
    const row = value as Record<string, unknown>;
    const loggedAt = this.stringValue(row.logged_at) ?? this.stringValue(row.loggedAt);
    const round = this.numberValue(row.round);
    const targetIndex = this.numberValue(row.target_index) ?? this.numberValue(row.targetIndex);
    const targetTotal = this.numberValue(row.target_total) ?? this.numberValue(row.targetTotal);
    const issue = this.stringValue(row.issue);
    const trainDraws = this.numberValue(row.train_draws) ?? this.numberValue(row.trainDraws);
    const elapsedSeconds = this.numberValue(row.elapsed_seconds) ?? this.numberValue(row.elapsedSeconds);
    if (
      loggedAt === null ||
      round === null ||
      targetIndex === null ||
      targetTotal === null ||
      issue === null ||
      trainDraws === null ||
      elapsedSeconds === null
    ) {
      return null;
    }
    return {
      loggedAt,
      round,
      targetIndex,
      targetTotal,
      issue,
      trainDraws,
      elapsedSeconds,
    };
  }

  private matrixCacheValue(value: unknown): TrainingMatrixCache | null {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      return null;
    }
    const row = value as Record<string, unknown>;
    return {
      backend: this.stringValue(row.backend),
      cacheKey: this.stringValue(row.cache_key) ?? this.stringValue(row.cacheKey),
      cachePath: this.stringValue(row.cache_path) ?? this.stringValue(row.cachePath),
      cacheHit: typeof row.cache_hit === 'boolean' ? row.cache_hit : typeof row.cacheHit === 'boolean' ? row.cacheHit : null,
      buildSeconds: this.numberValue(row.build_seconds) ?? this.numberValue(row.buildSeconds),
      sourceCount: this.numberValue(row.source_count) ?? this.numberValue(row.sourceCount),
      filteredCount: this.numberValue(row.filtered_count) ?? this.numberValue(row.filteredCount),
      excludedCount: this.numberValue(row.excluded_count) ?? this.numberValue(row.excludedCount),
      red5RankMode: this.stringValue(row.red5_rank_mode) ?? this.stringValue(row.red5RankMode),
    };
  }

  private prefilterStatusValue(value: unknown): TrainingPrefilterStatus | null {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      return null;
    }
    const row = value as Record<string, unknown>;
    return {
      mode: this.stringValue(row.mode),
      description: this.stringValue(row.description),
      latest: this.prefilterRunValue(row.latest),
    };
  }

  private prefilterLatestValue(value: unknown): unknown {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      return null;
    }
    return (value as Record<string, unknown>).latest ?? null;
  }

  private advisorSummariesValue(statusValue: unknown, prefilterLatestValue: unknown): TrainingAdvisorSummary[] {
    const statusRow = this.objectValue(statusValue);
    const prefilterLatest = this.objectValue(prefilterLatestValue);
    return ADVISOR_SOURCES.map((source) => this.advisorSummaryValue(source, statusRow, prefilterLatest)).filter(
      (summary): summary is TrainingAdvisorSummary => summary !== null,
    );
  }

  private advisorSummaryValue(
    source: TrainingAdvisorSource,
    statusRow: Record<string, unknown> | null,
    prefilterLatest: Record<string, unknown> | null,
  ): TrainingAdvisorSummary | null {
    const statusSource = this.objectValue(statusRow?.[source]);
    const statusLatest = this.objectValue(statusSource?.latest);
    const prefilterSource = this.objectValue(prefilterLatest?.[source]);
    const row = this.mergeObjects(statusSource, statusLatest, prefilterSource);
    if (!row) {
      return null;
    }

    const advice = this.advisorAdviceRowsValue(
      row.advice ?? row.top_advice ?? row.topAdvice ?? row.advice_rows ?? row.adviceRows ?? row.rows,
    );
    const fields = this.advisorFieldsValue(row, advice);
    const enabled =
      typeof row.enabled === 'boolean'
        ? row.enabled
        : advice.length > 0 || fields.length > 0 || Boolean(this.stringValue(row.latest_issue ?? row.latestIssue));
    const status =
      this.stringValue(row.status ?? row.state) ??
      (enabled ? (advice.length || fields.length ? 'ready' : null) : 'disabled');
    const selectedCount = this.numberValue(row.selected_count ?? row.selectedCount) ?? this.advisorDecisionCount(advice, 'selected');
    const downweightedCount =
      this.numberValue(row.downweighted_count ?? row.downweightedCount) ?? this.advisorDecisionCount(advice, 'downweighted');
    const rejectedCount = this.numberValue(row.rejected_count ?? row.rejectedCount) ?? this.advisorDecisionCount(advice, 'rejected');

    return {
      source,
      enabled,
      status,
      mode: this.stringValue(row.mode),
      budget: this.numberValue(row.budget ?? row.candidate_budget ?? row.candidateBudget),
      candidateCount: this.numberValue(row.candidate_count ?? row.candidateCount),
      selectedCount,
      downweightedCount,
      rejectedCount,
      fieldCount: this.numberValue(row.field_count ?? row.fieldCount) ?? (fields.length ? fields.length : null),
      fields,
      latestSignalIssue:
        this.stringValue(row.latest_signal_issue ?? row.latestSignalIssue) ??
        this.stringValue(row.latest_issue ?? row.latestIssue) ??
        this.stringValue(row.issue),
      signalRunId: this.stringValue(row.signal_run_id ?? row.signalRunId),
      advice,
      controlVerdict: this.advisorControlVerdictValue(row),
    };
  }

  private advisorAdviceRowsValue(value: unknown): TrainingAdvisorAdviceRow[] {
    if (!Array.isArray(value)) {
      return [];
    }
    return value
      .map((item) => this.advisorAdviceRowValue(item))
      .filter((item): item is TrainingAdvisorAdviceRow => item !== null);
  }

  private advisorAdviceRowValue(value: unknown): TrainingAdvisorAdviceRow | null {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      return null;
    }
    const row = value as Record<string, unknown>;
    const weightName =
      this.stringValue(row.weight_name ?? row.weightName) ??
      this.stringValue(row.field_name ?? row.fieldName) ??
      this.stringValue(row.field);
    if (!weightName) {
      return null;
    }
    const frozenValidation = this.objectValue(row.frozen_validation ?? row.frozenValidation);
    const frozenReward = this.objectValue(frozenValidation?.reward);
    return {
      weightName,
      latestIssue:
        this.stringValue(row.latest_issue ?? row.latestIssue) ??
        this.stringValue(row.signal_issue ?? row.signalIssue) ??
        this.stringValue(row.issue),
      suggestedOffset:
        this.numberValue(row.suggested_offset ?? row.suggestedOffset) ??
        this.numberValue(row.recommended_offset ?? row.recommendedOffset) ??
        this.numberValue(row.offset) ??
        this.numberValue(row.applied_offset ?? row.appliedOffset),
      confidence: this.numberValue(row.confidence),
      validationMetric:
        this.numberValue(row.validation_metric ?? row.validationMetric) ??
        this.numberValue(row.validation_score ?? row.validationScore) ??
        this.numberValue(frozenReward?.objectiveScore),
      baselineMetric:
        this.numberValue(row.baseline_metric ?? row.baselineMetric) ??
        this.numberValue(row.baseline_score ?? row.baselineScore),
      configHash: this.stringValue(row.config_hash ?? row.configHash),
      decision: this.stringValue(row.decision),
      reason: this.stringValue(row.reason),
      source: this.stringValue(row.source),
    };
  }

  private advisorFieldsValue(row: Record<string, unknown>, advice: TrainingAdvisorAdviceRow[]): string[] {
    const explicitFields = this.stringArrayValue(row.fields);
    if (explicitFields.length) {
      return this.uniqueStrings(explicitFields);
    }
    return this.uniqueStrings([
      ...this.stringArrayValue(row.selected_fields ?? row.selectedFields),
      ...this.stringArrayValue(row.downweighted_fields ?? row.downweightedFields),
      ...this.stringArrayValue(row.rejected_fields ?? row.rejectedFields),
      ...advice.map((item) => item.weightName),
    ]);
  }

  private advisorDecisionCount(advice: TrainingAdvisorAdviceRow[], decision: string): number | null {
    if (!advice.length) {
      return null;
    }
    return advice.filter((item) => item.decision === decision).length;
  }

  private advisorControlVerdictValue(row: Record<string, unknown>): Record<string, unknown> | string | null {
    const value =
      row.control_verdict ??
      row.controlVerdict ??
      row.frozen_verdict ??
      row.frozenVerdict ??
      row.verdict ??
      row.promotion_gate ??
      row.promotionGate;
    if (typeof value === 'string' && value.length > 0) {
      return value;
    }
    return this.objectValue(value);
  }

  private mergeObjects(
    ...values: Array<Record<string, unknown> | null | undefined>
  ): Record<string, unknown> | null {
    const objects = values.filter((value): value is Record<string, unknown> => Boolean(value));
    return objects.length ? Object.assign({}, ...objects) : null;
  }

  private uniqueStrings(values: string[]): string[] {
    return [...new Set(values.filter((value) => value.length > 0))];
  }

  private prefilterRunValue(value: unknown): TrainingPrefilterRun | null {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      return null;
    }
    const row = value as Record<string, unknown>;
    return {
      mode: this.stringValue(row.mode),
      round: this.numberValue(row.round),
      targetStride: this.numberValue(row.target_stride) ?? this.numberValue(row.targetStride),
      targetCount: this.numberValue(row.target_count) ?? this.numberValue(row.targetCount),
      targetWorkerCount: this.numberValue(row.target_worker_count) ?? this.numberValue(row.targetWorkerCount),
      generatedConfigCount: this.numberValue(row.generated_config_count) ?? this.numberValue(row.generatedConfigCount),
      keptConfigCount: this.numberValue(row.kept_config_count) ?? this.numberValue(row.keptConfigCount),
      promoteLimit: this.numberValue(row.promote_limit) ?? this.numberValue(row.promoteLimit),
      diversityQuota: this.numberValue(row.diversity_quota) ?? this.numberValue(row.diversityQuota),
      diversityAddedCount: this.numberValue(row.diversity_added_count) ?? this.numberValue(row.diversityAddedCount),
      stagnationRounds: this.numberValue(row.stagnation_rounds) ?? this.numberValue(row.stagnationRounds),
      lowCoverageFields: this.stringArrayValue(row.low_coverage_fields ?? row.lowCoverageFields),
      candidateBudget: this.numericRecordValue(row.candidate_budget ?? row.candidateBudget),
      phaseStage: this.stringValue(row.phase_stage ?? row.phaseStage),
      searchBaseMinDistance: this.numberValue(row.search_base_min_distance ?? row.searchBaseMinDistance),
      searchBaseStart: this.searchBaseSummaryValue(row.search_base_start ?? row.searchBaseStart),
      searchBase: this.searchBaseSummaryValue(row.search_base ?? row.searchBase),
      frozenValidationWindow: this.numberValue(row.frozen_validation_window) ?? this.numberValue(row.frozenValidationWindow),
      controlExperiments: this.objectArrayValue(row.control_experiments ?? row.controlExperiments),
      refinedConfigCount: this.numberValue(row.refined_config_count) ?? this.numberValue(row.refinedConfigCount),
      elapsedSeconds: this.numberValue(row.elapsed_seconds) ?? this.numberValue(row.elapsedSeconds),
      note: this.stringValue(row.note),
    };
  }

  private searchBaseSummaryValue(value: unknown): TrainingSearchBaseSummary | null {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      return null;
    }
    const row = value as Record<string, unknown>;
    const medianRank = this.numberValue(row.median_rank ?? row.medianRank);
    const bestRank = this.numberValue(row.best_rank ?? row.bestRank);
    const worstRank = this.numberValue(row.worst_rank ?? row.worstRank);
    const rankQuality = this.rankQualityValue(row.rank_quality ?? row.rankQuality, {
      medianRank,
      worstRank,
      universeSize: 1107568,
    });
    const rewardRow =
      row.reward && typeof row.reward === 'object' && !Array.isArray(row.reward)
        ? (row.reward as Record<string, unknown>)
        : null;
    const reward = rewardRow
      ? {
          hitReward: this.numberValue(rewardRow.hitReward) ?? 0,
          red5Reward: this.numberValue(rewardRow.red5Reward) ?? 0,
          rankQualityReward: this.numberValue(rewardRow.rankQualityReward) ?? 0,
          rankPenalty: this.numberValue(rewardRow.rankPenalty) ?? 0,
          tailRiskPenalty: this.numberValue(rewardRow.tailRiskPenalty) ?? rankQuality.tail_risk_penalty,
          objectiveScore: this.numberValue(rewardRow.objectiveScore) ?? 0,
        }
      : null;
    return {
      source: this.stringValue(row.source),
      changed: Boolean(row.changed),
      previousConfigHash: this.stringValue(row.previous_config_hash ?? row.previousConfigHash) ?? '',
      configHash: this.stringValue(row.config_hash ?? row.configHash) ?? '',
      candidateConfigHash: this.stringValue(row.candidate_config_hash ?? row.candidateConfigHash) ?? '',
      minConfigDistance: this.numberValue(row.min_config_distance ?? row.minConfigDistance),
      selectedConfigDistance: this.numberValue(row.selected_config_distance ?? row.selectedConfigDistance),
      searchChallengerConfigDistance: this.numberValue(
        row.search_challenger_config_distance ?? row.searchChallengerConfigDistance,
      ),
      searchChallengerRankVectorChanged:
        typeof (row.search_challenger_rank_vector_changed ?? row.searchChallengerRankVectorChanged) === 'boolean'
          ? Boolean(row.search_challenger_rank_vector_changed ?? row.searchChallengerRankVectorChanged)
          : null,
      recentSearchBaseHashes: this.stringArrayValue(row.recent_search_base_hashes ?? row.recentSearchBaseHashes),
      top_100_hits: this.numberValue(row.top_100_hits ?? row.top100Hits) ?? 0,
      top_1000_hits: this.numberValue(row.top_1000_hits ?? row.top1000Hits) ?? 0,
      top_10000_hits: this.numberValue(row.top_10000_hits ?? row.top10000Hits) ?? 0,
      median_rank: medianRank,
      best_rank: bestRank,
      worst_rank: worstRank,
      rank_quality: rankQuality,
      reward,
      config: this.numericRecordValue(row.config),
    };
  }

  private roundSummaryFromListItem(
    round: TrainingRoundListItem,
    detail: TrainingRoundDetail | null,
  ): TrainingRoundSummary {
    const detailBest = detail ? this.resultValue(detail.bestSummary, 1107568) : null;
    return {
      round: round.roundIndex,
      phase: round.phase,
      step: round.step,
      generated_config_count: null,
      config_count: 0,
      prefilter: this.prefilterRunValue(detail?.prefilter ?? round.prefilter),
      rankMovement: detail?.rankMovement ?? round.rankMovement,
      improved: round.improved,
      best: detailBest ?? this.resultFromRoundListItem(round),
      topResults: detail ? this.resultsValue(detail.topResults, 1107568) : [],
    };
  }

  private resultFromRoundListItem(round: TrainingRoundListItem): TrainingResult {
    const medianRank = round.medianRank ?? 1107568;
    const bestRank = round.bestRank ?? 1107568;
    const worstRank = round.worstRank ?? 1107568;
    const red5 = {
      ...this.emptyRedFive(),
      top_100_hits: round.red5Top100Hits,
      top_1000_hits: round.red5Top1000Hits,
      top_10000_hits: round.red5Top10000Hits,
    };
    const rankQuality = this.rankQualityValue(round.bestRankQuality, { medianRank, worstRank, universeSize: 1107568 });
    const reward = this.rewardSummary({
      top100Hits: round.top100Hits,
      top1000Hits: round.top1000Hits,
      top10000Hits: round.top10000Hits,
      red5,
      rankQuality,
      medianRank,
      worstRank,
      universeSize: 1107568,
    });
    if (round.objectiveScore !== null) {
      reward.objectiveScore = round.objectiveScore;
    }
    return {
      config: {},
      as_of_issue: round.asOfIssue,
      history_fingerprint: '',
      config_hash: '',
      evaluated_draws: round.evalWindow,
      top_100_hits: round.top100Hits,
      top_1000_hits: round.top1000Hits,
      top_10000_hits: round.top10000Hits,
      median_rank: medianRank,
      best_rank: bestRank,
      worst_rank: worstRank,
      red5,
      rank_quality: rankQuality,
      run_key: `${round.runId}:${round.roundIndex}`,
      reward,
      frozen_validation: null,
    };
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
      generated_config_count: this.numberValue(row.generated_config_count) ?? this.numberValue(row.generatedConfigCount),
      config_count: configCount,
      prefilter: this.prefilterRunValue(row.prefilter),
      rankMovement: this.rankMovementValue(row.rank_movement ?? row.rankMovement),
      improved: Boolean(row.improved),
      best: this.resultValue(row.best, universeSize),
      topResults: this.resultsValue(row.top_results, universeSize),
    };
  }

  private rankMovementValue(value: unknown): TrainingRankMovementSummary | null {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      return null;
    }
    const row = value as Record<string, unknown>;
    return {
      comparedToRound: this.numberValue(row.compared_to_round ?? row.comparedToRound),
      comparedTargetCount: this.numberValue(row.compared_target_count ?? row.comparedTargetCount) ?? 0,
      changedTargetCount: this.numberValue(row.changed_target_count ?? row.changedTargetCount) ?? 0,
      medianChangedAbsDelta: this.numberValue(row.median_changed_abs_delta ?? row.medianChangedAbsDelta),
      maxAbsDelta: this.numberValue(row.max_abs_delta ?? row.maxAbsDelta),
      sameRankVector:
        typeof (row.same_rank_vector ?? row.sameRankVector) === 'boolean'
          ? Boolean(row.same_rank_vector ?? row.sameRankVector)
          : null,
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

  private targetResultsValue(value: unknown): TrainingTargetResult[] {
    if (!Array.isArray(value)) {
      return [];
    }
    return value
      .map((item) => this.targetResultValue(item))
      .filter((item): item is TrainingTargetResult => item !== null);
  }

  private targetResultValue(value: unknown): TrainingTargetResult | null {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      return null;
    }
    const row = value as Record<string, unknown>;
    const issue = this.stringValue(row.issue);
    const rank = this.numberValue(row.rank);
    if (!issue || rank === null) {
      return null;
    }
    return {
      issue,
      drawDate: this.stringValue(row.draw_date) ?? this.stringValue(row.drawDate),
      redNumbers: this.numberArrayValue(row.red_numbers ?? row.redNumbers),
      rank,
      score: this.numberValue(row.score),
      hitTop100: Boolean(row.hit_top_100 ?? row.hitTop100),
      hitTop1000: Boolean(row.hit_top_1000 ?? row.hitTop1000),
      hitTop10000: Boolean(row.hit_top_10000 ?? row.hitTop10000),
      red5Rank: this.numberValue(row.red5_rank ?? row.red5Rank),
      red5Score: this.numberValue(row.red5_score ?? row.red5Score),
      red5Numbers: this.numberArrayValue(row.red5_numbers ?? row.red5Numbers),
      red5MissingNumber: this.numberValue(row.red5_missing_number ?? row.red5MissingNumber),
      red5ExtraNumber: this.numberValue(row.red5_extra_number ?? row.red5ExtraNumber),
      hitRed5Top100: Boolean(row.hit_red5_top_100 ?? row.hitRed5Top100),
      hitRed5Top1000: Boolean(row.hit_red5_top_1000 ?? row.hitRed5Top1000),
      hitRed5Top10000: Boolean(row.hit_red5_top_10000 ?? row.hitRed5Top10000),
    };
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
      frozen_validation: this.objectValue(row.frozen_validation),
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

  private async qianKunFromStatusOrHistory(value: unknown): Promise<TrainingQianKunSummary> {
    const fromStatus = this.qianKunValue(value);
    if (fromStatus.total_draws > 0 || fromStatus.latest_pattern || fromStatus.latest_issue) {
      return fromStatus;
    }
    return this.qianKunFromHistory().catch(() => fromStatus);
  }

  private async qianKunFromHistory(): Promise<TrainingQianKunSummary> {
    const draws = await this.repository.listSsqHistoryDraws();
    return this.qianKunFromHistoryDraws(draws);
  }

  private qianKunFromHistoryDraws(draws: SsqHistoryDraw[]): TrainingQianKunSummary {
    const rows = draws
      .map((draw) => {
        const numbers = this.normalizeRedNumbers(draw.redNumbers);
        return draw.issue && numbers.length === 6 ? { issue: draw.issue, numbers } : null;
      })
      .filter((row): row is { issue: string; numbers: number[] } => row !== null);
    const counts = new Map<string, number>();
    const recentCounts = new Map<string, number>();
    for (const row of rows) {
      const pattern = this.qianKunPattern(row.numbers);
      counts.set(pattern, (counts.get(pattern) ?? 0) + 1);
    }
    const recentWindow = Math.min(QIAN_KUN_RECENT_WINDOW, rows.length);
    for (const row of rows.slice(-recentWindow)) {
      const pattern = this.qianKunPattern(row.numbers);
      recentCounts.set(pattern, (recentCounts.get(pattern) ?? 0) + 1);
    }

    const totalDraws = rows.length;
    const latest = rows.at(-1);
    const latestPattern = latest ? this.qianKunPattern(latest.numbers) : '';
    const patterns = [...new Set([...counts.keys(), ...recentCounts.keys(), QIAN_PATTERN, KUN_PATTERN])]
      .map((pattern) => {
        const count = counts.get(pattern) ?? 0;
        const recentCount = recentCounts.get(pattern) ?? 0;
        return {
          pattern,
          label: this.qianKunLabel(pattern) ?? pattern,
          icon: this.qianKunIcon(pattern),
          lines: this.qianKunLines(pattern),
          count,
          rate: totalDraws > 0 ? count / totalDraws : 0,
          recent_count: recentCount,
          recent_rate: recentWindow > 0 ? recentCount / recentWindow : 0,
        };
      })
      .sort((left, right) => {
        if (right.count !== left.count) {
          return right.count - left.count;
        }
        if (right.recent_count !== left.recent_count) {
          return right.recent_count - left.recent_count;
        }
        return right.pattern.localeCompare(left.pattern);
      });

    return {
      total_draws: totalDraws,
      recent_window: recentWindow,
      latest_issue: latest?.issue ?? '',
      latest_numbers: latest?.numbers ?? [],
      latest_pattern: latestPattern,
      latest_label: latestPattern ? this.qianKunLabel(latestPattern) ?? latestPattern : '',
      latest_icon: latestPattern ? this.qianKunIcon(latestPattern) : '',
      latest_lines: latestPattern ? this.qianKunLines(latestPattern) : [],
      qian_count: counts.get(QIAN_PATTERN) ?? 0,
      kun_count: counts.get(KUN_PATTERN) ?? 0,
      patterns,
    };
  }

  private normalizeRedNumbers(value: unknown): number[] {
    if (!Array.isArray(value)) {
      return [];
    }
    const numbers = value
      .map((item) => this.numberValue(item))
      .filter((item): item is number => item !== null && Number.isInteger(item) && item >= 1 && item <= 33)
      .sort((left, right) => left - right);
    return new Set(numbers).size === 6 ? numbers : [];
  }

  private qianKunPattern(numbers: number[]): string {
    return numbers.map((number) => String(number % 2)).join('');
  }

  private qianKunLines(pattern: string): string[] {
    return /^[01]{6}$/.test(pattern) ? [...pattern].map((bit) => (bit === '1' ? YANG_LINE : YIN_LINE)) : [];
  }

  private qianKunValue(value: unknown): TrainingQianKunSummary {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      return {
        total_draws: 0,
        recent_window: 0,
        latest_issue: '',
        latest_numbers: [],
        latest_pattern: '',
        latest_label: '',
        latest_icon: '',
        latest_lines: [],
        qian_count: 0,
        kun_count: 0,
        patterns: [],
      };
    }
    const row = value as Record<string, unknown>;
    const latestPattern = this.stringValue(row.latest_pattern) ?? '';
    const latestLines = this.stringArrayValue(row.latest_lines);
    return {
      total_draws: this.numberValue(row.total_draws) ?? 0,
      recent_window: this.numberValue(row.recent_window) ?? 0,
      latest_issue: this.stringValue(row.latest_issue) ?? '',
      latest_numbers: this.numberArrayValue(row.latest_numbers),
      latest_pattern: latestPattern,
      latest_label: this.qianKunLabel(latestPattern) ?? this.stringValue(row.latest_label) ?? '',
      latest_icon: this.stringValue(row.latest_icon) ?? this.qianKunIcon(latestPattern),
      latest_lines: latestLines.length > 0 ? latestLines : this.qianKunLines(latestPattern),
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
          label: this.qianKunLabel(pattern) ?? this.stringValue(row.label) ?? pattern,
          icon: this.stringValue(row.icon) ?? this.qianKunIcon(pattern),
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
          icon: string;
          lines: string[];
          count: number;
          rate: number;
          recent_count: number;
          recent_rate: number;
        } => item !== null,
      );
  }

  private qianKunLabel(pattern: string) {
    return HEXAGRAMS_BY_PATTERN[pattern]?.label;
  }

  private qianKunIcon(pattern: string) {
    const number = HEXAGRAMS_BY_PATTERN[pattern]?.number;
    return number ? String.fromCodePoint(HEXAGRAM_UNICODE_BASE + number) : '';
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
    if (typeof value !== 'string') {
      return null;
    }
    const normalized = value.trim();
    return normalized.length > 0 ? normalized : null;
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

  private objectArrayValue(value: unknown): Record<string, unknown>[] {
    if (!Array.isArray(value)) {
      return [];
    }
    return value.filter(
      (item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object' && !Array.isArray(item),
    );
  }

  private objectValue(value: unknown): Record<string, unknown> | null {
    return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
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
