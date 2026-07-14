export interface ResearchExecutionRunRecord {
  id: string;
  requestKey: string;
  requestStatus: string;
  executionId: number | null;
  executionStatus: string | null;
  runId: string | null;
  planKey: string;
  planFingerprint: string;
  experimentKey: string;
  environment: string;
  productionAccess: boolean;
  startedAt: string | null;
  completedAt: string | null;
  artifactPaths: unknown[];
  result: Record<string, unknown>;
  error: Record<string, unknown>;
}

export interface ResearchExecutionReadRepository {
  listRuns(limit: number, offset: number): Promise<ResearchExecutionRunRecord[]>;
  getRun(id: string): Promise<ResearchExecutionRunRecord | null>;
  latestRun(): Promise<ResearchExecutionRunRecord | null>;
  countRuns(): Promise<{ total: number; completed: number; failed: number; running: number }>;
}
