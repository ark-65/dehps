import 'reflect-metadata';
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { mkdtemp, mkdir, writeFile, rm, rmdir, symlink, stat } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { NestFactory } from '@nestjs/core';
import { ExecutionStatusModule, ExecutionStatusReader, parseExecutionStatusSources } from '../src/execution-status';

const now = Date.parse('2026-09-10T04:00:00Z');
function packet() {
  return { control_plane: 'learning', payload: {
    schema: 'execution-status.v2', run_id: 'c45dd659-251b-4088-993a-7d2170c53d93', phase: 'completed',
    execution_id: 42, release_sha256: 'a'.repeat(64), plan_digest: 'b'.repeat(64),
    manifest_digest: 'c'.repeat(64), updated_at: new Date(now).toISOString(), tasks: { train: 'completed' },
  } };
}

async function fixture() {
  const root = await mkdtemp(path.join(os.tmpdir(), 'dehps-api-status-'));
  const file = path.join(root, 'learning/status/execution.json');
  await mkdir(path.dirname(file), { recursive: true });
  const binding = { root, controlPlane: 'learning', planDigest: 'b'.repeat(64), releaseSha256: 'a'.repeat(64),
    executionId: 42, requestId: 9, maxAgeSeconds: 60 };
  const reader = new ExecutionStatusReader([binding]);
  return { root, file, binding, reader, write: (value: unknown) => writeFile(file, JSON.stringify(value)) };
}

test('sources are explicit, closed and cannot silently select another domain', () => {
  assert.deepEqual(parseExecutionStatusSources(undefined), []);
  assert.throws(() => parseExecutionStatusSources('{}'));
  const binding = { root: '/tmp/status', controlPlane: 'learning', planDigest: 'b'.repeat(64),
    releaseSha256: 'a'.repeat(64), executionId: 42, maxAgeSeconds: 60 };
  for (const change of [{ root: '../runtime' }, { root: '/tmp/../runtime' }, { controlPlane: '../formal' },
    { executionId: 0 }, { maxAgeSeconds: 0 }, { releaseSha256: 'latest' }, { extra: true }]) {
    assert.throws(() => parseExecutionStatusSources(JSON.stringify([{ ...binding, ...change }])));
  }
  assert.throws(() => parseExecutionStatusSources(JSON.stringify([binding, binding])));
});

test('missing, stale, foreign, corrupt and future projections never reuse a cached success', async () => {
  const f = await fixture();
  try {
    assert.equal((await f.reader.read('learning', now)).reason, 'MISSING');
    await assert.rejects(() => f.reader.read('formal', now), /not configured/);
    await f.write(packet());
    const before = (await stat(f.file)).mtimeMs;
    const valid = await f.reader.read('learning', now);
    assert.equal(valid.status, 'COMPLETED');
    assert.equal(valid.durableCompletionVerified, false);
    assert.equal((await stat(f.file)).mtimeMs, before);
    assert.equal((await f.reader.read('learning', now + 60001)).reason, 'STALE');
    assert.equal((await f.reader.read('learning', now - 5001)).reason, 'FUTURE_TIMESTAMP');
    for (const field of ['plan_digest', 'release_sha256', 'execution_id']) {
      const value = packet();
      Object.assign(value.payload, { [field]: field === 'execution_id' ? 43 : 'd'.repeat(64) });
      await f.write(value);
      assert.equal((await f.reader.read('learning', now)).reason, 'IDENTITY_MISMATCH');
    }
    await f.write({ ...packet(), control_plane: 'formal' });
    assert.equal((await f.reader.read('learning', now)).reason, 'IDENTITY_MISMATCH');
    await f.write({ ...packet(), payload: { ...packet().payload, schema: 'execution-status.v1' } });
    assert.equal((await f.reader.read('learning', now)).reason, 'INVALID');
    await f.write({ ...packet(), payload: { ...packet().payload, tasks: { train: 'draft' } } });
    assert.equal((await f.reader.read('learning', now)).reason, 'INVALID');
    await writeFile(f.file, '{');
    assert.equal((await f.reader.read('learning', now)).reason, 'INVALID');
    await writeFile(f.file, ' '.repeat(1024 * 1024 + 1));
    assert.equal((await f.reader.read('learning', now)).reason, 'INVALID');
    await rm(f.file);
    assert.equal((await f.reader.read('learning', now)).reason, 'MISSING');
  } finally { await rm(f.root, { recursive: true, force: true }); }
});

test('symlink status and ancestor paths are rejected', async () => {
  const f = await fixture();
  try {
    const target = path.join(f.root, 'foreign.json');
    await writeFile(target, JSON.stringify(packet()));
    await symlink(target, f.file);
    assert.equal((await f.reader.read('learning', now)).reason, 'INVALID');
    await rm(f.file);
    await rmdir(path.dirname(f.file));
    const foreign = path.join(f.root, 'foreign');
    await mkdir(foreign);
    await writeFile(path.join(foreign, 'execution.json'), JSON.stringify(packet()));
    await symlink(foreign, path.dirname(f.file));
    assert.equal((await f.reader.read('learning', now)).reason, 'INVALID');
  } finally { await rm(f.root, { recursive: true, force: true }); }
});

test('per-issue waits, isolated failures and expired admission remain distinct', async () => {
  const f = await fixture();
  try {
    const base = packet();
    await f.write({ ...base, payload: { ...base.payload, phase: 'failed',
      tasks: { score: 'draft', report: 'draft', previous: 'completed' },
      wait_reasons: { score: 'WAITING_FOR_AUDITED_DRAW' }, task_errors: { report: 'OSError' } } });
    const failure = await f.reader.read('learning', now);
    assert.equal(failure.status, 'FAILED');
    assert.deepEqual('taskErrors' in failure && failure.taskErrors, { report: 'OSError' });
    await f.write({ ...base, payload: { ...base.payload, phase: 'waiting', wait_reasons: { foreign: 'wait' } } });
    assert.equal((await f.reader.read('learning', now)).reason, 'INVALID');
    await f.write({ ...base, payload: { schema: 'execution-admission-status.v1', phase: 'waiting',
      reason: 'AUTHORIZATION_REQUIRED', request_id: 9, run_id: base.payload.run_id,
      plan_digest: base.payload.plan_digest, release_sha256: base.payload.release_sha256,
      updated_at: base.payload.updated_at } });
    const wait = await f.reader.read('learning', now);
    assert.equal(wait.status, 'WAITING');
    assert.equal(wait.reason, 'AUTHORIZATION_REQUIRED');
    assert.equal(wait.executionId, null);
    assert.equal(wait.durableCompletionVerified, false);
  } finally { await rm(f.root, { recursive: true, force: true }); }
});

test('actual HTTP module reads failed status and exposes no implicit production source', async () => {
  const f = await fixture();
  const previous = process.env.DEHPS_EXECUTION_STATUS_SOURCES;
  process.env.DEHPS_EXECUTION_STATUS_SOURCES = JSON.stringify([f.binding]);
  const app = await NestFactory.create(ExecutionStatusModule, { logger: false });
  try {
    await f.write({ ...packet(), payload: { ...packet().payload, phase: 'failed', updated_at: new Date().toISOString() } });
    await app.listen(0, '127.0.0.1');
    const url = await app.getUrl();
    const response = await fetch(url + '/execution-status/learning');
    assert.equal(response.status, 200);
    assert.equal((await response.json()).status, 'FAILED');
    assert.equal((await fetch(url + '/execution-status/formal')).status, 404);
    const listed = await (await fetch(url + '/execution-status')).json();
    assert.equal(listed.domains.length, 1);
    assert.equal(listed.domains[0].controlPlane, 'learning');
  } finally {
    await app.close();
    if (previous === undefined) delete process.env.DEHPS_EXECUTION_STATUS_SOURCES;
    else process.env.DEHPS_EXECUTION_STATUS_SOURCES = previous;
    await rm(f.root, { recursive: true, force: true });
  }
});
