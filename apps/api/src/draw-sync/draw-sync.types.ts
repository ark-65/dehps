export interface DrawSyncRunRecord {
  id: number;
  runKey: string;
  startedAt: string;
  completedAt: string | null;
  status: string;
  previousLatestIssue: string | null;
  currentLatestIssue: string | null;
  insertedIssues: unknown[];
  updatedIssues: unknown[];
  auditPassed: boolean;
  fingerprintBefore: string | null;
  fingerprintAfter: string | null;
  eventKey: string | null;
  warnings: unknown[];
  error: Record<string, unknown>;
  metadata: Record<string, unknown>;
}

export interface DrawIssueEventRecord {
  id: number;
  eventKey: string;
  previousIssue: string;
  newIssue: string;
  historyFingerprint: string;
  auditReportHash: string;
  source: string;
  status: string;
  syncedAt: string;
  consumedAt: string | null;
  consumerRunId: string | null;
  createdAt: string;
  metadata: Record<string, unknown>;
}

export interface DrawSyncStatusRecord {
  latestRun: DrawSyncRunRecord | null;
  latestEvent: DrawIssueEventRecord | null;
  pendingEventCount: number;
}

export interface DrawSyncReadRepository {
  listRuns(limit: number, offset: number): Promise<DrawSyncRunRecord[]>;
  listEvents(limit: number, offset: number): Promise<DrawIssueEventRecord[]>;
  status(): Promise<DrawSyncStatusRecord>;
}
