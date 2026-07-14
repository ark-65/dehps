import assert from 'node:assert/strict';
import { test } from 'node:test';
import { BadRequestException, NotFoundException } from '@nestjs/common';
import { mapCycle, mapFeature, mapPattern, mapStrategy } from '../src/pattern-discovery/pattern-discovery.repository';
import { PatternDiscoveryReadService } from '../src/pattern-discovery/pattern-discovery.service';
import {
  PatternCycleRecord,
  PatternDiscoveryReadRepository,
  PatternFamilyRecord,
  PatternRecord,
  SynthesizedFeatureRecord,
  SynthesizedStrategyRecord,
} from '../src/pattern-discovery/pattern-discovery.types';

const pattern: PatternRecord = {
  patternKey: 'pattern-1',
  patternFamily: 'arithmetic_spacing',
  patternType: 'arithmetic_progression_len_3',
  lifecycleStatus: 'discovered',
  formulaHash: 'hash',
  historyFingerprint: 'history',
  legalUniverseFingerprint: 'legal',
  searchIssueRange: { start: '001', end: '010' },
  formula: { operator: 'contains_arithmetic_progression' },
  parameters: { length: 3 },
  pattern: { pattern_key: 'pattern-1' },
  parentPatternKey: null,
  multiplicityFamily: 'arithmetic_progression_len_3',
  generatorVersion: 'v1',
  codeCommit: 'commit',
  createdAt: '2026-07-14T00:00:00.000Z',
  updatedAt: '2026-07-14T00:00:00.000Z',
  metadata: {},
};

const family: PatternFamilyRecord = {
  patternFamily: 'arithmetic_spacing',
  patternCount: 1,
  supportedCount: 0,
  rejectedCount: 0,
};

const feature: SynthesizedFeatureRecord = {
  featureKey: 'feature-1',
  patternKey: 'pattern-1',
  formulaHash: 'feature-hash',
  feature: { execution_mode: 'declarative' },
  createdAt: '2026-07-14T00:00:00.000Z',
};

const strategy: SynthesizedStrategyRecord = {
  strategyKey: 'strategy-1',
  featureKey: 'feature-1',
  strategyType: 'single_feature_rank',
  strategy: { production_impact: 'none' },
  createdAt: '2026-07-14T00:00:00.000Z',
};

const cycle: PatternCycleRecord = {
  cycleKey: 'cycle-1',
  status: 'completed',
  searchIssueRange: {},
  budget: {},
  discoveredCount: 1,
  acceptedCount: 1,
  result: {},
  createdAt: '2026-07-14T00:00:00.000Z',
};

function repository(hasPattern = true): PatternDiscoveryReadRepository {
  return {
    async listPatterns() { return [pattern]; },
    async getPattern() { return hasPattern ? pattern : null; },
    async listFamilies() { return [family]; },
    async listFeatures() { return [feature]; },
    async listStrategies() { return [strategy]; },
    async listCycles() { return [cycle]; },
    async status() { return { pattern_count: 1, feature_count: 1, strategy_count: 1, cycle_count: 1 }; },
  };
}

test('pattern discovery service exposes read-only records and status', async () => {
  const service = new PatternDiscoveryReadService(repository());

  const patterns = await service.patterns(25, 2);
  const found = await service.pattern('pattern-1');
  const families = await service.families();
  const features = await service.features();
  const strategies = await service.strategies();
  const cycles = await service.cycles();
  const status = await service.status();

  assert.equal(patterns.items[0].patternKey, 'pattern-1');
  assert.equal(found.writeRoutesEnabled, false);
  assert.equal(families.items[0].patternFamily, 'arithmetic_spacing');
  assert.equal(features.items[0].featureKey, 'feature-1');
  assert.equal(strategies.items[0].strategyType, 'single_feature_rank');
  assert.equal(cycles.items[0].cycleKey, 'cycle-1');
  assert.equal(status.writeRoutesEnabled, false);
  assert.equal(status.productionAccess, false);
});

test('pattern discovery service rejects invalid pagination and missing pattern', async () => {
  await assert.rejects(() => new PatternDiscoveryReadService(repository()).patterns(0, 0), BadRequestException);
  await assert.rejects(() => new PatternDiscoveryReadService(repository()).features(10, -1), BadRequestException);
  await assert.rejects(() => new PatternDiscoveryReadService(repository(false)).pattern('missing'), NotFoundException);
});

test('postgres pattern discovery mappers normalize json payloads', () => {
  const mappedPattern = mapPattern({
    pattern_key: 'pattern-1',
    pattern_family: 'arithmetic_spacing',
    pattern_type: 'arithmetic_progression_len_3',
    lifecycle_status: 'discovered',
    formula_hash: 'hash',
    history_fingerprint: 'history',
    legal_universe_fingerprint: 'legal',
    search_issue_range_json: { start: '001' },
    formula_json: { operator: 'op' },
    parameters_json: { length: 3 },
    pattern_json: { pattern_key: 'pattern-1' },
    parent_pattern_key: null,
    multiplicity_family: 'ap3',
    generator_version: 'v1',
    code_commit: 'commit',
    created_at: new Date('2026-07-14T00:00:00Z'),
    updated_at: new Date('2026-07-14T00:00:00Z'),
    metadata_json: {},
  });
  const mappedFeature = mapFeature({
    feature_key: 'feature-1',
    pattern_key: 'pattern-1',
    formula_hash: 'hash',
    feature_json: { execution_mode: 'declarative' },
    created_at: new Date('2026-07-14T00:00:00Z'),
  });
  const mappedStrategy = mapStrategy({
    strategy_key: 'strategy-1',
    feature_key: 'feature-1',
    strategy_type: 'single_feature_rank',
    strategy_json: { production_impact: 'none' },
    created_at: new Date('2026-07-14T00:00:00Z'),
  });
  const mappedCycle = mapCycle({
    cycle_key: 'cycle-1',
    status: 'completed',
    search_issue_range_json: {},
    budget_json: {},
    discovered_count: 1,
    accepted_count: 1,
    result_json: {},
    created_at: new Date('2026-07-14T00:00:00Z'),
  });

  assert.equal(mappedPattern.formula.operator, 'op');
  assert.equal(mappedFeature.feature.execution_mode, 'declarative');
  assert.equal(mappedStrategy.strategy.production_impact, 'none');
  assert.equal(mappedCycle.discoveredCount, 1);
});
