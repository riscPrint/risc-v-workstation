import { test } from 'node:test';
import assert from 'node:assert/strict';
import report from './fixtures/report.json';
import sarif from './fixtures/report.sarif.json';
import { headline, messageText, parseLint } from '../src/model';

test('rvw.lint/1 report gives located, waived and unlocated diagnostics', () => {
  const s = parseLint(JSON.stringify(report));
  assert.equal(s.status, 'findings');
  assert.equal(s.diagnostics.length, 5);
  const [native, cdc, waived, info, stale] = s.diagnostics;
  assert.deepEqual([native.file, native.line, native.column], ['rtl/Top.v', 12, 7]);
  assert.deepEqual([cdc.file, cdc.line, cdc.severity], ['/src/Top.scala', 20, 'warning']);
  assert.equal(waived.severity, 'hint');
  assert.match(messageText(waived), /waived: reviewed/);
  assert.equal(info.severity, 'info');
  assert.equal(info.file, undefined);
  assert.equal(stale.severity, 'error');
  assert.equal(headline(s), 'Lint findings: 4 active, 1 waived; not run: verible');
});

test('SARIF log gives the same diagnostics', () => {
  const s = parseLint(JSON.stringify(sarif));
  assert.equal(s.diagnostics[0].file, '/src/Top A.scala');
  assert.equal(s.diagnostics[0].line, 20);
  assert.equal(s.diagnostics[1].severity, 'hint');
  assert.match(headline(s), /not run: verible/);
});

test('errors and unknown inputs never look clean', () => {
  assert.throws(() => parseLint('{"status":"error","error":"bad settings"}'), /bad settings/);
  assert.throws(() => parseLint('{"schema":"rvw.perf/1"}'), /not an rvw.lint/);
  const s = parseLint(JSON.stringify({...report, status: 'inconclusive', backends: {}, waiver_findings: []}));
  assert.match(headline(s), /^Lint inconclusive/);
});
