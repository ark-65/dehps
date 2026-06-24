import assert from 'node:assert/strict';
import { test } from 'node:test';
import { DEFAULT_API_PORT, DEFAULT_DB_PORT, parseApiPort, parseDbPort } from '../src/config';

test('parseApiPort preserves valid explicit ports', () => {
  assert.equal(parseApiPort('0'), 0);
  assert.equal(parseApiPort(' 3001 '), 3001);
  assert.equal(parseApiPort('3001'), 3001);
  assert.equal(parseApiPort('65535'), 65535);
});

test('parseApiPort falls back for missing or invalid ports', () => {
  assert.equal(parseApiPort(undefined), DEFAULT_API_PORT);
  assert.equal(parseApiPort(''), DEFAULT_API_PORT);
  assert.equal(parseApiPort('abc'), DEFAULT_API_PORT);
  assert.equal(parseApiPort('3000.5'), DEFAULT_API_PORT);
  assert.equal(parseApiPort('0x10'), DEFAULT_API_PORT);
  assert.equal(parseApiPort('1e3'), DEFAULT_API_PORT);
  assert.equal(parseApiPort('65536'), DEFAULT_API_PORT);
});

test('parseDbPort uses the project database default and rejects invalid values', () => {
  assert.equal(parseDbPort(undefined), DEFAULT_DB_PORT);
  assert.equal(parseDbPort(' 54329 '), 54329);
  assert.equal(parseDbPort('abc'), DEFAULT_DB_PORT);
  assert.equal(parseDbPort('54329.5'), DEFAULT_DB_PORT);
  assert.equal(parseDbPort('65536'), DEFAULT_DB_PORT);
});
