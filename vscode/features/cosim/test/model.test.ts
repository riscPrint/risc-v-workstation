import {test} from 'node:test';
import assert from 'node:assert/strict';
import fixture from './fixture.json';
import {parse,render,instructionLine} from '../src/model';
test('show actual and expected state and locate exact PC',()=>{const r=parse(JSON.stringify(fixture));const html=render(r);assert.match(html,/DUT/);assert.match(html,/Reference/);assert.match(html,/&lt;script&gt;/);assert.equal(instructionLine('00000080: add x1,x2,x3','0x80'),0);assert.throws(()=>instructionLine('180: add','0x80'));assert.throws(()=>parse('{}'));});
