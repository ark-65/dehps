export type ExperimentSummary = {
  experimentKey: string;
  strategyKey: string;
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

export type DashboardPayload = {
  experiments: ExperimentSummary[];
  pipelineRuns: PipelineRunSummary[];
  syncRuns: SyncRunSummary[];
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
