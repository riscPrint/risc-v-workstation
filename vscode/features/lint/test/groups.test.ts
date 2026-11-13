import {test} from 'node:test';
import assert from 'node:assert/strict';
import fixture from './groups.json';
import {parseLint,ruleGroups,waiver} from '../src/model';
test('group CDC and SDC findings without dropping backend or waiver identity',()=>{const s=parseLint(JSON.stringify(fixture));const g=ruleGroups(s);assert.deepEqual(g.map(v=>v.rule),['cdc.unsafe','sdc.missing_clock']);assert.equal(g[1].findings[0].backend,'sdc');assert.equal(waiver(g[0].findings[0],s.config).finding_id,'a');assert.deepEqual(ruleGroups({...s,diagnostics:[]}),[]);});
