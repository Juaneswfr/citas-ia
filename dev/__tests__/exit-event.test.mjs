import test from 'node:test';
import assert from 'node:assert/strict';
import { createExitEvent } from '../exit-event.mjs';

test('código distinto de cero', () => {
  const e = createExitEvent({ service: 'backend', code: 1, signal: null, shuttingDown: false });
  assert.equal(e.code, 1);
  assert.equal(e.signal, null);
  assert.equal(e.expected, false);
  assert.equal(e.message, 'backend terminó con código 1');
});

test('terminación por señal', () => {
  const e = createExitEvent({ service: 'agent', code: null, signal: 'SIGKILL', shuttingDown: false });
  assert.equal(e.code, null);
  assert.equal(e.signal, 'SIGKILL');
  assert.equal(e.message, 'agent terminó por señal SIGKILL');
});

test('expected refleja shuttingDown', () => {
  assert.equal(createExitEvent({ service: 'a', code: 0, signal: null, shuttingDown: true }).expected, true);
  assert.equal(createExitEvent({ service: 'a', code: 0, signal: null, shuttingDown: false }).expected, false);
});

test('exactamente uno de code/signal es no nulo', () => {
  for (const input of [
    { service: 'a', code: 2, signal: null, shuttingDown: false },
    { service: 'a', code: null, signal: 'SIGTERM', shuttingDown: true },
  ]) {
    const e = createExitEvent(input);
    assert.equal((e.code !== null) + (e.signal !== null), 1);
  }
});
