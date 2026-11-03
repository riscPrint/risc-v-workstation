import { test } from 'node:test';
import assert from 'node:assert/strict';
import fixture from './fixtures/report.json';
import { children, headline, parseReport } from '../../../src/results/model';
test('perf keeps event IPC basis, warnings, settings and limits',()=>{
 const report=parseReport('perf',JSON.stringify(fixture));
 assert.match(headline('perf',report),/Measurements; no correctness verdict/);
 assert.deepEqual(children(report).map(r=>r.key),Object.keys(fixture));
 assert.deepEqual(report,fixture);
});
test('comparison has no invented acceptance verdict',()=>{
 const report=parseReport('perf','{"schema":"rvw.perf.compare/1","differences":[],"significance":"practical threshold"}');
 assert.match(headline('perf',report),/no correctness verdict/);
 assert.deepEqual(children(report.differences),[]);
 assert.throws(()=>parseReport('perf','{"schema":"rvw.perf/99"}'));
});
