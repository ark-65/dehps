export interface EngineeringContractRecord {
  requestKey: string;
  status: string;
  requestedBy: string;
  title: string;
  hypothesisKey: string | null;
  experimentKey: string | null;
  experimentPlanKey: string | null;
  planFingerprint: string | null;
  mechanism: string | null;
  productionImpact: string | null;
  payload: Record<string, unknown>;
  metadata: Record<string, unknown>;
  createdAt: string;
  submittedAt: string | null;
}

export interface EngineeringPlanRecord {
  planKey: string;
  hypothesisKey: string;
  hypothesisStatus: string;
  planFingerprint: string | null;
  mechanism: string | null;
  plan: Record<string, unknown>;
  metadata: Record<string, unknown>;
}

export interface EngineeringReadRepository {
  listContracts(limit: number, offset: number): Promise<EngineeringContractRecord[]>;
  latestPlan(): Promise<EngineeringPlanRecord | null>;
  countContracts(): Promise<number>;
  countPlans(): Promise<number>;
}
