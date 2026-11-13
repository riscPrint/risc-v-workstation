import {test} from 'node:test';
import assert from 'node:assert/strict';
import fixture from './fixtures/lines.json';
import {lines,holes} from '../src/lines';
test('mixed line and toggle points retain partial hit counts',()=>{assert.deepEqual(lines(fixture),[{file:'A.scala',line:3,hit:1,total:2,types:['line','toggle']}]);assert.throws(()=>lines({}));assert.deepEqual(holes({schema:'rvw.functional-coverage/1',groups:{a:{holes:[[1]],expected_bins:2,observed_bins:1}}}),{a:{holes:[[1]],expected_bins:2,observed_bins:1}});});
