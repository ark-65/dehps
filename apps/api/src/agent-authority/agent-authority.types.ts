export type AgentRequestQuery = {
  status?: string;
  requestType?: string;
  requestedByRole?: string;
  riskLevel?: string;
  createdAfter?: Date;
  createdBefore?: Date;
  limit: number;
  offset: number;
};

export type AgentRequestRecord = {
  id: number;
  requestKey: string;
  requestType: string;
  requestedByRole: string;
  requestedBy: string;
  hypothesisId: number | null;
  experimentId: number | null;
  parentRequestId: number | null;
  title: string;
  summary: string;
  payload: Record<string, unknown>;
  status: string;
  riskLevel: string;
  requiresReview: boolean;
  createdAt: string;
  updatedAt: string;
  submittedAt: string | null;
  resolvedAt: string | null;
  metadata: Record<string, unknown>;
};

export type AgentRequestDecisionRecord = {
  id: number;
  requestId: number;
  previousStatus: string;
  newStatus: string;
  decisionCode: string;
  summary: string;
  reason: Record<string, unknown>;
  decidedByRole: string;
  decidedBy: string;
  decidedAt: string;
  createdAt: string;
};

export type AgentRequestExecutionRecord = {
  id: number;
  requestId: number;
  executorRole: string;
  executorId: string;
  executionType: string;
  status: string;
  environment: string;
  runId: string | null;
  startedAt: string;
  completedAt: string | null;
  result: Record<string, unknown>;
  artifactPaths: unknown[];
  error: Record<string, unknown>;
  createdAt: string;
};

export interface AgentRequestReadRepository {
  listRequests(query: AgentRequestQuery): Promise<AgentRequestRecord[]>;
  getRequest(requestKey: string): Promise<AgentRequestRecord | null>;
  listDecisions(requestKey: string): Promise<AgentRequestDecisionRecord[]>;
  listExecutions(requestKey: string): Promise<AgentRequestExecutionRecord[]>;
}
