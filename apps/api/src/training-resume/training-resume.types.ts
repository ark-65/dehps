export interface TrainingResumeAttemptRecord {
  id: number;
  attemptKey: string;
  eventKey: string | null;
  decision: string;
  reasonCode: string;
  oldRunId: string | null;
  newRunId: string | null;
  startedAt: string;
  completedAt: string | null;
  result: Record<string, unknown>;
}

export interface TrainingResumeStatusRecord {
  latestAttempt: TrainingResumeAttemptRecord | null;
  retryableEventCount: number;
}

export interface TrainingResumeReadRepository {
  history(limit: number, offset: number): Promise<TrainingResumeAttemptRecord[]>;
  status(): Promise<TrainingResumeStatusRecord>;
}
