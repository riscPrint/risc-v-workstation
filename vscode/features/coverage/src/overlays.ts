import * as vscode from 'vscode';
import {dirname,resolve} from 'node:path';
import type {FeatureContext} from '../../../src/api';
import {children,label,type Row} from '../../../src/results/model';
import {lines,holes,type Line} from './lines';
export function activateOverlays(context:FeatureContext){
 let marks:Line[]=[],base='',report:unknown;
 const changed=new vscode.EventEmitter<Row|undefined>();
 const decoration=vscode.window.createTextEditorDecorationType({gutterIconPath:vscode.Uri.joinPath(context.dist,'marker.svg'),gutterIconSize:'contain',overviewRulerColor:new vscode.ThemeColor('editorWarning.foreground')});
 function update(){for(const editor of vscode.window.visibleTextEditors)editor.setDecorations(decoration,marks.filter(m=>resolve(base,m.file)===editor.document.uri.fsPath&&m.line<=editor.document.lineCount).map(m=>({range:new vscode.Range(m.line-1,0,m.line-1,0),hoverMessage:`Saved coverage: ${m.hit}/${m.total} instrumented points hit (${m.types.join(', ')}). Source identity is not checked.`})));}
 context.subscriptions.push(changed,decoration,vscode.window.onDidChangeVisibleTextEditors(update),vscode.window.createTreeView('coverage.holes',{treeDataProvider:{onDidChangeTreeData:changed.event,getChildren:(row?:Row)=>row?children(row.value):report?children(report):[{key:'Open functional coverage or plan status JSON',value:null}],getTreeItem:(row:Row)=>new vscode.TreeItem(label(row),children(row.value).length?1:0)}}));
 for(const name of ['decorate','holes','plan','clearLines'])context.subscriptions.push(vscode.commands.registerCommand(`coverage.${name}`,async()=>{try{
 if(name==='clearLines'){marks=[];update();return;}
 const file=(await vscode.window.showOpenDialog({title:name==='plan'?'Saved rvw plan status --json':'Saved coverage JSON',canSelectMany:false,filters:{JSON:['json']}}))?.[0];if(!file)return;
 if(name==='decorate'){marks=[];update();}else{report=undefined;changed.fire(undefined);}
 const value=JSON.parse(Buffer.from(await vscode.workspace.fs.readFile(file)).toString());
 if(name==='decorate'){marks=lines(value);base=dirname(file.fsPath);update();if(!marks.length)void vscode.window.showInformationMessage('No mapped Scala coverage lines in this file.');}else{report=holes(value);changed.fire(undefined);}
 }catch(e){void vscode.window.showErrorMessage(`Coverage: ${String(e)}`);}}));
}
