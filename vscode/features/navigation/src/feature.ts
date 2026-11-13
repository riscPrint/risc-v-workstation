import * as vscode from 'vscode';
import {execFile} from 'node:child_process';
import type {Feature} from '../../../src/api';
import {candidates, dependencyArgs} from './model';
const feature: Feature = {id:'navigation', activate(context) {
  const register = (name:string, fn:(loc?:{file:string;line:number})=>Promise<unknown>) => context.subscriptions.push(
    vscode.commands.registerCommand(`navigation.${name}`, async loc => {try {await fn(loc);} catch(e) {void vscode.window.showErrorMessage(`Navigation: ${String(e)}`);}}));
  async function select(loc?:{file:string;line:number}):Promise<string|undefined> {
    const editor = vscode.window.activeTextEditor;
    loc ??= editor ? {file:editor.document.uri.fsPath,line:editor.selection.active.line+1} : undefined;
    if (!loc) throw new Error('Open a Scala source file first.');
    const found = candidates(await vscode.commands.executeCommand('lsp.sourceSignals', loc.file, loc.line));
    if (!found.length) throw new Error('No generated signals at this line in the captured database. Rebuild the database after source changes.');
    return found.length === 1 ? found[0] : vscode.window.showQuickPick(found, {title:'Choose a generated signal'});
  }
  register('signals', async loc => {const signal=await select(loc); if(signal) await vscode.window.showInformationMessage(signal);});
  register('blocks', async loc => vscode.commands.executeCommand('spinalblocks.showLocation', loc));
  register('wave', async loc => {const signal=await select(loc); if(signal) await vscode.commands.executeCommand('wave.signalQuery', signal);});
  for (const kind of ['drivers','loads'] as const) register(kind, async loc => {
    const signal=await select(loc); if(!signal) return;
    if(!vscode.workspace.isTrusted) throw new Error('Trust the workspace before running rvw.');
    const cfg=vscode.workspace.getConfiguration('lsp');
    const args=dependencyArgs(kind,cfg.get<string>('database',''),signal);
    const text=await new Promise<string>((resolve,reject)=>execFile(cfg.get('executable','rvw'),args,
      {cwd:vscode.workspace.workspaceFolders?.[0]?.uri.fsPath,timeout:30000,maxBuffer:8*1024*1024},(error,out,err)=>out.trim()?resolve(out):reject(new Error(err || String(error)))));
    const doc=await vscode.workspace.openTextDocument({language:'json',content:JSON.stringify(JSON.parse(text),null,2)});
    await vscode.window.showTextDocument(doc);
  });
}};
export default feature;
