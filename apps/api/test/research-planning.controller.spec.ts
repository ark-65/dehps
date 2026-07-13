import assert from 'node:assert/strict';
import { test } from 'node:test';
import { BadRequestException } from '@nestjs/common';
import { ResearchPlanningController } from '../src/research-planning/research-planning.controller';
import { ResearchPlanningReadService } from '../src/research-planning/research-planning.service';

test('research planning controller forwards decimal pagination', () => {
  const calls: unknown[] = [];
  const service = { plans(limit: number, offset: number) { calls.push({ limit, offset }); } } as any;

  new ResearchPlanningController(service).plans({ limit: '20', offset: '4' });

  assert.deepEqual(calls[0], { limit: 20, offset: 4 });
});

test('research planning controller exposes exactly five read methods', () => {
  const controller = new ResearchPlanningController({} as ResearchPlanningReadService);
  const methods = Object.getOwnPropertyNames(Object.getPrototypeOf(controller));

  assert.deepEqual(
    methods.filter((name) => !['constructor', 'integer'].includes(name)).sort(),
    ['plan', 'plans', 'requests', 'stages', 'status'].sort(),
  );
});

test('research planning controller rejects ambiguous pagination syntax', () => {
  const controller = new ResearchPlanningController({ plans() {} } as any);

  assert.throws(() => controller.plans({ limit: '1e2' }), BadRequestException);
  assert.throws(() => controller.plans({ offset: '9007199254740992' }), BadRequestException);
});
