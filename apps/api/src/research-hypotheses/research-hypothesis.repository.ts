import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { parseDbPort } from '../config';
import {
  HypothesisDecisionRecord,
  HypothesisEvidenceRecord,
  HypothesisExperimentRecord,
  HypothesisFamilyRecord,
  HypothesisReadRepository,
  HypothesisRecord,
  RegistryQuery,
} from './research-hypothesis.types';

type Row = Record<string, any>;

function jsonObject(value: unknown): Record<string, unknown> {
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

function jsonArray(value: unknown): unknown[] {
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }
  return Array.isArray(value) ? value : [];
}

function iso(value: unknown): string {
  return value instanceof Date ? value.toISOString() : new Date(String(value)).toISOString();
}

function optionalIso(value: unknown): string | null {
  return value === null || value === undefined ? null : iso(value);
}

function filters(query: RegistryQuery, alias: string, includeFamily: boolean) {
  const clauses: string[] = [];
  const values: unknown[] = [];
  const add = (clause: string, value: unknown) => {
    values.push(value);
    clauses.push(clause.replace('?', `$${values.length}`));
  };
  if (query.status) add(`${alias}.status = ?`, query.status);
  if (includeFamily && query.familyKey) add('f.family_key = ?', query.familyKey);
  if (query.createdAfter) add(`${alias}.created_at >= ?`, query.createdAfter);
  if (query.createdBefore) add(`${alias}.created_at <= ?`, query.createdBefore);
  return { clauses, values };
}

@Injectable()
export class PostgresHypothesisReadRepository implements HypothesisReadRepository, OnModuleDestroy {
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

  async listFamilies(query: RegistryQuery): Promise<HypothesisFamilyRecord[]> {
    const { clauses, values } = filters(query, 'f', false);
    values.push(query.limit, query.offset);
    const { rows } = await this.pool.query(
      `SELECT f.* FROM research_hypothesis_families f
       ${clauses.length ? `WHERE ${clauses.join(' AND ')}` : ''}
       ORDER BY f.created_at DESC, f.id DESC LIMIT $${values.length - 1} OFFSET $${values.length}`,
      values,
    );
    return rows.map(mapFamily);
  }

  async getFamily(familyKey: string): Promise<HypothesisFamilyRecord | null> {
    const { rows } = await this.pool.query(
      'SELECT * FROM research_hypothesis_families WHERE family_key = $1 LIMIT 1',
      [familyKey],
    );
    return rows[0] ? mapFamily(rows[0]) : null;
  }

  async listHypotheses(query: RegistryQuery): Promise<HypothesisRecord[]> {
    const { clauses, values } = filters(query, 'h', true);
    values.push(query.limit, query.offset);
    const { rows } = await this.pool.query(
      `SELECT h.*, f.family_key FROM research_hypotheses h
       JOIN research_hypothesis_families f ON f.id = h.family_id
       ${clauses.length ? `WHERE ${clauses.join(' AND ')}` : ''}
       ORDER BY h.created_at DESC, h.id DESC LIMIT $${values.length - 1} OFFSET $${values.length}`,
      values,
    );
    return rows.map(mapHypothesis);
  }

  async getHypothesis(hypothesisKey: string): Promise<HypothesisRecord | null> {
    const { rows } = await this.pool.query(
      `SELECT h.*, f.family_key FROM research_hypotheses h
       JOIN research_hypothesis_families f ON f.id = h.family_id
       WHERE h.hypothesis_key = $1 LIMIT 1`,
      [hypothesisKey],
    );
    return rows[0] ? mapHypothesis(rows[0]) : null;
  }

  async listExperiments(
    hypothesisKey: string,
    query: RegistryQuery,
  ): Promise<HypothesisExperimentRecord[]> {
    const { clauses, values } = filters(query, 'e', false);
    values.unshift(hypothesisKey);
    const shifted = clauses.map((clause) => clause.replace(/\$(\d+)/g, (_, value) => `$${Number(value) + 1}`));
    values.push(query.limit, query.offset);
    const { rows } = await this.pool.query(
      `SELECT e.* FROM research_hypothesis_experiments e
       JOIN research_hypotheses h ON h.id = e.hypothesis_id
       WHERE h.hypothesis_key = $1 ${shifted.length ? `AND ${shifted.join(' AND ')}` : ''}
       ORDER BY e.created_at DESC, e.id DESC LIMIT $${values.length - 1} OFFSET $${values.length}`,
      values,
    );
    return rows.map(mapExperiment);
  }

  async listEvidence(
    hypothesisKey: string,
    query: RegistryQuery,
  ): Promise<HypothesisEvidenceRecord[]> {
    const { clauses, values } = filters({ ...query, status: undefined }, 'e', false);
    values.unshift(hypothesisKey);
    const shifted = clauses.map((clause) => clause.replace(/\$(\d+)/g, (_, value) => `$${Number(value) + 1}`));
    values.push(query.limit, query.offset);
    const { rows } = await this.pool.query(
      `SELECT e.* FROM research_hypothesis_evidence e
       JOIN research_hypotheses h ON h.id = e.hypothesis_id
       WHERE h.hypothesis_key = $1 ${shifted.length ? `AND ${shifted.join(' AND ')}` : ''}
       ORDER BY e.observed_at DESC, e.id DESC LIMIT $${values.length - 1} OFFSET $${values.length}`,
      values,
    );
    return rows.map(mapEvidence);
  }

  async listDecisions(
    hypothesisKey: string,
    query: RegistryQuery,
  ): Promise<HypothesisDecisionRecord[]> {
    const { clauses, values } = filters({ ...query, status: undefined }, 'd', false);
    values.unshift(hypothesisKey);
    const shifted = clauses.map((clause) => clause.replace(/\$(\d+)/g, (_, value) => `$${Number(value) + 1}`));
    values.push(query.limit, query.offset);
    const { rows } = await this.pool.query(
      `SELECT d.* FROM research_hypothesis_decisions d
       JOIN research_hypotheses h ON h.id = d.hypothesis_id
       WHERE h.hypothesis_key = $1 ${shifted.length ? `AND ${shifted.join(' AND ')}` : ''}
       ORDER BY d.decided_at, d.id LIMIT $${values.length - 1} OFFSET $${values.length}`,
      values,
    );
    return rows.map(mapDecision);
  }
}

export function mapFamily(row: Row): HypothesisFamilyRecord {
  return {
    id: Number(row.id), familyKey: row.family_key, title: row.title, description: row.description,
    mechanism: row.mechanism, status: row.status, rejectionScope: row.rejection_scope,
    rejectionReason: row.rejection_reason ?? null, reopenCondition: row.reopen_condition ?? null,
    createdAt: iso(row.created_at), updatedAt: iso(row.updated_at), resolvedAt: optionalIso(row.resolved_at),
    metadata: jsonObject(row.metadata_json),
  };
}

export function mapHypothesis(row: Row): HypothesisRecord {
  return {
    id: Number(row.id), hypothesisKey: row.hypothesis_key, familyId: Number(row.family_id),
    familyKey: row.family_key, parentHypothesisId: row.parent_hypothesis_id == null ? null : Number(row.parent_hypothesis_id),
    title: row.title, statement: row.statement, mechanism: row.mechanism, nullHypothesis: row.null_hypothesis,
    minimalNonNull: row.minimal_non_null, invariants: jsonArray(row.invariants_json),
    baselineDefinition: jsonObject(row.baseline_definition_json), metricDefinition: jsonObject(row.metric_definition_json),
    failureCondition: jsonObject(row.failure_condition_json), selfDeceptionRisk: jsonArray(row.self_deception_risk_json),
    status: row.status, rejectionScope: row.rejection_scope, rejectionReason: row.rejection_reason ?? null,
    reopenCondition: row.reopen_condition ?? null, createdAt: iso(row.created_at), updatedAt: iso(row.updated_at),
    preregisteredAt: optionalIso(row.preregistered_at), startedAt: optionalIso(row.started_at),
    resolvedAt: optionalIso(row.resolved_at), metadata: jsonObject(row.metadata_json),
  };
}

function mapExperiment(row: Row): HypothesisExperimentRecord {
  return {
    id: Number(row.id), hypothesisId: Number(row.hypothesis_id), experimentKey: row.experiment_key,
    experimentType: row.experiment_type, externalRunId: row.external_run_id ?? null,
    trainingRunId: row.training_run_id ?? null,
    trainingRoundIndex: row.training_round_index == null ? null : Number(row.training_round_index),
    reportPath: row.report_path ?? null, artifactPaths: jsonArray(row.artifact_paths_json),
    configSnapshot: jsonObject(row.config_snapshot_json), status: row.status,
    startedAt: optionalIso(row.started_at), completedAt: optionalIso(row.completed_at),
    createdAt: iso(row.created_at), metadata: jsonObject(row.metadata_json),
  };
}

function mapEvidence(row: Row): HypothesisEvidenceRecord {
  return {
    id: Number(row.id), hypothesisId: Number(row.hypothesis_id),
    experimentId: row.experiment_id == null ? null : Number(row.experiment_id), evidenceType: row.evidence_type,
    direction: row.direction, summary: row.summary, metrics: jsonObject(row.metrics_json),
    artifactPath: row.artifact_path ?? null, contentHash: row.content_hash ?? null,
    observedAt: iso(row.observed_at), createdAt: iso(row.created_at), metadata: jsonObject(row.metadata_json),
  };
}

function mapDecision(row: Row): HypothesisDecisionRecord {
  return {
    id: Number(row.id), hypothesisId: Number(row.hypothesis_id), previousStatus: row.previous_status,
    newStatus: row.new_status, decisionCode: row.decision_code, summary: row.summary,
    reason: jsonObject(row.reason_json), evidenceIds: jsonArray(row.evidence_ids_json),
    decidedBy: row.decided_by, decidedAt: iso(row.decided_at), createdAt: iso(row.created_at),
  };
}
