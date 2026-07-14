import assert from 'node:assert/strict';
import { test } from 'node:test';
import { BadRequestException } from '@nestjs/common';
import { ResearchExecutionController } from '../src/research-execution/research-execution.controller';

test('research execution controller forwards decimal pagination', () => {
  const calls: unknown[] = [];
  const service = { runs(limit: number, offset: number) { calls.push({ limit, offset }); } } as any;

  new ResearchExecutionController(service).runs({ limit: '20', offset: '4' });

  assert.deepEqual(calls[0], { limit: 20, offset: 4 });
});

test('research execution controller exposes exactly five read methods', () => {
  const controller = new ResearchExecutionController({} as any);
  const methods = Object.getOwnPropertyNames(Object.getPrototypeOf(controller));

  assert.deepEqual(
    methods.filter((name) => !['constructor', 'integer'].includes(name)).sort(),
    ['artifacts', 'results', 'run', 'runs', 'status'].sort(),
  );
});

test('research execution controller rejects ambiguous pagination syntax', () => {
  const controller = new ResearchExecutionController({ runs() {} } as any);

  assert.throws(() => controller.runs({ limit: '1e2' }), BadRequestException);
  assert.throws(() => controller.runs({ offset: '9007199254740992' }), BadRequestException);
});
