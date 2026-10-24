import { test } from 'node:test';
import assert from 'node:assert/strict';
import { isFromWebview, isToWebview } from '../src/protocol';

test('binary payload survives the structured message transport', () => {
  const value = structuredClone({type:'load', bytes:new Uint8Array([31,139,0,255]).buffer});
  assert.ok(isToWebview(value) && value.type === 'load');
  assert.deepEqual(Array.from(new Uint8Array(value.bytes)), [31,139,0,255]);
  for (const bytes of [[-1],[256],[1.2],{},null]) assert.equal(isToWebview({type:'load',bytes}), false);
});
test('source requests require a file and a positive integer line', () => {
  assert.ok(isFromWebview({type:'openSource',loc:{file:'/src/Core.scala',line:12}}));
  for (const line of [0,-1,Infinity,1.5,'12']) assert.equal(isFromWebview({type:'openSource',loc:{file:'/src/Core.scala',line}}), false);
  assert.equal(isFromWebview({type:'openSource',loc:null}), false);
});
test('navigation, hierarchy and search target shapes are checked', () => {
  assert.ok(isFromWebview({type:'navigated',path:['tile','core'],modules:['Top','Tile','Core']}));
  assert.equal(isFromWebview({type:'navigated',path:['tile'],modules:[]}), false);
  assert.ok(isFromWebview({type:'hierarchy',root:{name:'Top',module:'Top',path:[],children:[]}}));
  assert.equal(isFromWebview({type:'hierarchy',root:{children:[]}}), false);
  assert.ok(isToWebview({type:'pick',target:{kind:'blockPort',block:'inst:core',port:'io'}}));
  assert.equal(isToWebview({type:'pick',target:{kind:'blockPort',id:'oops'}}), false);
  assert.ok(isFromWebview({type:'searchResults',request:3,hits:[{text:'core',kind:'instance',context:'Core',target:{kind:'block',id:'inst:core'}}]}));
  for (const value of [null,[],{}, {type:'execute',code:'bad'}]) { assert.equal(isFromWebview(value), false); assert.equal(isToWebview(value), false); }
});
test('saved view validates viewport and nested state before restoring it', () => {
  const saved = {state:{path:['tile','core'],options:{showClocks:false,showControl:true,maxPortsPerSide:10,maxBlocks:80},modules:{Core:{areas:{'area:rob':true},bundles:{}}}},viewport:{x:1,y:2,zoom:0.5},labels:true};
  assert.ok(isFromWebview({type:'save',saved}));
  assert.ok(isToWebview({type:'load',bytes:new ArrayBuffer(0),saved}));
  assert.equal(isFromWebview({type:'save',saved:{...saved,viewport:{x:1,y:2,zoom:0}}}), false);
  assert.equal(isToWebview({type:'load',bytes:new ArrayBuffer(0),saved:{...saved,state:{...saved.state,modules:{Core:{areas:null}}}}}), false);
});

test('editor and FSM requests validate locations and identifiers', () => {
  assert.ok(isToWebview({type:'showLocation',file:'/src/Core.scala',line:24}));
  assert.ok(isToWebview({type:'showFsm',module:'Core',fsm:'fsm:ctrl'}));
  for (const line of [0,-1,2.5,Infinity,'24']) assert.equal(isToWebview({type:'showLocation',file:'/src/Core.scala',line}), false);
  assert.equal(isToWebview({type:'showFsm',module:'Core',fsm:null}), false);
  assert.ok(isFromWebview({type:'selected',kind:'fsm',file:'/src/Core.scala',line:24,found:true}));
  assert.equal(isFromWebview({type:'selected',kind:'other',file:'/src/Core.scala',line:24,found:true}), false);
  assert.equal(isFromWebview({type:'selected',kind:'block',file:'/src/Core.scala',line:24,found:'yes'}), false);
  assert.ok(isFromWebview({type:'revealTree',path:['tile','core']}));
  assert.equal(isFromWebview({type:'revealTree',path:['tile',1]}), false);
});
test('exports accept only supported formats and binary PNG transport', () => {
  for (const format of ['svg','png']) assert.ok(isToWebview({type:'exportImage',format}));
  for (const format of ['jpeg','',null,1]) assert.equal(isToWebview({type:'exportImage',format}), false);
  assert.ok(isFromWebview(structuredClone({type:'exportPng',bytes:new Uint8Array([137,80,78,71]).buffer,name:'Core'})));
  assert.equal(isFromWebview({type:'exportPng',bytes:[137,80,78,71],name:'Core'}), false);
});
