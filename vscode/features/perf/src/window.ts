import * as vscode from 'vscode';
import type {FeatureContext} from '../../../src/api';
import {pipeline,renderPipeline} from './pipeline';
export function activateWindow(context:FeatureContext){context.subscriptions.push(vscode.commands.registerCommand('perf.pipeline',async()=>{try{
 const uri=(await vscode.window.showOpenDialog({title:'Saved uncompressed Kanata 0004 log',canSelectMany:false}))?.[0];if(!uri)return;
 if((await vscode.workspace.fs.stat(uri)).size>32*1024*1024)throw new Error('Select a log smaller than 32 MiB. Use rvw perf for large logs.');
 const input=await vscode.window.showInputBox({title:'Cycle window: from,to (up to 80 cycles)',value:'0,39'});if(input===undefined)return;
 const parts=input.split(',');if(parts.length!==2||parts.some(p=>!/^\d+$/.test(p.trim())))throw new Error('Enter two nonnegative integer cycles.');
 const result=pipeline(Buffer.from(await vscode.workspace.fs.readFile(uri)).toString(),Number(parts[0]),Number(parts[1]));
 const panel=vscode.window.createWebviewPanel('perf.pipeline','Pipeline window',vscode.ViewColumn.Active,{});panel.webview.html=renderPipeline(result);
 }catch(e){void vscode.window.showErrorMessage(`Performance: ${String(e)}`);}}));}
