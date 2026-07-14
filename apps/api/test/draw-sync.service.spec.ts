import assert from 'node:assert/strict';
import { test } from 'node:test';
import { BadRequestException } from '@nestjs/common';
import { mapDrawIssueEvent, mapDrawSyncRun } from '../src/draw-sync/draw-sync.repository';
import { DrawSyncReadService } from '../src/draw-sync/draw-sync.service';
import { DrawIssueEventRecord, DrawSyncReadRepository, DrawSyncRunRecord } from '../src/draw-sync/draw-sync.types';

const run: DrawSyncRunRecord = {
  id: 1,
  runKey: 'draw-sync-1',
  startedAt: '2026-07-14T00:00:00.000Z',
  completedAt: '2026-07-14T00:00:01.000Z',
  status: 'new_issue',
  previousLatestIssue: '2026079',
  currentLatestIssue: '2026080',
  insertedIssues: ['2026080'],
  updatedIssues: [],
  auditPassed: true,
  fingerprintBefore: 'fp-before',
  fingerprintAfter: 'fp-after',
  eventKey: 'event-1',
  warnings: [],
  error: {},
  metadata: { source: 'zhcw' },
};

const event: DrawIssueEventRecord = {
  id: 1,
  eventKey: 'event-1',
  previousIssue: '2026079',
  newIssue: '2026080',
  historyFingerprint: 'fp-after',
  auditReportHash: 'audit',
  source: 'zhcw',
  status: 'pending',
  syncedAt: '2026-07-14T00:00:01.000Z',
  consumedAt: null,
  consumerRunId: null,
  createdAt: '2026-07-14T00:00:01.000Z',
  metadata: {},
};

function repository(): DrawSyncReadRepository {
  return {
    async listRuns() { return [run]; },
    async listEvents() { return [event]; },
    async status() { return { latestRun: run, latestEvent: event, pendingEventCount: 1 }; },
  };
}

test('draw sync service exposes read-only status, runs, and events', async () => {
  const service = new DrawSyncReadService(repository());

  const status = await service.status();
  const runs = await service.runs(25, 2);
  const events = await service.events(10, 0);

  assert.equal(status.writeRoutesEnabled, false);
  assert.equal(status.pendingEventCount, 1);
  assert.equal(runs.items[0].runKey, 'draw-sync-1');
  assert.equal(events.items[0].eventKey, 'event-1');
  assert.deepEqual({ limit: runs.limit, offset: runs.offset }, { limit: 25, offset: 2 });
});

test('draw sync service rejects invalid pagination', async () => {
  const service = new DrawSyncReadService(repository());

  await assert.rejects(() => service.runs(0, 0), BadRequestException);
  await assert.rejects(() => service.events(10, -1), BadRequestException);
});

test('draw sync mappers normalize json payloads', () => {
  const mappedRun = mapDrawSyncRun({
    id: '7',
    run_key: 'run',
    started_at: new Date('2026-07-14T00:00:00Z'),
    completed_at: null,
    status: 'no_change',
    previous_latest_issue: '2026079',
    current_latest_issue: '2026079',
    inserted_issues_json: '[]',
    updated_issues_json: '[]',
    audit_passed: true,
    fingerprint_before: 'fp',
    fingerprint_after: 'fp',
    event_key: null,
    warnings_json: '[]',
    error_json: '{}',
    metadata_json: '{"source":"zhcw"}',
  });
  const mappedEvent = mapDrawIssueEvent({
    id: 8,
    event_key: 'event',
    previous_issue: '2026079',
    new_issue: '2026080',
    history_fingerprint: 'fp',
    audit_report_hash: 'audit',
    source: 'zhcw',
    status: 'pending',
    synced_at: new Date('2026-07-14T00:00:01Z'),
    consumed_at: null,
    consumer_run_id: null,
    created_at: new Date('2026-07-14T00:00:01Z'),
    metadata_json: '{}',
  });

  assert.equal(mappedRun.id, 7);
  assert.equal(mappedRun.metadata.source, 'zhcw');
  assert.equal(mappedEvent.newIssue, '2026080');
});
