import { test } from 'node:test';
import assert from 'node:assert/strict';
import why from './fixtures/why.json';
import txn from './fixtures/txn.json';
import find from './fixtures/find.json';
import { children, cutArgv, headline, label, parseQuery, queryArgv, rowLocation, rowSignal, rowTime } from '../src/model';

test('saved queries become argument arrays, never shell text', () => {
  const q = parseQuery(JSON.stringify({schema: 'rvw.wave-query/1', kind: 'why', wave: 'run/wave.vcd', args: ['x; rm -rf /'],
    options: {at: '18', db: 'design.db', depth: 1, indexed: false}}));
  assert.deepEqual(queryArgv(q, '/w'), ['wave', 'why', '/w/run/wave.vcd', 'x; rm -rf /', '--at', '18', '--db', '/w/design.db', '--depth', '1', '--json']);
  const d = parseQuery(JSON.stringify({schema: 'rvw.wave-query/1', kind: 'diff', wave: '/a.vcd', args: ['b.vcd'], options: {'on-clock': true}}));
  assert.deepEqual(queryArgv(d, '/w'), ['wave', 'diff', '/a.vcd', '/w/b.vcd', '--on-clock', '--json']);
  assert.throws(() => parseQuery('{"schema":"rvw.wave-query/1","kind":"rm","wave":"a"}'), /Unknown/);
  assert.throws(() => parseQuery('{"schema":"rvw.wave-query/1","kind":"find","wave":"a","options":{"--x":1}}'), /Invalid option/);
  assert.throws(() => parseQuery('{"schema":"other","kind":"find","wave":"a"}'), /schema/);
});

test('why results expose driver locations, signals and times', () => {
  assert.match(headline('why', why), /x @ 18: active \(binding unverified\)/);
  const trace = {key: 'trace', value: why.trace};
  assert.equal(label(trace), 'x = 0x4 (set at 15) [active]');
  assert.equal(rowSignal(trace), 'x');
  assert.equal(rowTime(trace), 18);
  const assignment = children(why.trace.assignments).find(r => (r.value as {id: number}).id === why.trace.active)!;
  assert.match(label(assignment), /^:= x - y \[holds: true\]/);
  assert.deepEqual(rowLocation(assignment), {file: '/repo/SpinalTrace/examples/src/spinaltrace/examples/Gcd.scala', line: 20});
});

test('txn and find rows carry times; no pass wording', () => {
  assert.match(headline('txn', txn), /Stream: 1 transfers, 2 issues/);
  const issue = children(txn.issues)[0];
  assert.equal(label(issue), '45: payload_changed');
  assert.equal(rowTime(issue), 45);
  assert.equal(label(children(find.matches)[0]), '5 .. 15');
  assert.equal(headline('diff', {status: 'no_points'}), 'inconclusive: no points compared');
  assert.doesNotMatch(headline('diff', {status: 'match', points_compared: 3}), /pass/i);
  assert.deepEqual(cutArgv('w.vcd', 50, 100, '/t/o.vcd'), ['wave', 'cut', 'w.vcd', '--from', '0', '--to', '150', '-o', '/t/o.vcd', '--json']);
});
