export type ResearchProposalRecord = {
  requestKey: string;
  requestStatus: string;
  requestedBy: string;
  submittedAt: string | null;
  engineVersion: string;
  contextFingerprint: string;
  proposal: Record<string, any>;
  noveltyReport: Record<string, any>;
  proposalScore: Record<string, any>;
  validationReport: Record<string, any>;
  sourceEvidenceIds: unknown[];
  sourceHypothesisKeys: unknown[];
  sourceTrainingRunIds: unknown[];
};

export interface ResearchAutonomyReadRepository {
  listProposals(limit: number, offset: number): Promise<ResearchProposalRecord[]>;
  getProposal(key: string): Promise<ResearchProposalRecord | null>;
  latestProposal(): Promise<ResearchProposalRecord | null>;
}
