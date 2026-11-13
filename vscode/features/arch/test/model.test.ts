import {test} from 'node:test';
import assert from 'node:assert/strict';
import fixture from './fixture.json';
import {parse,render} from '../src/model';
test('study table retains errors and unavailable attribution',()=>{const html=render(parse(JSON.stringify(fixture)));assert.match(html,/miss_rate/);assert.match(html,/&lt;missing&gt;/);assert.match(html,/unavailable: no producer top-down/);assert.throws(()=>parse('{}'));});


import {execFileSync} from 'node:child_process';
import {resolve} from 'node:path';
test('accept the current component study producer schema without native execution',()=>{
 const report=JSON.parse(execFileSync(resolve('../rvw/.venv/bin/python'),['-c',
   "import json; from rvw.csim.study import run; print(json.dumps(run({'branch':{'model':'bimodal'}},[])))"],{encoding:'utf8'}));
 assert.equal(report.schema,'rvw.csim-study-report/1');
 assert.deepEqual(parse(JSON.stringify(report)),report);
 assert.match(render(report),/rvw.csim-study-report\/1/);
 assert.doesNotMatch(render(report),/Engine: \[object Object\]/);
});
test('component results and aggregate metrics appear in the table',()=>{
 const report={schema:'rvw.csim-study-report/1',rtl_comparison:'inconclusive',aggregate:{mean:{direction_mpki:3.25}},
   results:[{input:{path:'branches.csim'},branch:{direction:{mpki:3.25}}}]};
 const html=render(parse(JSON.stringify(report)));
 assert.match(html,/branches.csim/);
 assert.match(html,/direction_mpki/);
 assert.match(html,/3.25/);
});
