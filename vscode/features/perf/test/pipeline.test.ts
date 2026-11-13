import {test} from 'node:test';
import assert from 'node:assert/strict';
import fixture from './fixtures/pipeline.json';
import {pipeline,renderPipeline} from '../src/pipeline';
test('half-open spans and explicit cause evidence',()=>{const r=pipeline(fixture.log,0,2);assert.deepEqual(r.rows[0].slice(2),['0:F','0:Ex','']);assert.deepEqual(r.stalls,[['core / busy / measured',1]]);assert.match(renderPipeline(r),/No causal attribution/);assert.throws(()=>pipeline(fixture.log,0,80));assert.throws(()=>pipeline('bad',0,2));assert.equal(pipeline(fixture.log,1,1).rows[0][2],'0:Ex?');});
