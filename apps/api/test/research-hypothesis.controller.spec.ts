import assert from 'node:assert/strict';
import { test } from 'node:test';
import { BadRequestException } from '@nestjs/common';
import { ResearchHypothesisController } from '../src/research-hypotheses/research-hypothesis.controller';
import { ResearchHypothesisReadService } from '../src/research-hypotheses/research-hypothesis.service';

test('hypothesis controller maps snake-case filters and pagination', async () => {
  const calls: unknown[] = [];
  const service = {
    listHypotheses(query: unknown) { calls.push(query); return {}; },
  } as ResearchHypothesisReadService;
  const controller = new ResearchHypothesisController(service);

  controller.hypotheses({
    status: 'running', family_key: 'family-1', created_after: '2026-01-01',
    created_before: '2026-07-01', limit: '20', offset: '4',
  });

  assert.deepEqual(calls[0], {
    status: 'running', familyKey: 'family-1', createdAfter: '2026-01-01',
    createdBefore: '2026-07-01', limit: 20, offset: 4,
  });
});

test('hypothesis controller exposes only read methods', () => {
  const controller = new ResearchHypothesisController({} as ResearchHypothesisReadService);
  const methods = Object.getOwnPropertyNames(Object.getPrototypeOf(controller));
  assert.deepEqual(
    methods.filter((name) => !['constructor'].includes(name) && !name.startsWith('query') && !name.startsWith('integer')).sort(),
    ['decisions', 'evidence', 'experiments', 'families', 'family', 'hypotheses', 'hypothesis'].sort(),
  );
});

test('hypothesis controller rejects non-decimal and unsafe pagination', () => {
  const controller = new ResearchHypothesisController({ listHypotheses() { return {}; } } as any);
  assert.throws(() => controller.hypotheses({ limit: '1e2' }), BadRequestException);
  assert.throws(() => controller.hypotheses({ offset: '9007199254740992' }), BadRequestException);
});
