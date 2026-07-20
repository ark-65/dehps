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

export type EvidenceState =
  | 'verified'
  | 'warning'
  | 'stale'
  | 'missing'
  | 'failed'
  | 'not_applicable'
  | 'not_defined';

export type DashboardEvidence = {
  key: string;
  label: string;
  state: EvidenceState;
  summary: string;
  source: string | null;
  observedAt: string | null;
  freshUntil: string | null;
  scope: string;
  metrics: Record<string, unknown>;
};

export type RuntimeDashboardPayload = {
  generatedAt: string;
  milestone: { key: 'M1'; label: string; state: 'accepted'; source: string };
  capabilityStatus: EvidenceState;
  operationalStatus: ServiceStatusLevel;
  capabilities: DashboardEvidence[];
  operations: DashboardEvidence[];
  services: ServiceStatusPayload;
  guardrail: string;
};

export type ResearchDashboardPayload = {
  generatedAt: string;
  milestone: { key: 'M2'; label: string; state: 'active'; source: string };
  qualityStatus: EvidenceState;
  processStatus: EvidenceState;
  quality: DashboardEvidence[];
  process: DashboardEvidence[];
  expectedValue: DashboardEvidence;
  guardrail: string;
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
  rankMovement: TrainingRankMovementSummary | null;
  improved: boolean;
  best: TrainingResult | null;
  topResults: TrainingResult[];
};

export type TrainingRankMovementSummary = {
  comparedToRound: number | null;
  comparedTargetCount: number;
  changedTargetCount: number;
  medianChangedAbsDelta: number | null;
  maxAbsDelta: number | null;
  sameRankVector: boolean | null;
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
  bestRankQuality: TrainingRankQualitySummary | null;
  prefilter: TrainingPrefilterRun | null;
  rankMovement: TrainingRankMovementSummary | null;
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

export type TrainingNextCandidate = {
  rank: number;
  redNumbers: number[];
  score: number;
};

export type TrainingNextCandidatesPayload = {
  status: 'ready' | 'empty';
  lineKey: string;
  lineLabel: string | null;
  lineKind: string | null;
  snapshotKey: string | null;
  runId: string | null;
  sourceRoundIndex: number | null;
  asOfIssue: string | null;
  nextIssue: string | null;
  nextDrawDate: string | null;
  trainMode: string | null;
  trainWindow: number | null;
  evalWindow: number | null;
  topN: number | null;
  historyFingerprint: string | null;
  configHash: string | null;
  config: Record<string, number>;
  predictionMetadata: Record<string, unknown>;
  generatedAt: string | null;
  totalCount: number;
  candidates: TrainingNextCandidate[];
  guardrail: string;
};

export type TrainingAdvisorSource =
  | 'weight_kdj_advisor'
  | 'ridge_kdj_advisor'
  | 'neural_kdj_advisor'
  | 'target_weight_inversion_advisor';

export type TrainingAdvisorAdviceRow = {
  weightName: string;
  latestIssue: string | null;
  suggestedOffset: number | null;
  confidence: number | null;
  validationMetric: number | null;
  baselineMetric: number | null;
  configHash: string | null;
  decision: string | null;
  reason: string | null;
  source: string | null;
};

export type TrainingAdvisorSummary = {
  source: TrainingAdvisorSource;
  enabled: boolean;
  status: string | null;
  mode: string | null;
  budget: number | null;
  candidateCount: number | null;
  selectedCount: number | null;
  downweightedCount: number | null;
  rejectedCount: number | null;
  fieldCount: number | null;
  fields: string[];
  latestSignalIssue: string | null;
  signalRunId: string | null;
  advice: TrainingAdvisorAdviceRow[];
  controlVerdict: Record<string, unknown> | string | null;
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
  heavyJobLock: Record<string, unknown> | null;
};

export type ServiceStatusPayload = {
  generatedAt: string;
  overall: ServiceStatusLevel;
  services: ServiceStatusItem[];
  heavyTaskLimits: HeavyTaskLimits;
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
  advisorSummaries: TrainingAdvisorSummary[];
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
  phaseStage: string | null;
  searchBaseMinDistance: number | null;
  searchBaseStart: TrainingSearchBaseSummary | null;
  searchBase: TrainingSearchBaseSummary | null;
  frozenValidationWindow: number | null;
  controlExperiments: Record<string, unknown>[];
  refinedConfigCount: number | null;
  elapsedSeconds: number | null;
  note: string | null;
};

export type TrainingSearchBaseSummary = {
  source: string | null;
  changed: boolean;
  previousConfigHash: string;
  configHash: string;
  candidateConfigHash: string;
  minConfigDistance: number | null;
  selectedConfigDistance: number | null;
  searchChallengerConfigDistance: number | null;
  searchChallengerRankVectorChanged: boolean | null;
  recentSearchBaseHashes: string[];
  top_100_hits: number;
  top_1000_hits: number;
  top_10000_hits: number;
  median_rank: number | null;
  best_rank: number | null;
  worst_rank: number | null;
  rank_quality: TrainingRankQualitySummary;
  reward: TrainingRewardSummary | null;
  config: Record<string, number>;
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

export function serviceStatusLabel(status: ServiceStatusLevel): string {
  const labels: Record<ServiceStatusLevel, string> = {
    ok: '正常',
    warning: '警告',
    failed: '失败',
    unknown: '未知',
  };
  return labels[status];
}

export function serviceStatusSeverity(status: ServiceStatusLevel): number {
  const severity: Record<ServiceStatusLevel, number> = {
    failed: 3,
    warning: 2,
    unknown: 1,
    ok: 0,
  };
  return severity[status];
}

export function advisorSourceLabel(source: TrainingAdvisorSource): string {
  const labels: Record<TrainingAdvisorSource, string> = {
    weight_kdj_advisor: 'KDJ Advisor',
    ridge_kdj_advisor: 'Ridge KDJ Advisor',
    neural_kdj_advisor: 'Neural KDJ Advisor',
    target_weight_inversion_advisor: 'Target Weight Inversion Advisor',
  };
  return labels[source];
}

export function advisorVerdictText(verdict: TrainingAdvisorSummary['controlVerdict']): string {
  if (!verdict) {
    return '无控制结论';
  }
  if (typeof verdict === 'string') {
    return verdict;
  }
  const passed = typeof verdict['passed'] === 'boolean' ? verdict['passed'] : null;
  const status = typeof verdict['status'] === 'string' ? verdict['status'] : null;
  const label = passed === null ? status : passed ? 'PASS' : 'FAIL';
  const reason =
    typeof verdict['language'] === 'string'
      ? verdict['language']
      : typeof verdict['reason'] === 'string'
        ? verdict['reason']
        : null;
  return [label, reason].filter(Boolean).join(' / ') || JSON.stringify(verdict);
}

export function sortedServiceStatuses(payload: ServiceStatusPayload): ServiceStatusItem[] {
  return [...payload.services].sort((left, right) => {
    const severityDelta = serviceStatusSeverity(right.status) - serviceStatusSeverity(left.status);
    return severityDelta || left.name.localeCompare(right.name);
  });
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
