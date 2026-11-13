import * as vscode from 'vscode';
import { execFile } from 'node:child_process';
import { dirname, join } from 'node:path';
import { tmpdir } from 'node:os';
import type { Feature, FeatureContext } from '../../../src/api';
import { queryArgs, sourceMatches, sourceTargets } from '../../../src/results/model';
import { children, cutArgv, headline, KINDS, label, object, parseQuery, queryArgv, rowLocation, rowSignal, rowTime,
  type QueryKind, type Row, type WaveQuery } from './model';

/** Saved `rvw wave` queries (find, why, seq, txn, diff ...) and their results, with jumps to
 * the source line, the driver's database location and a wave window in Surfer. */
const feature: Feature = {id: 'wave', activate(context: FeatureContext) {
  let query: WaveQuery | undefined;
  let queryFile: vscode.Uri | undefined;
  let result: unknown;
  const changed = new vscode.EventEmitter<Row | undefined>();
  const config = () => vscode.workspace.getConfiguration('wave');
  const base = () => queryFile ? dirname(queryFile.fsPath) : vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  const provider: vscode.TreeDataProvider<Row> = {
    onDidChangeTreeData: changed.event,
    getChildren: row => row ? children(row.value) : result && query ? [
      {key: headline(query.kind, object(result)), value: null, heading: true},
      {key: `rvw ${queryArgv(query).join(' ')}`, value: null, heading: true},
      {key: 'Result', value: result},
    ] : [{key: 'Run or open a saved wave query to show results', value: null, heading: true}],
    getTreeItem: row => {
      const text = label(row);
      const item = new vscode.TreeItem(text, children(row.value).length ? vscode.TreeItemCollapsibleState.Collapsed : vscode.TreeItemCollapsibleState.None);
      const ctx = [rowSignal(row) && 'signal', rowTime(row) !== undefined && 'time', rowLocation(row) && 'loc'].filter(Boolean);
      item.contextValue = ctx.length ? `rvw.wave.${ctx.join('.')}` : undefined;
      item.tooltip = row.heading ? row.key : JSON.stringify(row.value, null, 2);
      if (/ambiguous|unknown|unresolved|error|inconclusive|diverged|issue|fail/i.test(text)) {
        item.iconPath = new vscode.ThemeIcon('warning', new vscode.ThemeColor('editorWarning.foreground'));
      }
      return item;
    },
  };
  const view = vscode.window.createTreeView('wave.results', {treeDataProvider: provider});
  const guard = (fn: (row?: Row) => Promise<unknown>) => async (row?: Row) => {
    try { await fn(row); } catch (e) { void vscode.window.showErrorMessage(`Wave: ${String(e)}`); }
  };
  const register = (name: string, fn: (row?: Row) => Promise<unknown>) =>
    context.subscriptions.push(vscode.commands.registerCommand(`wave.${name}`, guard(fn)));

  function rvw(argv: string[], cwd?: string): Promise<unknown> {
    if (!vscode.workspace.isTrusted) throw new Error('Trust the workspace before running rvw.');
    const executable = config().get<string>('rvwExecutable', 'rvw');
    return new Promise((resolve, reject) => execFile(executable, argv, {cwd, timeout: config().get<number>('timeoutMs', 600000),
      maxBuffer: 64 * 1024 * 1024}, (error, stdout, stderr) => {
      context.log.info(`rvw ${argv.join(' ')}\n${stderr}`);
      // diff exits 1 on a divergence and still prints its JSON result.
      try { if (stdout.trim()) { resolve(JSON.parse(stdout)); return; } } catch { /* fall through */ }
      reject(new Error(error ? `${error.message}\n${stderr}` : 'rvw printed no JSON'));
    }));
  }
  async function run(q: WaveQuery): Promise<void> {
    query = q; result = undefined; view.message = q.title ?? q.kind; changed.fire(undefined);
    result = await vscode.window.withProgress({location: {viewId: 'wave.results'}, title: `rvw wave ${q.kind}`},
      () => rvw(queryArgv(q, base()), base()));
    changed.fire(undefined);
  }
  async function ask(title: string, prompt?: string, value?: string): Promise<string> {
    const v = await vscode.window.showInputBox({title, prompt, value, ignoreFocusOut: true});
    if (v === undefined) throw new Error('cancelled');
    return v;
  }
  register('new', async () => {
    const kind = (await vscode.window.showQuickPick([...KINDS], {title: 'Wave query kind'})) as QueryKind | undefined;
    if (!kind) return;
    const wave = (await vscode.window.showOpenDialog({title: 'Wave (.vcd, .fst, .rvwi)', canSelectMany: false}))?.[0];
    if (!wave) return;
    const options: WaveQuery['options'] = {};
    let args: string[] = [];
    const prompts: Record<QueryKind, string> = {
      find: 'Expression, e.g. valid && ready && data[7:0] == 0x2a', edges: 'Signal regex', changes: 'Signal regex',
      sample: 'Signal regex', why: 'Signal path', seq: "Sequence, e.g. req ##[1:4] gnt", txn: 'valid signal',
      diff: 'Second wave path'};
    args = [await ask(`rvw wave ${kind}`, prompts[kind])];
    if (kind === 'txn') { options.valid = args[0]; args = []; const r = await ask('ready signal (empty for a Flow)'); if (r) options.ready = r;
      const p = await ask('payload regex (optional)'); if (p) options.payload = p; }
    if (kind === 'why') { options.at = await ask('Time (or Nc for cycle N)');
      options.db = (await vscode.window.showOpenDialog({title: 'SpinalDB design database', canSelectMany: false}))?.[0]?.fsPath ?? ''; }
    if (kind === 'sample') options.at = await ask('Time, Nc or end', undefined, 'end');
    if (['find', 'edges', 'seq', 'txn', 'diff', 'changes'].includes(kind)) {
      const from = await ask('From time (optional)'); if (from) options.from = from;
      const to = await ask('To time (optional)'); if (to) options.to = to;
    }
    if (kind !== 'why') options.indexed = true;
    queryFile = undefined;
    await run({schema: 'rvw.wave-query/1', kind, wave: wave.fsPath, args, options});
  });
  register('open', async () => {
    const uri = (await vscode.window.showOpenDialog({title: 'Saved wave query', canSelectMany: false, filters: {'Wave query': ['json']}}))?.[0];
    if (!uri) return;
    queryFile = uri;
    await run(parseQuery(Buffer.from(await vscode.workspace.fs.readFile(uri)).toString('utf8')));
  });
  register('rerun', async () => { if (query) await run(query); });
  register('save', async () => {
    if (!query) throw new Error('Run a query first.');
    const uri = await vscode.window.showSaveDialog({title: 'Save wave query', filters: {'Wave query': ['rvwq.json']}});
    if (!uri) return;
    await vscode.workspace.fs.writeFile(uri, Buffer.from(JSON.stringify(query, null, 2) + '\n'));
    queryFile = uri;
  });
  register('raw', async row => {
    const document = await vscode.workspace.openTextDocument({language: 'json', content: JSON.stringify(row ? row.value : result, null, 2)});
    await vscode.window.showTextDocument(document);
  });
  register('driverSource', async row => {
    const loc = rowLocation(row);
    if (!loc) throw new Error('This row has no database location.');
    const document = await vscode.workspace.openTextDocument(vscode.Uri.file(loc.file));
    if (loc.line > document.lineCount) throw new Error('Source line is unresolved; the file changed since the database was built.');
    await vscode.window.showTextDocument(document, {selection: new vscode.Range(loc.line - 1, 0, loc.line - 1, 0)});
    void vscode.window.setStatusBarMessage('Database location; source identity not checked. Use "Jump to Signal Source" for a checked jump.', 6000);
  });
  register('signalSource', async row => {
    const signal = rowSignal(row);
    const db = typeof query?.options.db === 'string' && query.options.db ? query.options.db
      : (await vscode.window.showOpenDialog({title: 'Design database for this wave', canSelectMany: false}))?.[0]?.fsPath;
    if (!signal || !db) return;
    const r = await rvw(queryArgs(db, signal), base());
    const targets = sourceTargets(r);
    if (!targets.length) throw new Error(`Source mapping is unresolved, pruned, stale or inconclusive. ${String(object(r).cause ?? '')}`);
    const t = targets[0];
    const uri = vscode.Uri.file(t.file);
    if (!sourceMatches(t, await vscode.workspace.fs.readFile(uri))) throw new Error('Source changed since the database capture.');
    await vscode.window.showTextDocument(await vscode.workspace.openTextDocument(uri), {selection: new vscode.Range(t.line - 1, 0, t.line - 1, 0)});
  });
  register('openWindow', async row => {
    const time = rowTime(row);
    if (time === undefined || !query) throw new Error('This row has no time.');
    const span = config().get<number>('windowSpan', 1000);
    const out = join(tmpdir(), `rvw-wave-${process.pid}-${Date.now()}.vcd`);
    await rvw(cutArgv(query.wave, time, span, out), base());
    const task = new vscode.Task({type: 'wave'}, vscode.TaskScope.Workspace, 'Surfer', 'wave',
      new vscode.ProcessExecution(config().get('surferExecutable', 'surfer'), [out]));
    await vscode.tasks.executeTask(task);
  });
  context.subscriptions.push(changed, view);
  return {run};
}};
export default feature;
