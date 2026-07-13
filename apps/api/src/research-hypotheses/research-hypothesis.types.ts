export type RegistryEntity =
  | 'hypothesis_family'
  | 'hypothesis'
  | 'hypothesis_experiment'
  | 'hypothesis_evidence'
  | 'hypothesis_decision';

export type RegistryQuery = {
  status?: string;
  familyKey?: string;
  createdAfter?: Date;
  createdBefore?: Date;
  limit: number;
  offset: number;
};

export type HypothesisFamilyRecord = {
  id: number;
  familyKey: string;
  title: string;
  description: string;
  mechanism: string;
  status: string;
  rejectionScope: string;
  rejectionReason: string | null;
  reopenCondition: string | null;
  createdAt: string;
  updatedAt: string;
  resolvedAt: string | null;
  metadata: Record<string, unknown>;
};

export type HypothesisRecord = {
  id: number;
  hypothesisKey: string;
  familyId: number;
  familyKey: string;
  parentHypothesisId: number | null;
  title: string;
  statement: string;
  mechanism: string;
  nullHypothesis: string;
  minimalNonNull: string;
  invariants: unknown[];
  baselineDefinition: Record<string, unknown>;
  metricDefinition: Record<string, unknown>;
  failureCondition: Record<string, unknown>;
  selfDeceptionRisk: unknown[];
  status: string;
  rejectionScope: string;
  rejectionReason: string | null;
  reopenCondition: string | null;
  createdAt: string;
  updatedAt: string;
  preregisteredAt: string | null;
  startedAt: string | null;
  resolvedAt: string | null;
  metadata: Record<string, unknown>;
};

export type HypothesisExperimentRecord = {
  id: number;
  hypothesisId: number;
  experimentKey: string;
  experimentType: string;
  externalRunId: string | null;
  trainingRunId: string | null;
  trainingRoundIndex: number | null;
  reportPath: string | null;
  artifactPaths: unknown[];
  configSnapshot: Record<string, unknown>;
  status: string;
  startedAt: string | null;
  completedAt: string | null;
  createdAt: string;
  metadata: Record<string, unknown>;
};

export type HypothesisEvidenceRecord = {
  id: number;
  hypothesisId: number;
  experimentId: number | null;
  evidenceType: string;
  direction: string;
  summary: string;
  metrics: Record<string, unknown>;
  artifactPath: string | null;
  contentHash: string | null;
  observedAt: string;
  createdAt: string;
  metadata: Record<string, unknown>;
};

export type HypothesisDecisionRecord = {
  id: number;
  hypothesisId: number;
  previousStatus: string;
  newStatus: string;
  decisionCode: string;
  summary: string;
  reason: Record<string, unknown>;
  evidenceIds: unknown[];
  decidedBy: string;
  decidedAt: string;
  createdAt: string;
};

export interface HypothesisReadRepository {
  listFamilies(query: RegistryQuery): Promise<HypothesisFamilyRecord[]>;
  getFamily(familyKey: string): Promise<HypothesisFamilyRecord | null>;
  listHypotheses(query: RegistryQuery): Promise<HypothesisRecord[]>;
  getHypothesis(hypothesisKey: string): Promise<HypothesisRecord | null>;
  listExperiments(hypothesisKey: string, query: RegistryQuery): Promise<HypothesisExperimentRecord[]>;
  listEvidence(hypothesisKey: string, query: RegistryQuery): Promise<HypothesisEvidenceRecord[]>;
  listDecisions(hypothesisKey: string, query: RegistryQuery): Promise<HypothesisDecisionRecord[]>;
}
