import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { parseDbPort } from '../config';
import { ResearchEvidenceReadRepository, ResearchEvidenceRecord } from './research-evidence.types';

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
export class PostgresResearchEvidenceReadRepository
  implements ResearchEvidenceReadRepository, OnModuleDestroy
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

  async listEvidence(limit: number, offset: number): Promise<ResearchEvidenceRecord[]> {
    const { rows } = await this.pool.query(
      `${baseQuery()} ORDER BY ev.observed_at DESC, ev.id DESC LIMIT $1 OFFSET $2`,
      [limit, offset],
    );
    return rows.map(mapEvidence);
  }

  async getEvidence(key: string): Promise<ResearchEvidenceRecord | null> {
    const { rows } = await this.pool.query(
      `${baseQuery()}
       WHERE ev.id::text = $1 OR ev.content_hash = $1 OR ev.metadata_json->>'evidence_key' = $1
       ORDER BY ev.observed_at DESC, ev.id DESC LIMIT 1`,
      [key],
    );
    return rows[0] ? mapEvidence(rows[0]) : null;
  }

  async countEvidence(): Promise<number> {
    const { rows } = await this.pool.query(`SELECT count(*)::int AS count FROM research_hypothesis_evidence`);
    return Number(rows[0]?.count ?? 0);
  }
}

function baseQuery() {
  return `SELECT ev.*, h.hypothesis_key, ex.experiment_key
          FROM research_hypothesis_evidence ev
          JOIN research_hypotheses h ON h.id = ev.hypothesis_id
          LEFT JOIN research_hypothesis_experiments ex ON ex.id = ev.experiment_id`;
}

export function mapEvidence(row: Row): ResearchEvidenceRecord {
  const metadata = object(row.metadata_json);
  return {
    id: Number(row.id),
    evidenceKey: String(metadata.evidence_key ?? row.content_hash ?? row.id),
    hypothesisKey: String(row.hypothesis_key),
    experimentKey: row.experiment_key == null ? null : String(row.experiment_key),
    evidenceType: String(row.evidence_type),
    direction: String(row.direction),
    summary: String(row.summary),
    metrics: object(row.metrics_json),
    artifactPath: row.artifact_path == null ? null : String(row.artifact_path),
    contentHash: row.content_hash == null ? null : String(row.content_hash),
    observedAt: iso(row.observed_at),
    createdAt: iso(row.created_at),
    metadata,
  };
}
