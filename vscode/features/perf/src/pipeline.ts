import {page,table} from '../../../src/results/html';
interface Span {lane:string;stage:string;start:number;end?:number}
interface Instruction {id:string;label:string;start:number;end?:number;flushed?:boolean;spans:Span[];active:Map<string,Span>}
export function pipeline(text:string,from:number,to:number){
 if(!Number.isSafeInteger(from)||!Number.isSafeInteger(to)||from<0||to<from||to-from>=80)throw new Error('Choose a window of 1 to 80 cycles.');
 const records=text.replace(/^\uFEFF/,'').split(/\r?\n/);if(records.shift()!=='Kanata\t0004')throw new Error('Expected Kanata 0004 log');
 let cycle=0;const instructions=new Map<string,Instruction>(),stalls=new Map<string,Set<number>>();
 for(const line of records){const f=line.split('\t'),cmd=f[0];if(!line)continue;
 if(cmd==='C'||cmd==='C='){const next=(cmd==='C'?cycle:0)+Number(f[1]);if(!Number.isSafeInteger(next)||next<cycle)throw new Error('Invalid cycle record');cycle=next;if(cycle>to)break;continue;}
 if(cmd==='#rvw'&&f[1]==='1'&&f[2]==='stall'&&cycle>=from){const key=`${f[3]} / ${f[4]} / ${f[5]}`,set=stalls.get(key)??new Set<number>();set.add(cycle);stalls.set(key,set);continue;}
 if(cmd==='I'){if(instructions.has(f[1]))throw new Error('Duplicate instruction ID');instructions.set(f[1],{id:f[1],label:'',start:cycle,spans:[],active:new Map()});continue;}
 if(!['L','S','E','R'].includes(cmd))continue;const ins=instructions.get(f[1]);if(!ins)throw new Error('Instruction event has no I record');
 if(cmd==='L'&&f[2]==='0')ins.label+=f.slice(3).join('\t');
 if(cmd==='S'){const prev=ins.active.get(f[2]);if(prev)prev.end=cycle;const span={lane:f[2],stage:f[3],start:cycle};ins.spans.push(span);ins.active.set(f[2],span);}
 if(cmd==='E'){const span=ins.active.get(f[2]);if(!span||span.stage!==f[3])throw new Error('Unmatched stage end');span.end=cycle;ins.active.delete(f[2]);}
 if(cmd==='R'){if(!['0','1'].includes(f[3]))throw new Error('Invalid retirement type');ins.end=cycle;ins.flushed=f[3]==='1';for(const span of ins.active.values())span.end=cycle;ins.active.clear();}
 }
 const selected=[...instructions.values()].filter(i=>i.start<=to&&(i.end===undefined||i.end>=from));
 const cycles=Array.from({length:to-from+1},(_,i)=>from+i);
 const rows=selected.slice(0,500).map(ins=>[`${ins.id}: ${ins.label}`,ins.end===undefined?'open at window end':ins.flushed?'discarded':'R type 0',...cycles.map(t=>ins.spans.filter(s=>s.start<=t&&(s.end===undefined||t<s.end)).map(s=>`${s.lane}:${s.stage}${s.end===undefined?'?':''}`).join(' '))]);
 return {cycles,rows,truncated:selected.length>500,stalls:[...stalls].map(([key,set])=>[key,set.size])};
}
export function renderPipeline(result:ReturnType<typeof pipeline>){return page('Pipeline window',`<p>Stage intervals are half-open. ? means no stage end in this window. R type 0 is a producer retirement event. Missing causes stay unknown. ${result.truncated?'Only first 500 instructions shown.':''}</p>${table(['Instruction','State',...result.cycles.map(String)],result.rows)}<h2>Explicit stall samples in window</h2>${table(['Scope / cause / evidence','Unique cycles'],result.stalls)}<p>Causes can overlap. No causal attribution is inferred from stage duration.</p>`);}
