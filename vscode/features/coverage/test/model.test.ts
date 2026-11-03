import { test } from 'node:test';
import assert from 'node:assert/strict';
import fixture from './fixtures/report.json';
import functional from './fixtures/functional.json';
import { children, headline, label, parseReport } from '../../../src/results/model';
test('coverage keeps holes, confidence, waivers, incompatible bins and stale sources', () => {
  const report=parseReport('coverage',JSON.stringify(fixture));
  assert.match(headline('coverage',report), /no correctness verdict/);
  assert.deepEqual(children(report).map(r=>r.key),Object.keys(fixture));
  assert.deepEqual(report,fixture);
  assert.equal(label({key:'state',value:'inconclusive'}),'state: inconclusive');
  assert.equal(label({key:'missing',value:null}),'missing: null');
});
test('functional coverage keeps expected bins, hits, holes and unsupported observations', () => {
  assert.deepEqual(parseReport('coverage',JSON.stringify(functional)),functional);
  assert.throws(()=>parseReport('coverage','{"schema":"rvw.perf/1"}'));
  assert.match(headline('coverage',parseReport('coverage','{"schema":"rvw.coverage-error/1","error":"missing inputs"}')), /inconclusive: missing inputs/);
});
