import {object} from '../../../src/results/model';
export interface Step {id:string;do:string;cli?:string[];decide?:unknown}
export interface Workflow {id:string;title:string;steps:Step[]}
export function workflows(value:unknown):Workflow[]{const r=object(value);if(r.schema!=='rvw.agent-guide/1'||!Array.isArray(r.workflows))throw new Error('Expected rvw.agent-guide/1');
 return r.workflows.map(v=>{const w=object(v);if(typeof w.id!=='string'||typeof w.title!=='string'||!Array.isArray(w.steps))throw new Error('Invalid workflow');
 const steps=w.steps.map(value=>{const s=object(value);if(typeof s.id!=='string'||typeof s.do!=='string')throw new Error('Invalid workflow step');return s as unknown as Step;});return {id:w.id,title:w.title,steps};});}
export function stepKey(workflow:string,step:string):string{return JSON.stringify([workflow,step]);}
