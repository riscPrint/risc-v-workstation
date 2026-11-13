import {test} from 'node:test';
import assert from 'node:assert/strict';
import fixture from './fixture.json';
import {summary,traceFile} from '../src/model';
test('bundle summary and declared trace',()=>{assert.match(summary(fixture),/last 0x80: add/);assert.equal(traceFile(fixture),'retired.txt');assert.throws(()=>summary({}));assert.equal(traceFile({}),undefined);});
