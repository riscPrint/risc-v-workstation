import { test } from 'node:test';
import assert from 'node:assert/strict';
import Module from 'node:module';
import { createHash } from 'node:crypto';
import suite from './fixtures/suite.json';
import verdict from './fixtures/verdict.json';

test('result host loads fixtures, clears failed loads and launches native tools', async () => {
  const commands = new Map<string, (row?: any) => Promise<void>>();
  const dialogs: string[] = [];
  const errors: string[] = [];
  const tasks: any[] = [];
  const opened: any[] = [];
  const queries: any[] = [];
  let queryResult: any;
  let provider: any;
  let content = JSON.stringify(verdict);
  const uri = (fsPath: string) => ({fsPath});
  const vscode = {
    EventEmitter: class { event = () => {}; fire() {} dispose() {} },
    TreeItem: class { constructor(public label: string, public collapsibleState: number) {} },
    ThemeIcon: class { constructor(public id: string, public color: any) {} },
    ThemeColor: class { constructor(public id: string) {} },
    Uri: {file:uri},
    Range: class { constructor(public startLine:number, public startColumn:number, public endLine:number, public endColumn:number) {} },
    TreeItemCollapsibleState: {None:0, Collapsed:1},
    TaskScope: {Workspace:1},
    Task: class { constructor(public definition:any, public scope:any, public name:any, public source:any, public execution:any) {} },
    ProcessExecution: class { constructor(public executable:string, public args:string[]) {} },
    workspace: {isTrusted:true, getWorkspaceFolder:()=>undefined, openTextDocument:async(u:any)=>({uri:u,lineCount:20}), fs:{readFile:async()=>Buffer.from(content)}, getConfiguration:()=>({get:(_:string,fallback:string)=>fallback})},
    window: {
      showTextDocument:async(document:any,options:any)=>opened.push({document,options}),
      createTreeView: (_:string, options:any) => { provider=options.treeDataProvider; return {dispose(){}}; },
      showOpenDialog:async()=>[uri(dialogs.shift()!)],
      showInputBox:async()=> 'signal:io.result',
      showErrorMessage:(message:string)=>errors.push(message),
    },
    tasks: {executeTask:async(task:any)=>tasks.push(task)},
    commands:{registerCommand:(id:string,fn:()=>Promise<void>)=>{commands.set(id,fn);return {dispose(){}};}},
  };
  const loader = Module as unknown as {_load:(...args:any[])=>unknown};
  const original = loader._load;
  loader._load = function(name,...args) { return name==='vscode' ? vscode : name==='node:child_process' ? {execFile:(executable:any,args:any,options:any,callback:any)=>{queries.push({executable,args,options});callback(null,JSON.stringify(queryResult),'');}} : original.call(this,name,...args); };
  try {
    // esbuild keeps the host initialization lazy until the mock is installed.
    const {resultsFeature} = require('../../../src/results/feature');
    const api=resultsFeature('regress','Regression').activate({subscriptions:[],log:{info(){}}});
    assert.equal(commands.size,8);
    await api.load(uri('/tmp/verdict.json'));
    let rows=provider.getChildren();
    assert.match(rows[0].key,/inconclusive; tests: pass/);
    const item=provider.getTreeItem(rows[0]);
    assert.equal(item.iconPath.id,'warning');
    assert.equal(item.iconPath.color.id,'editorWarning.foreground');
    content=JSON.stringify(suite); await commands.get('regress.refresh')!();
    assert.match(provider.getChildren()[0].key,/1 inconclusive/);
    content='{'; await commands.get('regress.refresh')!();
    assert.match(provider.getChildren()[0].key,/Open an rvw JSON report/);
    assert.equal(errors.length,1);
    dialogs.push('/tmp/wave with spaces.vcd'); await commands.get('regress.wave')!();
    assert.equal(tasks[0].execution.executable,'surfer');
    assert.deepEqual(tasks[0].execution.args,['/tmp/wave with spaces.vcd']);
    dialogs.push('/tmp/pdg.json','/tmp/wave.vcd'); await commands.get('regress.trace')!();
    assert.equal(tasks[1].execution.executable,'spinaltrace');
    assert.deepEqual(tasks[1].execution.args,['-p','/tmp/pdg.json','-v','/tmp/wave.vcd','-s','signal:io.result']);
    content='// captured source';
    queryResult={signal:{loc:'/tmp/Unit.scala:9',source:{source:'/tmp/Unit.scala',sha256:createHash('sha256').update(content).digest('hex')}}};
    dialogs.push('/tmp/design.db'); await commands.get('regress.source')!();
    assert.equal(opened.length,1);
    assert.equal(opened[0].options.selection.startLine,8);
    assert.deepEqual(queries[0].args,['query','where','--db','/tmp/design.db','--json','--','signal:io.result']);
    queryResult.status='inconclusive'; queryResult.cause='changed RTL';
    dialogs.push('/tmp/design.db'); await commands.get('regress.source')!();
    assert.equal(opened.length,1);
    assert.match(errors.at(-1)!,/inconclusive/);
    delete queryResult.status; content='// changed source';
    dialogs.push('/tmp/design.db'); await commands.get('regress.source')!();
    assert.equal(opened.length,1);
    assert.match(errors.at(-1)!,/Source changed/);
    vscode.workspace.isTrusted=false;
    dialogs.push('/tmp/wave.vcd'); await commands.get('regress.wave')!();
    assert.equal(tasks.length,2);
    assert.match(errors.at(-1)!,/Trust the workspace/);
    vscode.workspace.isTrusted=true;
    const row={key:'job',value:{run:'jobs/one/result.json',status:'error',inconclusive:'missing evidence'}};
    assert.equal(provider.getTreeItem(row).contextValue,'rvw.run');
    await commands.get('regress.runResult')!(row);
    assert.equal(opened.at(-1).document.fsPath,'/tmp/jobs/one/result.json');
    await commands.get('regress.evidence')!(row);
    assert.equal(JSON.parse(opened.at(-1).document.uri.content).inconclusive,'missing evidence');
    const count=opened.length;
    await commands.get('regress.runResult')!({key:'missing',value:{}});
    assert.equal(opened.length,count);
    assert.match(errors.at(-1)!,/No declared C1 run path/);
    content='// captured source';
    queryResult={signal:{loc:'/tmp/Unit.scala:9',source:{source:'/tmp/Unit.scala',sha256:createHash('sha256').update(content).digest('hex')}}};
    const signalRow={key:'point',value:{signal:'top.io.result'}};
    assert.equal(provider.getTreeItem(signalRow).contextValue,'rvw.signal');
    dialogs.push('/tmp/design.db'); await commands.get('regress.source')!(signalRow);
    assert.equal(queries.at(-1).args.at(-1),'top.io.result');

  } finally { loader._load=original; }
});
