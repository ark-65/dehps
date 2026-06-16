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

export type DashboardPayload = {
  experiments: ExperimentSummary[];
  pipelineRuns: PipelineRunSummary[];
  syncRuns: SyncRunSummary[];
  featureDistributions: FeatureDistribution[];
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

export function latestStatus(payload: DashboardPayload): string {
  const latestPipeline = payload.pipelineRuns[0];
  if (!latestPipeline) {
    return 'No pipeline runs';
  }
  if (latestPipeline.status === 'success') {
    return 'Pipeline healthy';
  }
  if (latestPipeline.status === 'failed') {
    return 'Pipeline failed';
  }
  return `Pipeline ${latestPipeline.status}`;
}

export function reportStatus(detail: ExperimentDetail | null): string {
  if (!detail) {
    return 'Select an experiment';
  }
  return detail.reportMarkdown ? 'Report available' : 'No report attached';
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
    return 'N/A';
  }
  const sign = value > 0 ? '+' : '';
  return `${sign}${percent(value)}`;
}

export function signedNumber(value: number | null): string {
  if (value === null) {
    return 'N/A';
  }
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(4)}`;
}
