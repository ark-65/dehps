import assert from 'node:assert/strict';
import { test } from 'node:test';
import { BadRequestException } from '@nestjs/common';
import { PatternDiscoveryController } from '../src/pattern-discovery/pattern-discovery.controller';

function controller() {
  const calls: string[] = [];
  const service = {
    patterns(limit: number, offset: number) { calls.push(`patterns:${limit}:${offset}`); return { calls }; },
    pattern(key: string) { calls.push(`pattern:${key}`); return { calls }; },
    families() { calls.push('families'); return { calls }; },
    features(limit: number, offset: number) { calls.push(`features:${limit}:${offset}`); return { calls }; },
    strategies(limit: number, offset: number) { calls.push(`strategies:${limit}:${offset}`); return { calls }; },
    cycles(limit: number, offset: number) { calls.push(`cycles:${limit}:${offset}`); return { calls }; },
    status() { calls.push('status'); return { calls }; },
  } as any;
  return { controller: new PatternDiscoveryController(service), calls };
}

test('pattern discovery controller routes read-only endpoints', () => {
  const { controller: c, calls } = controller();

  c.patterns({ limit: '25', offset: '2' });
  c.pattern('pattern-1');
  c.families();
  c.features({});
  c.strategies({});
  c.cycles({});
  c.status();

  assert.deepEqual(calls, [
    'patterns:25:2',
    'pattern:pattern-1',
    'families',
    'features:100:0',
    'strategies:100:0',
    'cycles:100:0',
    'status',
  ]);
});

test('pattern discovery controller rejects non-integer pagination', () => {
  const { controller: c } = controller();

  assert.throws(() => c.patterns({ limit: 'abc' }), BadRequestException);
});
