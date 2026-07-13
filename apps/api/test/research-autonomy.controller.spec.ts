import assert from 'node:assert/strict';
import { test } from 'node:test';
import { BadRequestException } from '@nestjs/common';
import { ResearchAutonomyController } from '../src/research-autonomy/research-autonomy.controller';
import { ResearchAutonomyReadService } from '../src/research-autonomy/research-autonomy.service';

test('research autonomy controller forwards decimal pagination', () => {
  const calls: unknown[] = [];
  const service = { proposals(limit: number, offset: number) { calls.push({ limit, offset }); } } as any;
  new ResearchAutonomyController(service).proposals({ limit: '20', offset: '4' });
  assert.deepEqual(calls[0], { limit: 20, offset: 4 });
});

test('research autonomy controller exposes exactly four read methods', () => {
  const controller = new ResearchAutonomyController({} as ResearchAutonomyReadService);
  const methods = Object.getOwnPropertyNames(Object.getPrototypeOf(controller));
  assert.deepEqual(
    methods.filter((name) => !['constructor', 'integer'].includes(name)).sort(),
    ['context', 'engineStatus', 'proposal', 'proposals'].sort(),
  );
});

test('research autonomy controller rejects ambiguous pagination syntax', () => {
  const controller = new ResearchAutonomyController({ proposals() {} } as any);
  assert.throws(() => controller.proposals({ limit: '1e2' }), BadRequestException);
  assert.throws(() => controller.proposals({ offset: '9007199254740992' }), BadRequestException);
});
