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
  config_count: number;
  improved: boolean;
  best: TrainingResult | null;
  topResults: TrainingResult[];
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

export type TrainingQianKunSummary = {
  total_draws: number;
  recent_window: number;
  latest_issue: string;
  latest_numbers: number[];
  latest_pattern: string;
  latest_label: string;
  latest_lines: string[];
  qian_count: number;
  kun_count: number;
  patterns: TrainingQianKunPattern[];
};

export type TrainingQianKunPattern = {
  pattern: string;
  label: string;
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
}
