export interface ResearchDecisionRecord {
  key: string;
  requestKey: string;
  status: string;
  proposedStatus: string;
  hypothesisKey: string;
  evidenceIds: unknown[];
  payload: Record<string, unknown>;
  executionResult: Record<string, unknown>;
  createdAt: string;
  resolvedAt: string | null;
}

export interface ResearchDecisionReadRepository {
  listDecisions(limit: number, offset: number): Promise<ResearchDecisionRecord[]>;
  getDecision(key: string): Promise<ResearchDecisionRecord | null>;
  reviewStatus(): Promise<{ pending: number; completed: number; rejected: number }>;
}
