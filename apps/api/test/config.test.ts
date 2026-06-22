import assert from 'node:assert/strict';
import { test } from 'node:test';
import { DEFAULT_API_PORT, parseApiPort } from '../src/config';

test('parseApiPort preserves valid explicit ports', () => {
  assert.equal(parseApiPort('0'), 0);
  assert.equal(parseApiPort('3001'), 3001);
  assert.equal(parseApiPort('65535'), 65535);
});

test('parseApiPort falls back for missing or invalid ports', () => {
  assert.equal(parseApiPort(undefined), DEFAULT_API_PORT);
  assert.equal(parseApiPort(''), DEFAULT_API_PORT);
  assert.equal(parseApiPort('abc'), DEFAULT_API_PORT);
  assert.equal(parseApiPort('3000.5'), DEFAULT_API_PORT);
  assert.equal(parseApiPort('65536'), DEFAULT_API_PORT);
});
