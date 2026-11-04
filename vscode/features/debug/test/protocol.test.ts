import {test} from 'node:test';
import assert from 'node:assert/strict';
import {isRequest, body} from '../src/protocol';
test('all panes and navigation requests are present',()=>{
  for(const id of ['wave','source','diagram','dependencies']) assert.ok(body.includes(`id="${id}"`));
  for(const op of ['select','trace']) assert.ok(isRequest({op,signal:'TOP.VexRiscv.execute_PC',time:'9007199254740993'}));
  assert.ok(isRequest({op:'source',file:'VexRiscv.scala',line:42}));
  assert.ok(isRequest({op:'open'}));
});
test('reject malformed requests',()=>{
  for(const a of [null,{}, {op:'trace',signal:'x',time:'-1'},{op:'source',file:'x',line:0},{op:'exec',signal:'x',time:'0'}]) assert.equal(isRequest(a),false);
});

import {position} from '../src/wave';
test('wave time positions retain precision above 2^53',()=>{assert.equal(position('9007199254740994','9007199254740993','9007199254741003'),80);});
