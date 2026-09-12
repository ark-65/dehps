import { Controller, Get, Inject, Module, NotFoundException, Param } from '@nestjs/common';
import { constants } from 'node:fs';
import { open, realpath } from 'node:fs/promises';
import path from 'node:path';

export type ExecutionStatusSource = {
  controlPlane: string;
  root: string;
  planDigest: string;
  releaseSha256: string;
  executionId: number;
  requestId?: number;
  maxAgeSeconds: number;
};

type UnknownReason = 'MISSING' | 'UNREADABLE' | 'INVALID' | 'IDENTITY_MISMATCH' | 'STALE' | 'FUTURE_TIMESTAMP';
type Projection = {
  schema: 'execution-status.v2';
  run_id: string;
  phase: 'starting' | 'running' | 'waiting' | 'completed' | 'failed';
  execution_id: number;
  release_sha256: string;
  plan_digest: string;
  manifest_digest: string;
  updated_at: string;
  tasks: Record<string, string>;
  wait_reasons?: Record<string, string>;
  task_errors?: Record<string, string>;
};

const HEX = /^[a-f0-9]{64}$/;
const DOMAIN = /^[a-z][a-z0-9-]{0,95}$/;
const MAX_BYTES = 1024 * 1024;
const PHASES = new Set(['starting', 'running', 'waiting', 'completed', 'failed']);
const TASK_STATES = new Set(['draft', 'running', 'ready', 'dependency_wait', 'external_wait',
  'approval_wait', 'blocked_by_contract', 'completed', 'failed', 'superseded']);

function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

export function parseExecutionStatusSources(raw: string | undefined): ExecutionStatusSource[] {
  if (raw === undefined || raw.trim() === '') return [];
  const values: unknown = JSON.parse(raw);
  if (!Array.isArray(values)) throw new Error('execution status sources must be an explicit array');
  const domains = new Set<string>();
  return values.map((value: unknown) => {
    if (!object(value) || Object.keys(value).filter(key => key !== 'requestId').sort().join(',') !==
      'controlPlane,executionId,maxAgeSeconds,planDigest,releaseSha256,root' ||
      typeof value.controlPlane !== 'string' || !DOMAIN.test(value.controlPlane) ||
      domains.has(value.controlPlane) || typeof value.root !== 'string' ||
      !path.isAbsolute(value.root) || path.normalize(value.root) !== value.root ||
      typeof value.planDigest !== 'string' || !HEX.test(value.planDigest) ||
      typeof value.releaseSha256 !== 'string' || !HEX.test(value.releaseSha256) ||
      !Number.isSafeInteger(value.executionId) || (value.executionId as number) < 1 ||
      (value.requestId !== undefined && (!Number.isSafeInteger(value.requestId) || (value.requestId as number) < 1)) ||
      !Number.isInteger(value.maxAgeSeconds) || (value.maxAgeSeconds as number) < 1 ||
      (value.maxAgeSeconds as number) > 86400) {
      throw new Error('invalid or duplicate execution status binding');
    }
    domains.add(value.controlPlane);
    return Object.freeze({ ...value }) as ExecutionStatusSource;
  });
}

function projection(value: unknown): value is Projection {
  if (!object(value) || value.schema !== 'execution-status.v2' ||
      typeof value.run_id !== 'string' || !/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(value.run_id) ||
      typeof value.phase !== 'string' || !PHASES.has(value.phase) ||
      !Number.isSafeInteger(value.execution_id) || (value.execution_id as number) < 1 ||
      typeof value.release_sha256 !== 'string' || !HEX.test(value.release_sha256) ||
      typeof value.plan_digest !== 'string' || !HEX.test(value.plan_digest) ||
      typeof value.manifest_digest !== 'string' || !HEX.test(value.manifest_digest) ||
      typeof value.updated_at !== 'string' ||
      !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|\+00:00)$/.test(value.updated_at) ||
      !Number.isFinite(Date.parse(value.updated_at)) || !object(value.tasks) ||
      Object.keys(value.tasks).length === 0 ||
      !Object.entries(value.tasks).every(([key, state]) => key.length > 0 &&
        typeof state === 'string' && TASK_STATES.has(state))) return false;
  if (new Date(value.updated_at).toISOString().slice(0, 19) !== value.updated_at.slice(0, 19)) return false;
  const tasks = value.tasks;
  for (const reasons of [value.wait_reasons, value.task_errors]) {
    if (reasons !== undefined && (!object(reasons) ||
      !Object.entries(reasons).every(([key, reason]) => Object.hasOwn(tasks, key) &&
        typeof reason === 'string' && reason.length > 0 && reason.length <= 200))) return false;
  }
  return value.phase !== 'completed' || Object.values(value.tasks).every(state => state === 'completed');
}

/** Readonly operational observations. Never substitute a legacy path or cached success. */
export class ExecutionStatusReader {
  private readonly sources: Map<string, ExecutionStatusSource>;

  constructor(sources: ExecutionStatusSource[]) {
    // Validate/copy injected bindings too; request parameters cannot supply paths.
    this.sources = new Map(parseExecutionStatusSources(JSON.stringify(sources)).map(source => [source.controlPlane, source]));
  }

  domains() {
    return [...this.sources.keys()].sort();
  }

  async read(controlPlane: string, now = Date.now()) {
    const source = this.sources.get(controlPlane);
    if (!source) throw new NotFoundException('execution control domain is not configured');
    const expected = { controlPlane, planDigest: source.planDigest, releaseSha256: source.releaseSha256,
      executionId: source.executionId };
    const unknown = (reason: UnknownReason) => ({ ...expected, status: 'UNKNOWN' as const, reason,
      evidence: 'OPERATIONAL_PROJECTION_ONLY' as const, durableCompletionVerified: false as const });
    const file = path.join(source.root, controlPlane, 'status', 'execution.json');
    let raw: unknown;
    try {
      // The fixed domain root must be mounted readonly for the API in deployment.
      // realpath rejects symlinks in every ancestor; O_NOFOLLOW protects final open.
      if (await realpath(file) !== file) return unknown('INVALID');
      const handle = await open(file, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
      try {
        const info = await handle.stat();
        if (!info.isFile() || info.size > MAX_BYTES) return unknown('INVALID');
        const bytes = Buffer.alloc(MAX_BYTES + 1);
        // Bounded even if the file grows after stat. Writer normally uses rename.
        let size = 0;
        while (size < bytes.length) {
          const result = await handle.read(bytes, size, bytes.length - size, size);
          if (!result.bytesRead) break;
          size += result.bytesRead;
        }
        if (size > MAX_BYTES) return unknown('INVALID');
        raw = JSON.parse(bytes.subarray(0, size).toString('utf8'));
      } finally {
        await handle.close();
      }
    } catch (error) {
      const code = (error as NodeJS.ErrnoException).code;
      if (code === 'ENOENT' || code === 'ENOTDIR') return unknown('MISSING');
      if (error instanceof SyntaxError || code === 'ELOOP') return unknown('INVALID');
      return unknown('UNREADABLE');
    }
    if (!object(raw) || !object(raw.payload)) return unknown('INVALID');
    if (raw.payload.schema === 'execution-admission-status.v1') {
      const value = raw.payload;
      if (value.phase !== 'waiting' || value.reason !== 'AUTHORIZATION_REQUIRED' ||
          !Number.isSafeInteger(value.request_id) || (value.request_id as number) < 1 ||
          typeof value.run_id !== 'string' ||
          typeof value.updated_at !== 'string' || !Number.isFinite(Date.parse(value.updated_at))) return unknown('INVALID');
      if (raw.control_plane !== controlPlane || value.plan_digest !== source.planDigest ||
          value.release_sha256 !== source.releaseSha256 || value.request_id !== source.requestId) return unknown('IDENTITY_MISMATCH');
      const age = now - Date.parse(value.updated_at);
      if (age < -5000) return unknown('FUTURE_TIMESTAMP');
      if (age > source.maxAgeSeconds * 1000) return unknown('STALE');
      return { ...expected, executionId: null, requestId: value.request_id, status: 'WAITING',
        reason: 'AUTHORIZATION_REQUIRED', currentExecutionAuthorized: false,
        evidence: 'OPERATIONAL_PROJECTION_ONLY' as const, durableCompletionVerified: false as const,
        runId: value.run_id, updatedAt: value.updated_at };
    }
    if (!projection(raw.payload)) return unknown('INVALID');
    const value = raw.payload;
    if (raw.control_plane !== controlPlane || value.plan_digest !== source.planDigest ||
        value.release_sha256 !== source.releaseSha256 || value.execution_id !== source.executionId) {
      return unknown('IDENTITY_MISMATCH');
    }
    const age = now - Date.parse(value.updated_at);
    if (age < -5000) return unknown('FUTURE_TIMESTAMP');
    if (age > source.maxAgeSeconds * 1000) return unknown('STALE');
    return { ...expected, status: value.phase.toUpperCase(), reason: null,
      evidence: 'OPERATIONAL_PROJECTION_ONLY' as const, durableCompletionVerified: false as const,
      runId: value.run_id, updatedAt: value.updated_at, manifestDigest: value.manifest_digest,
      tasks: value.tasks, ...(value.wait_reasons === undefined ? {} : { waitReasons: value.wait_reasons }),
      ...(value.task_errors === undefined ? {} : { taskErrors: value.task_errors }) };
  }
}

@Controller('execution-status')
export class ExecutionStatusController {
  constructor(@Inject(ExecutionStatusReader) private readonly reader: ExecutionStatusReader) {}

  @Get()
  async list() {
    return { domains: await Promise.all(this.reader.domains().map(domain => this.reader.read(domain))) };
  }

  @Get(':controlPlane')
  read(@Param('controlPlane') controlPlane: string) {
    return this.reader.read(controlPlane);
  }
}

@Module({
  controllers: [ExecutionStatusController],
  providers: [{ provide: ExecutionStatusReader,
    useFactory: () => new ExecutionStatusReader(parseExecutionStatusSources(process.env.DEHPS_EXECUTION_STATUS_SOURCES)) }],
})
export class ExecutionStatusModule {}
