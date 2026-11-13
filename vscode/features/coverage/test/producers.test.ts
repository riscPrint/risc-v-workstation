import {test} from 'node:test';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {resolve} from 'node:path';
import {lines,holes} from '../src/lines';
import {parseReport,children} from '../../../src/results/model';
import {checkProducer} from '../../../src/results/contracts';
import {object} from '../../../src/results/model';
import {summary,traceFile} from '../../project/src/model';
import {parseLint,ruleGroups} from '../../lint/src/model';
import {workflows} from '../../workstation/src/model';

test('current Python coverage, plan and guide producers feed the actual models',()=>{
 const samples=JSON.parse(execFileSync(resolve('../rvw/.venv/bin/python'),['scripts/producer-samples.py'],{encoding:'utf8'}));
 for(const name of ['guide','functional','coverage','coverage_report','plan','lint','run','suite','csim_study'] as const) checkProducer(name,samples[name]);
 const lint=parseLint(JSON.stringify(samples.lint)), sarif=parseLint(JSON.stringify(samples.sarif));
 assert.equal(lint.status,samples.lint.status);
 assert.ok(lint.diagnostics.length>0);
 assert.equal(lint.diagnostics.filter(d=>d.waived===undefined).length,samples.lint.active_findings);
 assert.equal(ruleGroups(lint).flatMap(g=>g.findings).length,lint.diagnostics.length);
 assert.deepEqual(sarif,lint);
 assert.match(summary(samples.run),/rvw.run\/1: fail/);
 assert.equal(traceFile(samples.run),samples.run.artifacts.rvfi_trace);
 const suiteTitle=summary(samples.suite);
 for(const [status,count] of Object.entries(samples.suite_counts))assert.ok(suiteTitle.includes(`${count} ${status}`));
 const merged=parseReport('coverage',JSON.stringify(samples.coverage));
 const report=parseReport('coverage',JSON.stringify(samples.coverage_report));
 assert.equal(lines(merged)[0].hit,samples.coverage_report.summary.hit);
 assert.equal(lines(merged)[0].line,3);
 assert.deepEqual(report.summary,samples.coverage_report.summary);
 const groups=holes(samples.functional);
 for(const [name,value] of Object.entries(samples.functional.groups)) {
   const group=value as {holes:unknown;observed_bins:number};
   assert.deepEqual(object(object(groups)[name]).holes,group.holes);
   assert.equal(object(object(groups)[name]).observed_bins,group.observed_bins);
 }
 assert.deepEqual(holes(samples.plan),samples.plan);
 assert.equal(children(holes(samples.plan)).length,Object.keys(samples.plan).length);
 const guide=workflows(samples.guide);
 assert.equal(guide.length,samples.guide.workflows.length);
 assert.equal(guide.flatMap(w=>w.steps).length,samples.guide.workflows.flatMap((w:any)=>w.steps).length);
});
