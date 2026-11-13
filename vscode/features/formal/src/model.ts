import {object} from '../../../src/results/model';
const schemas=['rvw.formal-regress/1','rvw.formal-app-results/1','rvw.isa-signoff/1','rvw.formal/1','rvw.solver-core/1'];
export function parse(text:string){const r=object(JSON.parse(text));if(!schemas.includes(String(r.schema)))throw new Error('Unsupported formal result schema');return r;}
export function coreLines(value:unknown):{file:string;line:number}[]{const r=object(value);
 if(r.schema!=='rvw.solver-core/1'||r.status!=='pass'||(Array.isArray(r.database_staleness)&&r.database_staleness.length))return [];
 return (Array.isArray(r.design)?r.design:[]).flatMap(v=>{const d=object(v),loc=object(d.location);if(!Array.isArray(r.labels)||!r.labels.includes(d.label)||typeof loc.loc!=='string')return [];
 const m=/^(.*):(\d+)$/.exec(loc.loc);return m&&Number(m[2])>0?[{file:m[1],line:Number(m[2])}]:[];});}
