export type ExperimentSummary = {
  experimentKey: string;
  strategyKey: string;
  hypothesis: string | null;
  totalCombinations: number;
  keptCombinations: number;
  keepRate: number;
  historyDraws: number;
  coveredDraws: number;
  coverageRate: number;
  lift: number;
  config: Record<string, unknown>;
  summary: string | null;
  createdAt: string;
};

export type ExperimentDetail = ExperimentSummary & {
  reportMarkdown: string | null;
  reportCreatedAt: string | null;
};

export type PipelineRunSummary = {
  runKey: string;
  status: string;
  startedAt: string;
  finishedAt: string | null;
  syncRunKey: string | null;
  experimentKey: string | null;
  gitCommitSha: string | null;
  errorMessage: string | null;
};

export type SyncRunSummary = {
  runKey: string;
  source: string;
  status: string;
  startedAt: string;
  finishedAt: string | null;
  fetchedCount: number;
  insertedCount: number;
  updatedCount: number;
  skippedCount: number;
  conflictCount: number;
  errorMessage: string | null;
};

export type FeatureDistributionBin = {
  label: string;
  count: number;
  rate: number;
};

export type FeatureDistribution = {
  featureKey: string;
  label: string;
  totalCount: number;
  bins: FeatureDistributionBin[];
};

export type TrainingResult = {
  config: Record<string, number>;
  as_of_issue: string;
  history_fingerprint: string;
  config_hash: string;
  evaluated_draws: number;
  top_100_hits: number;
  top_1000_hits: number;
  top_10000_hits: number;
  median_rank: number;
  best_rank: number;
  worst_rank: number;
  red5: TrainingRedFiveSummary;
  rank_quality: TrainingRankQualitySummary;
  run_key: string;
  reward: TrainingRewardSummary;
  frozen_validation: Record<string, unknown> | null;
};

export type TrainingRankQualitySummary = {
  top_50000_hits: number;
  top_100000_hits: number;
  top_250000_hits: number;
  top_500000_hits: number;
  p90_rank: number | null;
  p95_rank: number | null;
  tail_over_750000_count: number;
  tail_over_900000_count: number;
  tail_over_1000000_count: number;
  worst_rank_reward: number;
  median_rank_reward: number;
  band_reward: number;
  tail_risk_penalty: number;
  reward: number;
};

export type TrainingRedFiveSummary = {
  top_100_hits: number;
  top_1000_hits: number;
  top_10000_hits: number;
  median_rank: number | null;
  best_rank: number | null;
  missing_counts: Record<string, number>;
  extra_counts: Record<string, number>;
  pairs: TrainingRedFivePair[];
  examples: TrainingRedFiveExample[];
};

export type TrainingRedFivePair = {
  missing_number: number;
  extra_number: number;
  count: number;
};

export type TrainingRedFiveExample = {
  issue: string;
  rank: number;
  score: number | null;
  numbers: number[];
  missing_number: number;
  extra_number: number;
};

export type TrainingRewardSummary = {
  hitReward: number;
  red5Reward: number;
  rankQualityReward: number;
  rankPenalty: number;
  tailRiskPenalty: number;
  objectiveScore: number;
};

export type TrainingRoundSummary = {
  round: number;
  phase: string;
  step: number;
  generated_config_count: number | null;
  config_count: number;
  prefilter: TrainingPrefilterRun | null;
  improved: boolean;
  best: TrainingResult | null;
  topResults: TrainingResult[];
};

export type TrainingTargetResult = {
  issue: string;
  drawDate: string | null;
  redNumbers: number[];
  rank: number;
  score: number | null;
  hitTop100: boolean;
  hitTop1000: boolean;
  hitTop10000: boolean;
  red5Rank: number | null;
  red5Score: number | null;
  red5Numbers: number[];
  red5MissingNumber: number | null;
  red5ExtraNumber: number | null;
  hitRed5Top100: boolean;
  hitRed5Top1000: boolean;
  hitRed5Top10000: boolean;
};

export type TrainingRoundListItem = {
  runId: string;
  roundIndex: number;
  phase: string;
  step: number;
  trainMode: string;
  trainWindow: number;
  evalWindow: number;
  topN: number;
  asOfIssue: string;
  improved: boolean;
  top100Hits: number;
  top1000Hits: number;
  top10000Hits: number;
  red5Top100Hits: number;
  red5Top1000Hits: number;
  red5Top10000Hits: number;
  medianRank: number | null;
  bestRank: number | null;
  worstRank: number | null;
  objectiveScore: number | null;
  createdAt: string;
};

export type TrainingRoundDetail = TrainingRoundListItem & {
  historyFingerprint: string;
  bestConfig: Record<string, number>;
  bestSummary: TrainingResult | null;
  topResults: TrainingResult[];
  targetResults: TrainingTargetResult[];
  prefilter: TrainingPrefilterRun | null;
};

export type TrainingWeightSignalPoint = {
  issue: string;
  drawDate: string | null;
  baseValue: number;
  closeValue: number;
  issueLowValue: number;
  issueHighValue: number;
  rollingLowValue: number;
  rollingHighValue: number;
  rsv: number;
  kValue: number;
  dValue: number;
  jValue: number;
  recommendedOffset: number;
  bestObjectiveScore: number;
  objectiveDelta: number;
  sampleCount: number;
};

export type TrainingWeightSignalSeries = {
  signalRunId: string;
  weightName: string;
  source: string;
  trainMode: string;
  trainWindow: number;
  evalWindow: number;
  topN: number;
  points: TrainingWeightSignalPoint[];
};

export type ServiceStatusLevel = 'ok' | 'warning' | 'failed' | 'unknown';

export type ServiceStatusName = 'api' | 'web' | 'db' | 'sync' | 'kdj' | 'training';

export type ServiceStatusItem = {
  name: ServiceStatusName;
  label: string;
  status: ServiceStatusLevel;
  pid: number | null;
  processAlive: boolean | null;
  heartbeatAt: string | null;
  heartbeatAgeSeconds: number | null;
  lastStartedAt: string | null;
  lastFinishedAt: string | null;
  recentError: string | null;
  logFile: string | null;
  metrics: Record<string, unknown>;
};

export type HeavyTaskLimits = {
  cpuCount: number;
  defaultWorkers: number;
  recommendedInteractiveMax: number;
  activeTrainingWorkers: number | null;
};

export type ServiceStatusPayload = {
  generatedAt: string;
  overall: ServiceStatusLevel;
  services: ServiceStatusItem[];
  heavyTaskLimits: HeavyTaskLimits;
};

export type SsqHistorySummary = {
  tablePresent: boolean;
  totalDraws: number;
  minDrawDate: string | null;
  maxDrawDate: string | null;
  latestIssue: string | null;
  latestDrawDate: string | null;
  latestCreatedAt: string | null;
};

export type TrainingWeightSignalSummary = {
  tablePresent: boolean;
  totalRows: number;
  latestSignalRunId: string | null;
  latestIssue: string | null;
  latestDrawDate: string | null;
  latestCreatedAt: string | null;
  weights: string[];
};

export type TrainingProgress = {
  loggedAt: string;
  round: number;
  targetIndex: number;
  targetTotal: number;
  issue: string;
  trainDraws: number;
  elapsedSeconds: number;
};

export type TrainingStatusPayload = {
  status: string;
  active: boolean;
  processAlive: boolean | null;
  runId: string | null;
  startedAt: string | null;
  updatedAt: string | null;
  deadline: string | null;
  pid: number | null;
  historyScope: string | null;
  regimeYears: number | null;
  regimeStartDate: string | null;
  trainMode: string | null;
  trainWindow: number | null;
  evalWindow: number | null;
  topN: number | null;
  workers: number | null;
  memoryBudgetGb: number | null;
  universeSize: number | null;
  matrixBackend: string | null;
  featureMatrixCache: TrainingMatrixCache | null;
  red5RankMode: string | null;
  prefilter: TrainingPrefilterStatus | null;
  qianKun: TrainingQianKunSummary;
  completedRounds: number;
  rounds: TrainingRoundSummary[];
  latestRound: TrainingRoundSummary | null;
  recentRounds: TrainingRoundSummary[];
  best: TrainingResult | null;
  latestProgress: TrainingProgress | null;
  statusFile: string | null;
  reportFile: string | null;
  logFile: string | null;
  serviceUnit: string | null;
  logTail: string[];
  syncSchedule: {
    timezone: string;
    cron: string;
    description: string;
  };
};

export type TrainingMatrixCache = {
  backend: string | null;
  cacheKey: string | null;
  cachePath: string | null;
  cacheHit: boolean | null;
  buildSeconds: number | null;
  sourceCount: number | null;
  filteredCount: number | null;
  excludedCount: number | null;
  red5RankMode: string | null;
};

export type TrainingPrefilterRun = {
  mode: string | null;
  round: number | null;
  targetStride: number | null;
  targetCount: number | null;
  targetWorkerCount: number | null;
  generatedConfigCount: number | null;
  keptConfigCount: number | null;
  promoteLimit: number | null;
  diversityQuota: number | null;
  diversityAddedCount: number | null;
  stagnationRounds: number | null;
  lowCoverageFields: string[];
  candidateBudget: Record<string, number>;
  frozenValidationWindow: number | null;
  controlExperiments: Record<string, unknown>[];
  refinedConfigCount: number | null;
  elapsedSeconds: number | null;
  note: string | null;
};

export type TrainingPrefilterStatus = {
  mode: string | null;
  description: string | null;
  latest: TrainingPrefilterRun | null;
};

export type TrainingQianKunSummary = {
  total_draws: number;
  recent_window: number;
  latest_issue: string;
  latest_numbers: number[];
  latest_pattern: string;
  latest_label: string;
  latest_icon: string;
  latest_lines: string[];
  qian_count: number;
  kun_count: number;
  patterns: TrainingQianKunPattern[];
};

export type TrainingQianKunPattern = {
  pattern: string;
  label: string;
  icon: string;
  lines: string[];
  count: number;
  rate: number;
  recent_count: number;
  recent_rate: number;
};

export type DashboardPayload = {
  experiments: ExperimentSummary[];
  pipelineRuns: PipelineRunSummary[];
  syncRuns: SyncRunSummary[];
  featureDistributions: FeatureDistribution[];
  trainingStatus: TrainingStatusPayload;
};

export interface ResearchRepository {
  listExperiments(limit: number): Promise<ExperimentSummary[]>;
  getExperimentDetail(experimentKey: string): Promise<ExperimentDetail | null>;
  listPipelineRuns(limit: number): Promise<PipelineRunSummary[]>;
  listSyncRuns(limit: number): Promise<SyncRunSummary[]>;
  listFeatureDistributions(): Promise<FeatureDistribution[]>;
  listTrainingRounds(limit: number): Promise<TrainingRoundListItem[]>;
  getTrainingRoundDetail(runId: string, roundIndex: number): Promise<TrainingRoundDetail | null>;
  listTrainingWeightSignals(
    signalRunId: string | null,
    weights: string[],
    limit: number,
  ): Promise<TrainingWeightSignalSeries[]>;
  getSsqHistorySummary(): Promise<SsqHistorySummary>;
  getTrainingWeightSignalSummary(): Promise<TrainingWeightSignalSummary>;
}
