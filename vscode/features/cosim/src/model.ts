import {object} from '../../../src/results/model';
import {page,table,escape} from '../../../src/results/html';
export function parse(text:string){const r=object(JSON.parse(text));if(r.schema!=='rvw.cosim/1')throw new Error('Expected rvw.cosim/1');return r;}
export function render(r:Record<string,unknown>):string {
 const m=object(r.mismatch),actual=object(m.actual),expected=object(m.expected);
 const fields=[...new Set([...Object.keys(actual),...Object.keys(expected)])];
 const differences=Object.entries(object(m.differences)).map(([key,value])=>[key,object(value).actual,object(value).expected]);
 return page('First cosim divergence',`<p>Status: ${escape(r.status ?? 'inconclusive')}. PC: ${escape(m.pc)}. Order: ${escape(m.order)}.</p><pre>${escape(m.disassembly)}</pre>${table(['Field','DUT','Reference'],[...fields.map(k=>[k,actual[k],expected[k]]),...differences])}${table(['Register','DUT','Reference'],(Array.isArray(m.register_diff)?m.register_diff:[]).map(v=>{const d=object(v);return [d.reg,d.actual,d.expected];}))}<pre>${escape(JSON.stringify(r,null,2))}</pre>`);
}
export function instructionLine(text:string,pc:unknown):number {
 if(typeof pc!=='string'||!/^0x[0-9a-f]+$/i.test(pc))throw new Error('No mismatch PC');
 const address=BigInt(pc);
 const i=text.split(/\r?\n/).findIndex(line=>{const m=/^\s*([0-9a-f]+):\s/i.exec(line);return !!m&&BigInt('0x'+m[1])===address;});
 if(i<0)throw new Error('PC is absent from this disassembly');return i;
}
