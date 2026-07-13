export type ExperimentPlanRecord = {
  planKey: string;
  planVersion: string;
  proposalKey: string;
  hypothesisKey: string;
  familyKey: string;
  mechanism: string;
  planFingerprint: string;
  proposalFingerprint: string;
  hypothesisStatus: string;
  plan: Record<string, any>;
};

export type ExperimentPlanStageRecord = {
  experimentKey: string;
  experimentType: string;
  status: string;
  artifactPaths: unknown[];
  configSnapshot: Record<string, any>;
  metadata: Record<string, any>;
};

export type ExperimentPlanRequestRecord = {
  requestKey: string;
  requestType: string;
  status: string;
  requestedByRole: string;
  requestedBy: string;
  title: string;
  summary: string;
  payload: Record<string, any>;
  metadata: Record<string, any>;
  submittedAt: string | null;
};

export interface ResearchPlanningReadRepository {
  listPlans(limit: number, offset: number): Promise<ExperimentPlanRecord[]>;
  getPlan(key: string): Promise<ExperimentPlanRecord | null>;
  listStages(planKey: string): Promise<ExperimentPlanStageRecord[]>;
  listRequests(planKey: string): Promise<ExperimentPlanRequestRecord[]>;
  latestPlan(): Promise<ExperimentPlanRecord | null>;
}
