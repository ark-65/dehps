import { DrawIssueEventRecord } from '../draw-sync/draw-sync.types';
import { TrainingResumeAttemptRecord } from '../training-resume/training-resume.types';

export interface ForwardStateRecord {
  latestIssue: string | null;
  pendingEvent: DrawIssueEventRecord | null;
  consumedForwardCount: number;
  latestTrainingResumeAttempt: TrainingResumeAttemptRecord | null;
}

export interface ForwardStateReadRepository {
  status(): Promise<ForwardStateRecord>;
}
