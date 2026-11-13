import {checkProducer} from '../../../src/results/contracts';
import {object} from '../../../src/results/model';
import {page,table,escape} from '../../../src/results/html';
export function parse(text:string){const r=object(JSON.parse(text));if(!['rvw.perf/1','rvw.arch-run/1','rvw.arch-compare/1','rvw.ooo-run/1','rvw.csim-study-report/1','rvw.csim-sweep/1','rvw.csim-compare/1'].includes(String(r.schema)))throw new Error('Unsupported architecture or component study report');if(r.schema==='rvw.csim-study-report/1')checkProducer('csim_study',r);return r;}
export function render(r:Record<string,unknown>):string {
 const rows=Array.isArray(r.rows)?r.rows:Array.isArray(r.benchmarks)?r.benchmarks:Array.isArray(r.results)?r.results:[];
 const keys=[...new Set(rows.flatMap(row=>Object.keys(object(row))))];
 const summary=object(r.summary ?? object(r.aggregate).mean);
 return page('Architecture designer report',`<p>${escape(r.schema)}. Engine: ${escape(typeof r.engine==='object'?JSON.stringify(r.engine):r.engine)}. Model trends do not establish RTL correctness.</p><h2>IPC and counters</h2>${table(['Field','Recorded value'],Object.entries(Object.keys(summary).length?summary:{ipc:r.ipc,cycles:r.cycles,instret:r.instret}))}<h2>Top-down</h2><pre>${escape(JSON.stringify(r.top_down ?? r.topdown ?? 'unavailable: no producer top-down report',null,2))}</pre><h2>Bottlenecks and explicit causes</h2><pre>${escape(JSON.stringify(r.bottlenecks ?? r.stall_causes ?? 'unavailable: no producer attribution',null,2))}</pre><h2>Study rows</h2>${table(keys,rows.map(row=>keys.map(k=>object(row)[k])))}<h2>Full report and limits</h2><pre>${escape(JSON.stringify(r,null,2))}</pre>`);
}
