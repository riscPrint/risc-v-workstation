import { test } from 'node:test';
import assert from 'node:assert/strict';
import verdict from './fixtures/verdict.json';
import suite from './fixtures/suite.json';
import { children, headline, parseReport, queryArgs, sourceMatches, sourceTargets } from '../../../src/results/model';
import { createHash } from 'node:crypto';
test('C4 keeps inconclusive verdict, passing tests, unchanged failures and causes', () => {
  const report = parseReport('regress', JSON.stringify(verdict));
  assert.match(headline('regress', report), /inconclusive; tests: pass/);
  assert.deepEqual(children(report).map(r => r.key), Object.keys(verdict));
  assert.deepEqual(report, verdict);
});
test('C3 keeps incomplete evidence and never issues a gate verdict', () => {
  assert.match(headline('regress', parseReport('regress', JSON.stringify(suite))), /1 pass, 1 inconclusive; no gate verdict/);
  assert.match(headline('regress', {schema:'rvw.results/1',tests:[]}), /inconclusive/);
  assert.match(headline('regress', {schema:'rvw.verdict/2',verdict:'unknown'}), /inconclusive/);
  assert.throws(() => parseReport('regress','{"schema":"rvw.verdict/1"}'));
  assert.throws(() => parseReport('regress','{}'));
  assert.throws(() => parseReport('regress','{'));
});
test('where requires current captured non-pruned source and keeps arguments literal', () => {
  const bytes=Buffer.from('// fixture\n'), sha256=createHash('sha256').update(bytes).digest('hex');
  const signal={loc:'/tmp/Unit.scala:9',source:{source:'/tmp/Unit.scala',sha256}};
  const targets=sourceTargets({signal});
  assert.deepEqual(targets,[{file:'/tmp/Unit.scala',line:9,sha256}]);
  assert.ok(sourceMatches(targets[0],bytes));
  assert.equal(sourceMatches(targets[0],Buffer.from('changed')),false);
  for (const result of [{status:'inconclusive',signal},{signal:{...signal,pruned:true}},{db_warnings:['stale'],signal},{signal:{stored_loc:signal.loc}},{signal:{...signal,source:{}}},{error:'unresolved'}]) assert.deepEqual(sourceTargets(result),[]);
  assert.deepEqual(sourceTargets({signals:[signal]}),targets);
  assert.deepEqual(queryArgs('/tmp/a b.db','x; echo bad'),['query','where','--db','/tmp/a b.db','--json','--','x; echo bad']);
});
