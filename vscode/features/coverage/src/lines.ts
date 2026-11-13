import {object} from '../../../src/results/model';
export interface Line {file:string;line:number;hit:number;total:number;types:string[]}
export function lines(value:unknown):Line[]{
 const r=object(value);if(r.schema!=='rvw.coverage/1')throw new Error('Open a merged rvw.coverage/1 file for line decorations.');
 const rows=new Map<string,Line>();
 for(const v of Array.isArray(r.points)?r.points:[]){const p=object(v),s=object(p.scala);if(p.exclusion)continue;
 const locations=Array.isArray(s.locations)?s.locations:[s];
 for(const loc of locations){const l=object(loc);if(typeof l.file!=='string'||!Number.isInteger(l.line)||Number(l.line)<1)continue;
 const key=`${l.file}:${l.line}`,row=rows.get(key)??{file:l.file,line:Number(l.line),hit:0,total:0,types:[]};
 row.total++;if(typeof p.count==='number'&&p.count>0)row.hit++;const kind=String(object(p.fields).t??'unknown');if(!row.types.includes(kind))row.types.push(kind);rows.set(key,row);}}
 return [...rows.values()];
}
export function holes(value:unknown){const r=object(value);if(r.schema==='rvw.plan-status/1')return r;
 if(r.schema!=='rvw.functional-coverage/1')throw new Error('Expected functional coverage or rvw plan status JSON');
 return Object.fromEntries(Object.entries(object(r.groups)).map(([name,v])=>[name,{holes:object(v).holes,expected_bins:object(v).expected_bins,observed_bins:object(v).observed_bins}]));}
