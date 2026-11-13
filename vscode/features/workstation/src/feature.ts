import * as vscode from 'vscode';
import {execFile} from 'node:child_process';
import type {Feature} from '../../../src/api';
import guide from '../../../../rvw/src/rvw/agent/playbook.json';
import {workflows,stepKey,type Step,type Workflow} from './model';
interface Entry {label:string;command?:string;workflow?:Workflow;step?:Step;key?:string}
const tools:Entry[]=[['Project results','project.refresh'],['Cosim mismatch','cosim.open'],['Coverage lines','coverage.decorate'],['Functional coverage holes','coverage.holes'],['Verification plan','coverage.plan'],['Formal properties','formal.open'],['Lint / CDC / RDC / SDC','lint.open'],['Architecture report','arch.open'],['Component study','arch.study'],['Pipeline window','perf.pipeline'],['Saved performance','perf.open'],['Wave queries','wave.new'],['Block diagrams','spinalblocks.open'],['Start design language server','lsp.start']].map(([label,command])=>({label,command}));
const feature:Feature={id:'workstation',activate(context){
 let guideWorkflows=workflows(guide),checked=new Set(context.workspaceState.get<string[]>('checked',[]));
 const changed=new vscode.EventEmitter<Entry|undefined>();
 const provider:vscode.TreeDataProvider<Entry>={onDidChangeTreeData:changed.event,
 getChildren:entry=>entry?.workflow?entry.workflow.steps.map(step=>({label:step.do,step,key:stepKey(entry.workflow!.id,step.id)})):entry?[]:[...tools,...guideWorkflows.map(workflow=>({label:workflow.title,workflow}))],
 getTreeItem:entry=>{const item=new vscode.TreeItem(entry.label,entry.workflow?1:0);
 if(entry.command)item.command={command:entry.command,title:entry.label};
 if(entry.step){item.checkboxState=checked.has(entry.key!)?vscode.TreeItemCheckboxState.Checked:vscode.TreeItemCheckboxState.Unchecked;item.description=entry.step.cli?`rvw ${entry.step.cli.join(' ')}`:'manual';item.tooltip=JSON.stringify(entry.step,null,2);}
 return item;}};
 const view=vscode.window.createTreeView('workstation.results',{treeDataProvider:provider,manageCheckboxStateManually:true});
 view.message='Checklist marks record manual progress. They do not establish a pass.';
 context.subscriptions.push(changed,view,view.onDidChangeCheckboxState(async event=>{for(const [entry,state]of event.items)if(entry.key){if(state===vscode.TreeItemCheckboxState.Checked)checked.add(entry.key);else checked.delete(entry.key);}await context.workspaceState.update('checked',[...checked]);changed.fire(undefined);}));
 const command=(name:string,fn:()=>Promise<unknown>)=>context.subscriptions.push(vscode.commands.registerCommand(`workstation.${name}`,async()=>{try{await fn();}catch(e){void vscode.window.showErrorMessage(`Workstation: ${String(e)}`);}}));
 command('reset',async()=>{checked.clear();await context.workspaceState.update('checked',[]);changed.fire(undefined);});
 command('guide',async()=>{const file=(await vscode.window.showOpenDialog({title:'Saved rvw agent guide --json',canSelectMany:false,filters:{JSON:['json']}}))?.[0];if(!file)return;guideWorkflows=workflows(JSON.parse(Buffer.from(await vscode.workspace.fs.readFile(file)).toString()));changed.fire(undefined);});
 command('refreshGuide',async()=>{if(!vscode.workspace.isTrusted)throw new Error('Trust the workspace before running rvw.');
 const result=await new Promise<string>((resolve,reject)=>execFile(vscode.workspace.getConfiguration('workstation').get('rvwExecutable','rvw'),['agent','guide','--json'],{cwd:vscode.workspace.workspaceFolders?.[0]?.uri.fsPath,timeout:30000,maxBuffer:4*1024*1024},(err,out,stderr)=>err?reject(new Error(stderr||err.message)):resolve(out)));
 guideWorkflows=workflows(JSON.parse(result));changed.fire(undefined);});
}};export default feature;
