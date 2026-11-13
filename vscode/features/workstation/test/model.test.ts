import {test} from 'node:test';
import assert from 'node:assert/strict';
import fixture from './fixture.json';
import {workflows,stepKey} from '../src/model';
test('guide retains commands and decisions without executing them',()=>{const w=workflows(fixture);assert.deepEqual(w[0].steps[0].cli,['bundle','<RUN>']);assert.deepEqual(w[0].steps[0].decide,[{then:'stop'}]);assert.notEqual(stepKey('a:b','c'),stepKey('a','b:c'));assert.throws(()=>workflows({}));});
