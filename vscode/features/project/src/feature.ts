import * as vscode from 'vscode';
import {dirname,resolve} from 'node:path';
import type {Feature} from '../../../src/api';
import {children,label,type Row,object} from '../../../src/results/model';
import {summary,traceFile} from './model';
type Entry=Row & {file:vscode.Uri; root?:boolean};
const feature:Feature={id:'project',activate(context){
 let entries:Entry[]=[];
 const changed=new vscode.EventEmitter<Entry|undefined>();
 const provider:vscode.TreeDataProvider<Entry>={onDidChangeTreeData:changed.event,
 getChildren:row=>row?children(row.value).map(c=>({...c,file:row.file})):entries,
 getTreeItem:row=>{const item=new vscode.TreeItem(row.root?row.key:label(row),children(row.value).length?1:0);
 item.contextValue='project.result';item.tooltip=row.file.fsPath;
 if(row.root) item.command={command:'project.inspect',title:'Inspect',arguments:[row]};return item;}};
 context.subscriptions.push(changed,vscode.window.createTreeView('project.results',{treeDataProvider:provider}));
 const command=(name:string,fn:(row?:Entry)=>Promise<unknown>)=>context.subscriptions.push(vscode.commands.registerCommand(`project.${name}`,async row=>{try{await fn(row);}catch(e){void vscode.window.showErrorMessage(`Project results: ${String(e)}`);}}));
 async function load(file:vscode.Uri){const value=JSON.parse(Buffer.from(await vscode.workspace.fs.readFile(file)).toString());return {key:summary(value),value,file,root:true};}
 command('refresh',async()=>{entries=[];changed.fire(undefined);
 const files=await vscode.workspace.findFiles('**/{result,results,verdict,summary,cosim}.json','**/{node_modules,.git}/**',500);
 for(const file of files) {try{entries.push(await load(file));}catch{/* unrelated JSON */}}
 if(!entries.length) void vscode.window.showInformationMessage('No saved project results found. Use rvw to produce results, or open a saved result.');changed.fire(undefined);});
 command('open',async()=>{const file=(await vscode.window.showOpenDialog({canSelectMany:false,filters:{JSON:['json']}}))?.[0];if(file){entries.push(await load(file));changed.fire(undefined);}});
 command('inspect',async row=>{if(!row)return;const doc=await vscode.workspace.openTextDocument({language:'json',content:JSON.stringify(row.value,null,2)});await vscode.window.showTextDocument(doc);});
 command('trace',async row=>{if(!row)return;const file=traceFile(row.value) ?? (typeof row.value==='string'?row.value:undefined);if(!file)throw new Error('No trace path on this row. Select a bundle or trace artifact.');await vscode.window.showTextDocument(await vscode.workspace.openTextDocument(vscode.Uri.file(resolve(dirname(row.file.fsPath),file))));});
 command('source',async row=>{const loc=object(object(row?.value).scala ?? object(row?.value).source ?? row?.value);if(typeof loc.file!=='string'||!Number.isInteger(loc.line)||Number(loc.line)<1)throw new Error('No recorded source location on this row.');await vscode.window.showTextDocument(await vscode.workspace.openTextDocument(vscode.Uri.file(resolve(dirname(row!.file.fsPath),loc.file))),{selection:new vscode.Range(Number(loc.line)-1,0,Number(loc.line)-1,0)});});
}};export default feature;
