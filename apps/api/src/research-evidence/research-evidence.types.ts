export interface ResearchEvidenceRecord {
  id: number;
  evidenceKey: string;
  hypothesisKey: string;
  experimentKey: string | null;
  evidenceType: string;
  direction: string;
  summary: string;
  metrics: Record<string, unknown>;
  artifactPath: string | null;
  contentHash: string | null;
  observedAt: string;
  createdAt: string;
  metadata: Record<string, unknown>;
}

export interface ResearchEvidenceReadRepository {
  listEvidence(limit: number, offset: number): Promise<ResearchEvidenceRecord[]>;
  getEvidence(key: string): Promise<ResearchEvidenceRecord | null>;
  countEvidence(): Promise<number>;
}
