import {object,gateVerdict} from '../../../src/results/model';
export const schemas = ['rvw.run/1','rvw.results/1','rvw.verdict/2','rvw.bundle/1','rvw.cosim/1'];
export function summary(value:unknown):string {
 const r=object(value); if(!schemas.includes(String(r.schema))) throw new Error('Not a supported project result');
 const p=object(r.progress), m=object(r.mismatch);
 return `${r.schema}: ${r.schema === 'rvw.verdict/2' ? gateVerdict(r) : r.status ?? r.verdict ?? 'inconclusive'}${p.last_pc ? `; last ${p.last_pc}: ${p.last_text ?? ''}`:''}${m.pc ? `; first mismatch ${m.pc}`:''}`;
}
export function traceFile(value:unknown):string|undefined {
 const r=object(value), files=object(r.files), artifacts=object(r.artifacts);
 const file=files.retired ?? artifacts.rvfi_trace;
 return typeof file==='string' ? file : undefined;
}
