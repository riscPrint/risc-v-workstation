import * as vscode from 'vscode';
import type {Feature} from '../../../src/api';
import {object} from '../../../src/results/model';
import {parse,render,instructionLine} from './model';
const feature:Feature={id:'cosim',activate(context){
 let report:Record<string,unknown>|undefined;
 const command=(name:string,fn:()=>Promise<unknown>)=>context.subscriptions.push(vscode.commands.registerCommand(`cosim.${name}`,async()=>{try{await fn();}catch(e){void vscode.window.showErrorMessage(`Cosim: ${String(e)}`);}}));
 command('open',async()=>{report=undefined;const file=(await vscode.window.showOpenDialog({canSelectMany:false,filters:{JSON:['json']}}))?.[0];if(!file)return;
 report=parse(Buffer.from(await vscode.workspace.fs.readFile(file)).toString());
 const panel=vscode.window.createWebviewPanel('cosim.mismatch','Cosim first divergence',vscode.ViewColumn.Active,{});panel.webview.html=render(report);});
 command('disassembly',async()=>{if(!report)throw new Error('Open a saved cosim result first.');
 const file=(await vscode.window.showOpenDialog({title:'Saved objdump -d output for the run ELF',canSelectMany:false}))?.[0];if(!file)return;
 const doc=await vscode.workspace.openTextDocument(file),line=instructionLine(doc.getText(),object(report.mismatch).pc);
 await vscode.window.showTextDocument(doc,{selection:new vscode.Range(line,0,line,0)});});
}};export default feature;
