import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { parseDbPort } from '../config';
import { ResearchAutonomyReadRepository, ResearchProposalRecord } from './research-autonomy.types';

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
export class PostgresResearchAutonomyReadRepository
  implements ResearchAutonomyReadRepository, OnModuleDestroy
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

  async listProposals(limit: number, offset: number): Promise<ResearchProposalRecord[]> {
    const { rows } = await this.pool.query(
      `SELECT request_key, status, requested_by, submitted_at, payload_json
       FROM agent_requests
       WHERE request_type = 'research_hypothesis_proposal'
       ORDER BY created_at DESC, id DESC LIMIT $1 OFFSET $2`,
      [limit, offset],
    );
    return rows.map(mapProposal);
  }

  async getProposal(key: string): Promise<ResearchProposalRecord | null> {
    const { rows } = await this.pool.query(
      `SELECT request_key, status, requested_by, submitted_at, payload_json
       FROM agent_requests
       WHERE request_type = 'research_hypothesis_proposal'
         AND (request_key = $1 OR payload_json->'proposal'->>'proposal_key' = $1)
       ORDER BY created_at DESC, id DESC LIMIT 1`,
      [key],
    );
    return rows[0] ? mapProposal(rows[0]) : null;
  }

  async latestProposal(): Promise<ResearchProposalRecord | null> {
    const items = await this.listProposals(1, 0);
    return items[0] ?? null;
  }
}

export function mapProposal(row: Row): ResearchProposalRecord {
  const payload = object(row.payload_json);
  return {
    requestKey: String(row.request_key),
    requestStatus: String(row.status),
    requestedBy: String(row.requested_by),
    submittedAt: optionalIso(row.submitted_at),
    engineVersion: String(payload.engine_version ?? ''),
    contextFingerprint: String(payload.context_fingerprint ?? ''),
    proposal: object(payload.proposal),
    noveltyReport: object(payload.novelty_report),
    proposalScore: object(payload.proposal_score),
    validationReport: object(payload.validation_report),
    sourceEvidenceIds: array(payload.source_evidence_ids),
    sourceHypothesisKeys: array(payload.source_hypothesis_keys),
    sourceTrainingRunIds: array(payload.source_training_run_ids),
  };
}
