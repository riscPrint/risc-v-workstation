import * as vscode from 'vscode';
import type {Feature} from '../../../src/api';
import {parse,render} from './model';
const feature:Feature={id:'arch',activate(context){for(const name of ['open','study'])context.subscriptions.push(vscode.commands.registerCommand(`arch.${name}`,async()=>{try{
 const uri=(await vscode.window.showOpenDialog({title:'Saved architecture, perf or csim JSON',canSelectMany:false,filters:{JSON:['json']}}))?.[0];if(!uri)return;
 const report=parse(Buffer.from(await vscode.workspace.fs.readFile(uri)).toString());
 const panel=vscode.window.createWebviewPanel('arch.report','Architecture report',vscode.ViewColumn.Active,{});panel.webview.html=render(report);
 }catch(e){void vscode.window.showErrorMessage(`Architecture: ${String(e)}`);}}));}};export default feature;
