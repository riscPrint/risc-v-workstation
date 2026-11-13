import {test} from 'node:test';
import assert from 'node:assert/strict';
import fixture from './fixture.json';
import {parse,coreLines} from '../src/model';
test('highlight only successful selected core labels',()=>{assert.deepEqual(coreLines(parse(JSON.stringify(fixture))),[{file:'A.scala',line:9}]);assert.deepEqual(coreLines({...fixture,status:'inconclusive'}),[]);assert.deepEqual(coreLines({...fixture,database_staleness:['stale']}),[]);assert.throws(()=>parse('{}'));});
