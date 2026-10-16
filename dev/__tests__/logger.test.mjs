import test from 'node:test';
import assert from 'node:assert/strict';
import { createLineLogger, createSystemLogger } from '../logger.mjs';

const collect = () => {
  const out = [];
  return { out, write: (l) => out.push(l) };
};

test('chunk partido a mitad de línea produce una sola línea con un prefijo', () => {
  const { out, write } = collect();
  const log = createLineLogger({ name: 'backend', color: 32, write, useColor: false });
  log.push('hola ');
  assert.equal(out.length, 0);
  log.push('mundo\n');
  assert.equal(out.length, 1);
  assert.match(out[0], /^\[backend\]\s+hola mundo\n$/);
});

test('varias líneas en un chunk', () => {
  const { out, write } = collect();
  const log = createLineLogger({ name: 'frontend', write, useColor: false });
  log.push('a\nb\nc\n');
  assert.equal(out.length, 3);
  assert.ok(out.every((l) => l.startsWith('[frontend]')));
});

test('flush emite el resto parcial', () => {
  const { out, write } = collect();
  const log = createLineLogger({ name: 'agent', write, useColor: false });
  log.push('sin salto');
  log.flush();
  assert.equal(out.length, 1);
  assert.match(out[0], /sin salto\n$/);
  log.flush();
  assert.equal(out.length, 1);
});

test('sin color no hay secuencias ANSI; con color cada línea lleva el color', () => {
  const plain = collect();
  createLineLogger({ name: 'x', color: 36, write: plain.write, useColor: false }).push('l\n');
  assert.ok(!plain.out[0].includes('\x1b['));

  const colored = collect();
  const log = createLineLogger({ name: 'x', color: 36, write: colored.write, useColor: true });
  log.push('1\n2\n');
  assert.equal(colored.out.length, 2);
  for (const l of colored.out) {
    assert.ok(l.includes('\x1b[36m'));
    assert.ok(l.includes('\x1b[0m'));
  }
});

test('logger del sistema usa prefijo [dev]', () => {
  const { out, write } = collect();
  createSystemLogger(write, false)('mensaje');
  assert.match(out[0], /^\[dev\]\s+mensaje\n$/);
});
