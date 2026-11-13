import {test} from 'node:test';
import assert from 'node:assert/strict';
import fixture from './fixture.json';
import {parse,render} from '../src/model';
test('study table retains errors and unavailable attribution',()=>{const html=render(parse(JSON.stringify(fixture)));assert.match(html,/miss_rate/);assert.match(html,/&lt;missing&gt;/);assert.match(html,/unavailable: no producer top-down/);assert.throws(()=>parse('{}'));});
