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
  run_key: string;
  reward: TrainingRewardSummary;
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
  rankPenalty: number;
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
