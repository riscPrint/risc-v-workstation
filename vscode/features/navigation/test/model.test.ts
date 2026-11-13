import {test} from 'node:test';
import assert from 'node:assert/strict';
import fixture from './signals.json';
import {candidates,dependencyArgs} from '../src/model';
test('retain every instance candidate and use argv without a shell',()=>{
 assert.deepEqual(candidates(fixture),['top.a','top.b']);
 assert.deepEqual(candidates(null),[]);
 assert.deepEqual(dependencyArgs('loads','a b.db','top.a'),['query','loads','--db','a b.db','--json','--','top.a']);
});
