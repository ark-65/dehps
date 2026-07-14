import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { parseDbPort } from '../config';
import {
  PatternCycleRecord,
  PatternDiscoveryReadRepository,
  PatternFamilyRecord,
  PatternRecord,
  SynthesizedFeatureRecord,
  SynthesizedStrategyRecord,
} from './pattern-discovery.types';

type Row = Record<string, any>;

function object(value: unknown): Record<string, unknown> {
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value);
      return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
    } catch {
      return {};
    }
  }
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function iso(value: unknown): string {
  return value instanceof Date ? value.toISOString() : new Date(String(value)).toISOString();
}

@Injectable()
export class PostgresPatternDiscoveryReadRepository
  implements PatternDiscoveryReadRepository, OnModuleDestroy
{
  private readonly pool = new Pool({
    host: process.env.DB_HOST ?? 'localhost',
    port: parseDbPort(process.env.DB_PORT),
    database: process.env.DB_NAME ?? 'dehps',
    user: process.env.DB_USER ?? 'dehps',
    password: process.env.DB_PASSWORD ?? 'dehps_password',
  });

  async onModuleDestroy() {
    await this.pool.end();
  }

  async listPatterns(limit: number, offset: number): Promise<PatternRecord[]> {
    const { rows } = await this.pool.query(
      `SELECT * FROM discovered_patterns ORDER BY created_at DESC, id DESC LIMIT $1 OFFSET $2`,
      [limit, offset],
    );
    return rows.map(mapPattern);
  }

  async getPattern(key: string): Promise<PatternRecord | null> {
    const { rows } = await this.pool.query(`SELECT * FROM discovered_patterns WHERE pattern_key = $1`, [key]);
    return rows[0] ? mapPattern(rows[0]) : null;
  }

  async listFamilies(): Promise<PatternFamilyRecord[]> {
    const { rows } = await this.pool.query(
      `SELECT pattern_family,
              count(*)::int AS pattern_count,
              count(*) FILTER (WHERE lifecycle_status IN ('frozen_supported', 'forward_supported'))::int AS supported_count,
              count(*) FILTER (WHERE lifecycle_status IN ('frozen_rejected', 'forward_rejected'))::int AS rejected_count
       FROM discovered_patterns
       GROUP BY pattern_family
       ORDER BY pattern_family`,
    );
    return rows.map((row) => ({
      patternFamily: String(row.pattern_family),
      patternCount: Number(row.pattern_count),
      supportedCount: Number(row.supported_count),
      rejectedCount: Number(row.rejected_count),
    }));
  }

  async listFeatures(limit: number, offset: number): Promise<SynthesizedFeatureRecord[]> {
    const { rows } = await this.pool.query(
      `SELECT * FROM synthesized_features ORDER BY created_at DESC, id DESC LIMIT $1 OFFSET $2`,
      [limit, offset],
    );
    return rows.map(mapFeature);
  }

  async listStrategies(limit: number, offset: number): Promise<SynthesizedStrategyRecord[]> {
    const { rows } = await this.pool.query(
      `SELECT * FROM synthesized_strategies ORDER BY created_at DESC, id DESC LIMIT $1 OFFSET $2`,
      [limit, offset],
    );
    return rows.map(mapStrategy);
  }

  async listCycles(limit: number, offset: number): Promise<PatternCycleRecord[]> {
    const { rows } = await this.pool.query(
      `SELECT * FROM pattern_search_cycles ORDER BY created_at DESC, id DESC LIMIT $1 OFFSET $2`,
      [limit, offset],
    );
    return rows.map(mapCycle);
  }

  async status(): Promise<Record<string, unknown>> {
    const { rows } = await this.pool.query(
      `SELECT
         (SELECT count(*)::int FROM discovered_patterns) AS pattern_count,
         (SELECT count(*)::int FROM synthesized_features) AS feature_count,
         (SELECT count(*)::int FROM synthesized_strategies) AS strategy_count,
         (SELECT count(*)::int FROM pattern_search_cycles) AS cycle_count`,
    );
    return rows[0] ?? {};
  }
}

export function mapPattern(row: Row): PatternRecord {
  return {
    patternKey: String(row.pattern_key),
    patternFamily: String(row.pattern_family),
    patternType: String(row.pattern_type),
    lifecycleStatus: String(row.lifecycle_status),
    formulaHash: String(row.formula_hash),
    historyFingerprint: String(row.history_fingerprint),
    legalUniverseFingerprint: String(row.legal_universe_fingerprint),
    searchIssueRange: object(row.search_issue_range_json),
    formula: object(row.formula_json),
    parameters: object(row.parameters_json),
    pattern: object(row.pattern_json),
    parentPatternKey: row.parent_pattern_key == null ? null : String(row.parent_pattern_key),
    multiplicityFamily: row.multiplicity_family == null ? null : String(row.multiplicity_family),
    generatorVersion: String(row.generator_version),
    codeCommit: row.code_commit == null ? null : String(row.code_commit),
    createdAt: iso(row.created_at),
    updatedAt: iso(row.updated_at),
    metadata: object(row.metadata_json),
  };
}

export function mapFeature(row: Row): SynthesizedFeatureRecord {
  return {
    featureKey: String(row.feature_key),
    patternKey: String(row.pattern_key),
    formulaHash: String(row.formula_hash),
    feature: object(row.feature_json),
    createdAt: iso(row.created_at),
  };
}

export function mapStrategy(row: Row): SynthesizedStrategyRecord {
  return {
    strategyKey: String(row.strategy_key),
    featureKey: String(row.feature_key),
    strategyType: String(row.strategy_type),
    strategy: object(row.strategy_json),
    createdAt: iso(row.created_at),
  };
}

export function mapCycle(row: Row): PatternCycleRecord {
  return {
    cycleKey: String(row.cycle_key),
    status: String(row.status),
    searchIssueRange: object(row.search_issue_range_json),
    budget: object(row.budget_json),
    discoveredCount: Number(row.discovered_count),
    acceptedCount: Number(row.accepted_count),
    result: object(row.result_json),
    createdAt: iso(row.created_at),
  };
}
