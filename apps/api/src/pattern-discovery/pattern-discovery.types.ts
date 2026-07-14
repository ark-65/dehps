export interface PatternRecord {
  patternKey: string;
  patternFamily: string;
  patternType: string;
  lifecycleStatus: string;
  formulaHash: string;
  historyFingerprint: string;
  legalUniverseFingerprint: string;
  searchIssueRange: Record<string, unknown>;
  formula: Record<string, unknown>;
  parameters: Record<string, unknown>;
  pattern: Record<string, unknown>;
  parentPatternKey: string | null;
  multiplicityFamily: string | null;
  generatorVersion: string;
  codeCommit: string | null;
  createdAt: string;
  updatedAt: string;
  metadata: Record<string, unknown>;
}

export interface PatternFamilyRecord {
  patternFamily: string;
  patternCount: number;
  supportedCount: number;
  rejectedCount: number;
}

export interface SynthesizedFeatureRecord {
  featureKey: string;
  patternKey: string;
  formulaHash: string;
  feature: Record<string, unknown>;
  createdAt: string;
}

export interface SynthesizedStrategyRecord {
  strategyKey: string;
  featureKey: string;
  strategyType: string;
  strategy: Record<string, unknown>;
  createdAt: string;
}

export interface PatternCycleRecord {
  cycleKey: string;
  status: string;
  searchIssueRange: Record<string, unknown>;
  budget: Record<string, unknown>;
  discoveredCount: number;
  acceptedCount: number;
  result: Record<string, unknown>;
  createdAt: string;
}

export interface PatternDiscoveryReadRepository {
  listPatterns(limit: number, offset: number): Promise<PatternRecord[]>;
  getPattern(key: string): Promise<PatternRecord | null>;
  listFamilies(): Promise<PatternFamilyRecord[]>;
  listFeatures(limit: number, offset: number): Promise<SynthesizedFeatureRecord[]>;
  listStrategies(limit: number, offset: number): Promise<SynthesizedStrategyRecord[]>;
  listCycles(limit: number, offset: number): Promise<PatternCycleRecord[]>;
  status(): Promise<Record<string, unknown>>;
}
