export interface ResearchSchedulerQueueRecord {
  id: number;
  queueKey: string;
  queueStatus: string;
  action: string;
  priorityScore: number;
  targetHypothesisKey: string | null;
  targetFamilyKey: string | null;
  targetExperimentKey: string | null;
  requestKey: string | null;
  requestStatus: string | null;
  contextFingerprint: string;
  reason: Record<string, unknown>;
  budget: Record<string, unknown>;
  policy: Record<string, unknown>;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
  completedAt: string | null;
  metadata: Record<string, unknown>;
}

export interface ResearchSchedulerReadRepository {
  listQueue(limit: number, offset: number): Promise<ResearchSchedulerQueueRecord[]>;
  latestQueueItem(): Promise<ResearchSchedulerQueueRecord | null>;
  countOpenQueue(): Promise<number>;
  countSchedulerRequests(): Promise<number>;
}
