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

export type CombinationDistribution = {
  retainedCount: number;
  rejectedCount: number;
  retainedRate: number;
  rejectedRate: number;
};

export function percent(value: number): string {
  return `${(value * 100).toFixed(2)}%`;
}

export function combinationDistribution(experiment: ExperimentSummary): CombinationDistribution {
  const rejectedCount = experiment.totalCombinations - experiment.keptCombinations;
  const rejectedRate = 1 - experiment.keepRate;
  return {
    retainedCount: experiment.keptCombinations,
    rejectedCount,
    retainedRate: experiment.keepRate,
    rejectedRate,
  };
}

export function latestStatus(payload: Pick<DashboardPayload, 'pipelineRuns'>): string {
  const latestPipeline = payload.pipelineRuns[0];
  if (!latestPipeline) {
    return '暂无流水线记录';
  }
  if (latestPipeline.status === 'success') {
    return '流水线正常';
  }
  if (latestPipeline.status === 'failed') {
    return '流水线失败';
  }
  return `流水线状态：${latestPipeline.status}`;
}

export function reportStatus(detail: ExperimentDetail | null): string {
  if (!detail) {
    return '请选择实验';
  }
  return detail.reportMarkdown ? '报告已生成' : '暂无报告';
}

export type ExperimentComparison = {
  primary: ExperimentSummary;
  comparison: ExperimentSummary | null;
  keepRateDelta: number | null;
  coverageRateDelta: number | null;
  liftDelta: number | null;
};

export function compareExperiments(
  primary: ExperimentSummary | null,
  comparison: ExperimentSummary | null,
): ExperimentComparison | null {
  if (!primary) {
    return null;
  }
  if (!comparison) {
    return {
      primary,
      comparison: null,
      keepRateDelta: null,
      coverageRateDelta: null,
      liftDelta: null,
    };
  }
  return {
    primary,
    comparison,
    keepRateDelta: primary.keepRate - comparison.keepRate,
    coverageRateDelta: primary.coverageRate - comparison.coverageRate,
    liftDelta: primary.lift - comparison.lift,
  };
}

export function signedPercent(value: number | null): string {
  if (value === null) {
    return '无';
  }
  const sign = value > 0 ? '+' : '';
  return `${sign}${percent(value)}`;
}

export function signedNumber(value: number | null): string {
  if (value === null) {
    return '无';
  }
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(4)}`;
}

export function trainingStatusText(status: TrainingStatusPayload): string {
  if (status.active) {
    return '训练运行中';
  }
  if (status.status === 'completed') {
    return '训练已完成';
  }
  if (status.status === 'failed') {
    return '训练失败';
  }
  if (status.status === 'not_started') {
    return '训练未启动';
  }
  return `训练状态：${status.status}`;
}

export function phaseText(phase: string | null | undefined): string {
  const labels: Record<string, string> = {
    micro: '微权重',
    small: '小权重',
    medium: '中权重',
    large: '大权重',
  };
  return phase ? labels[phase] ?? phase : '无';
}

export function trainModeText(mode: string | null): string {
  if (mode === 'expanding') {
    return '扩展窗口回归';
  }
  if (mode === 'rolling') {
    return '滚动窗口回归';
  }
  return mode || '无';
}

export function hitRate(hits: number, evaluatedDraws: number): string {
  if (!evaluatedDraws) {
    return '0.00%';
  }
  return percent(hits / evaluatedDraws);
}

export function progressRate(progress: TrainingProgress | null): number {
  if (!progress || !progress.targetTotal) {
    return 0;
  }
  return Math.min(Math.max(progress.targetIndex / progress.targetTotal, 0), 1);
}
