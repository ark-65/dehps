import assert from 'node:assert/strict';
import { test } from 'node:test';
import { normalizeRankingContract } from '../src/ranking-contract';

test('historical null ranking contracts normalize to legacy', () => {
  assert.equal(normalizeRankingContract(null), 'legacy_score_partition');
  assert.equal(normalizeRankingContract(''), 'legacy_score_partition');
  assert.equal(normalizeRankingContract('strict_v1'), 'strict_v1');
});

test('unknown ranking contracts fail closed', () => {
  assert.throws(() => normalizeRankingContract('strict_v2'), /unknown ranking contract/);
});
