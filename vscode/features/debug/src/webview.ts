import { createEngine } from '../../../../SpinalBlocks/engine/src/index';
import { workerLayout } from '../../../../SpinalBlocks/engine/src/elk';
import {lane} from './wave';
import { isTime, type Request } from './protocol';

declare function acquireVsCodeApi(): {postMessage(v:unknown):void};
async function main():Promise<void> {
const api = typeof acquireVsCodeApi === 'function' ? acquireVsCodeApi() : null;
const $ = (id:string) => document.getElementById(id)!;
const signal = $('signal') as HTMLInputElement, time = $('time') as HTMLInputElement;
let serial = 0, generation = 0, highlighting = false;
function clearEvidence(): void {
  for (const id of ['wave', 'source', 'dependencies']) $(id).replaceChildren();
}
function begin(): number {
  clearEvidence();
  $('status').textContent = 'Loading; previous evidence cleared.';
  return ++generation;
}
const pending = new Map<number, {resolve:(v:any)=>void; reject:(e:Error)=>void}>();
window.addEventListener('message', e => {
  if (e.data?.type === 'source') { run(() => fromSource(e.data.file, e.data.line)); return; }
  if(e.data?.id===-1 && e.data.error) {for(const p of pending.values()) p.reject(new Error(e.data.error));pending.clear();++generation;clearEvidence();$('status').textContent=e.data.error;return;}
  const p = pending.get(e.data?.id); if (!p) return;
  pending.delete(e.data.id);
  e.data.error ? p.reject(new Error(e.data.error)) : p.resolve(e.data);
});
async function request(a:Request):Promise<any> {
  if (!api) {
    const r = await fetch('/api', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(a)});
    const data = await r.json(); if (data.error) throw new Error(data.error); return data;
  }
  return new Promise((resolve,reject) => { const id = ++serial; pending.set(id,{resolve,reject}); api.postMessage({id,...a}); });
}
function button(label:string, action:()=>void):HTMLButtonElement {
  const b = document.createElement('button'); b.textContent = label; b.onclick = action; return b;
}
function run(action:()=>Promise<void>):void {
  const work = action(), ticket = generation;
  void work.catch(e => { if (ticket === generation) $('status').textContent = `inconclusive: ${String(e)}`; });
}
// Fetch the packaged worker before making its blob. VS Code serves resource URLs
// through a service worker that a worker cannot import directly.
const workerResponse=await fetch(document.body.dataset.worker ?? new URL('elk-worker.js',location.href).href);
if(!workerResponse.ok) throw new Error(`ELK worker: ${workerResponse.status}`);
const workerUrl=URL.createObjectURL(new Blob([await workerResponse.text()],{type:'text/javascript'}));
const engine = createEngine($('diagram'), {
  openSource: loc => run(() => fromSource(loc.file, loc.line)),
  selectionChanged: d => {
    if (highlighting || !d) return;
    if (d.loc) run(() => fromSource(d.loc!.file, d.loc!.line));
  },
  error: e => { $('status').textContent = e.message; },
}, {layout:workerLayout(workerUrl)});
async function fromSource(file:string, line:number):Promise<void> {
  const ticket = begin();
  const data = await request({op:'source', file, line});
  if (ticket !== generation) return;
  const candidates = data.result.candidates as string[];
  $('source').replaceChildren(...candidates.map(s => button(s, () => { signal.value=s; run(select); })));
  if (candidates.length === 1) { signal.value=candidates[0]; await select(); }
  else $('status').textContent = candidates.length ? 'Select a signal for this source line.' : 'Unresolved source mapping.';
}
function links(value:any, container:HTMLElement):void {
  if (!value || typeof value !== 'object') return;
  if (typeof value.path === 'string') container.append(button(value.path, () => {signal.value=value.path; run(select);}));
  if (value.assigns_to) value = {...value, assignsTo:value.assigns_to};
  if (typeof value.loc === 'string') { const m=/^(.*):(\d+)$/.exec(value.loc); if(m) container.append(button(value.loc, () => run(() => fromSource(m[1],Number(m[2]))))); }
  if (typeof value.assignsTo === 'string' && !value.assignsTo.startsWith('$')) container.append(button(value.assignsTo, () => {signal.value=value.assignsTo; run(select);}));
  if (typeof value.file === 'string' && Number.isInteger(value.line)) container.append(button(`${value.file}:${value.line}`, () => run(() => fromSource(value.file,value.line))));
  for (const item of Object.values(value)) if (item && typeof item === 'object') links(item, container);
}
async function select():Promise<void> {
  const ticket = begin();
  const start=time.value;
  if (!isTime(start)) throw new Error('Time must be an integer from 0 to 9223372036854775807.');
  const end=String(BigInt(start)+100n > 2n**63n-1n ? 2n**63n-1n : BigInt(start)+100n);
  const response = await request({op:'select', signal:signal.value, time:start, end});
  if (ticket !== generation) return;
  const r = response.result, loc = r.location;
  $('status').textContent = `${r.mapping}; ${r.where.cause ?? ''}; ${response.elapsed_ms.toFixed(1)} ms backend; database ${JSON.stringify(response.database)}`;
  $('wave').replaceChildren();
  for (const v of r.values) {
    $('wave').append(lane(v.initial,v.changes,start,v.truncated ? v.changes.at(-1).time : end,800));
    $('wave').append(button(`${v.signal} @ ${time.value} = ${v.initial ?? 'unknown'}`, () => run(select)));
    // Event cells retain exact integer times. They also form a native value lane.
    for (const c of v.changes) $('wave').append(button(`${c.time}: ${c.value}`, () => {time.value=String(c.time); run(select);}));
    if (v.truncated) $('wave').append('Window limited to 500 changes.');
  }
  $('source').replaceChildren();
  if (r.source && loc) for (const line of r.source) {
    $('source').append(button(`${line.line}: ${line.text}`, () => run(() => fromSource(loc.file,line.line))));
  } else $('source').textContent = 'Source unavailable or stale.';
  $('dependencies').replaceChildren();
  const label = document.createElement('p'); label.textContent = 'Static drivers. Select Trace active driver for dynamic evidence.';
  $('dependencies').append(label); links(r.drivers, $('dependencies'));
  const raw = document.createElement('pre'); raw.textContent=JSON.stringify(r.drivers,null,2); $('dependencies').append(raw);
  if (loc && engine.design) {
    highlighting=true;
    try { await engine.showLocation(loc.file,loc.line); } finally { highlighting=false; }
  }
}
$('jump').onclick = () => run(select);
for (const input of [signal, time]) input.addEventListener('keydown', event => {
  if (event.key === 'Enter') { event.preventDefault(); run(select); }
});
$('trace').onclick = () => run(async () => {
  const ticket = begin();
  if (!isTime(time.value)) throw new Error('Time must be an integer from 0 to 9223372036854775807.');
  $('status').textContent='Tracing. The engine reads the complete VCD. This can take up to 60 seconds.';
  const r = await request({op:'trace',signal:signal.value,time:time.value});
  if (ticket !== generation) return;
  $('dependencies').replaceChildren(); links(r.result.graph, $('dependencies'));
  const pre=document.createElement('pre'); pre.textContent=JSON.stringify(r.result,null,2); $('dependencies').append(pre);
  $('status').textContent = r.result.status;
});
run(async () => {
  const r = await request({op:'open'});
  const binding = r.result.run_binding;
  $('binding').textContent = binding ? `Wave to C1 run: ${binding.status}; ${binding.cause}. Database to run: ${binding.database}` : r.result.binding;
  $('run-evidence').textContent = JSON.stringify(binding ?? {status:'inconclusive',cause:'No C1 binding evidence'}, null, 2);
  $('status').textContent = `${r.result.binding}; ${JSON.stringify(r.result.warnings)}; ${r.elapsed_ms.toFixed(1)} ms backend`;
  $('signals').replaceChildren(...r.result.signals.map((s:any) => {const o=document.createElement('option');o.value=s.name;return o;}));
  if (r.result.blocks) await engine.setDesign(r.result.blocks);
  else $('diagram').textContent = 'No blocks artifact in this database.';
});

}
void main().catch(error=>{document.getElementById('status')!.textContent=String(error);});
