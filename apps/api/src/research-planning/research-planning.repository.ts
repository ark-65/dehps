import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { parseDbPort } from '../config';
import {
  ExperimentPlanRecord,
  ExperimentPlanRequestRecord,
  ExperimentPlanStageRecord,
  ResearchPlanningReadRepository,
} from './research-planning.types';

type Row = Record<string, any>;

function object(value: unknown): Record<string, any> {
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value);
      return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
    } catch {
      return {};
    }
  }
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, any>)
    : {};
}

function array(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function optionalIso(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  return value instanceof Date ? value.toISOString() : new Date(String(value)).toISOString();
}

@Injectable()
export class PostgresResearchPlanningReadRepository
  implements ResearchPlanningReadRepository, OnModuleDestroy
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

  async listPlans(limit: number, offset: number): Promise<ExperimentPlanRecord[]> {
    const { rows } = await this.pool.query(
      `SELECT h.hypothesis_key, h.status AS hypothesis_status, h.metadata_json
       FROM research_hypotheses h
       WHERE h.metadata_json ? 'experiment_plan'
       ORDER BY h.created_at DESC, h.id DESC LIMIT $1 OFFSET $2`,
      [limit, offset],
    );
    return rows.map(mapPlan);
  }

  async getPlan(key: string): Promise<ExperimentPlanRecord | null> {
    const { rows } = await this.pool.query(
      `SELECT h.hypothesis_key, h.status AS hypothesis_status, h.metadata_json
       FROM research_hypotheses h
       WHERE h.metadata_json->'experiment_plan'->>'plan_key' = $1
          OR h.hypothesis_key = $1
       ORDER BY h.created_at DESC, h.id DESC LIMIT 1`,
      [key],
    );
    return rows[0] ? mapPlan(rows[0]) : null;
  }

  async listStages(planKey: string): Promise<ExperimentPlanStageRecord[]> {
    const { rows } = await this.pool.query(
      `SELECT e.experiment_key, e.experiment_type, e.status, e.artifact_paths_json,
              e.config_snapshot_json, e.metadata_json
       FROM research_hypothesis_experiments e
       WHERE e.metadata_json->>'experiment_plan_key' = $1
       ORDER BY e.created_at ASC, e.id ASC`,
      [planKey],
    );
    return rows.map(mapStage);
  }

  async listRequests(planKey: string): Promise<ExperimentPlanRequestRecord[]> {
    const { rows } = await this.pool.query(
      `SELECT request_key, request_type, status, requested_by_role, requested_by,
              title, summary, payload_json, metadata_json, submitted_at
       FROM agent_requests
       WHERE payload_json->>'experiment_plan_key' = $1
          OR metadata_json->>'experiment_plan_key' = $1
       ORDER BY created_at ASC, id ASC`,
      [planKey],
    );
    return rows.map(mapRequest);
  }

  async latestPlan(): Promise<ExperimentPlanRecord | null> {
    const items = await this.listPlans(1, 0);
    return items[0] ?? null;
  }
}

export function mapPlan(row: Row): ExperimentPlanRecord {
  const metadata = object(row.metadata_json);
  const plan = object(metadata.experiment_plan);
  return {
    planKey: String(plan.plan_key ?? ''),
    planVersion: String(plan.plan_version ?? ''),
    proposalKey: String(plan.proposal_key ?? ''),
    hypothesisKey: String(row.hypothesis_key),
    familyKey: String(plan.family_key ?? ''),
    mechanism: String(plan.mechanism ?? ''),
    planFingerprint: String(plan.plan_fingerprint ?? ''),
    proposalFingerprint: String(plan.proposal_fingerprint ?? ''),
    hypothesisStatus: String(row.hypothesis_status),
    plan,
  };
}

export function mapStage(row: Row): ExperimentPlanStageRecord {
  return {
    experimentKey: String(row.experiment_key),
    experimentType: String(row.experiment_type),
    status: String(row.status),
    artifactPaths: array(row.artifact_paths_json),
    configSnapshot: object(row.config_snapshot_json),
    metadata: object(row.metadata_json),
  };
}

export function mapRequest(row: Row): ExperimentPlanRequestRecord {
  return {
    requestKey: String(row.request_key),
    requestType: String(row.request_type),
    status: String(row.status),
    requestedByRole: String(row.requested_by_role),
    requestedBy: String(row.requested_by),
    title: String(row.title),
    summary: String(row.summary),
    payload: object(row.payload_json),
    metadata: object(row.metadata_json),
    submittedAt: optionalIso(row.submitted_at),
  };
}
