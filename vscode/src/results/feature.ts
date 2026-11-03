import * as vscode from 'vscode';
import { execFile } from 'node:child_process';
import type { Feature, FeatureContext } from '../api';
import { children, headline, label, object, parseReport, queryArgs, sourceMatches, sourceTargets, type Kind, type Row } from './model';

/** Shared host for saved rvw results. Each tool owns its feature manifest and entry point. */
export function resultsFeature(id: Kind, title: string): Feature {
  return {id, activate(context: FeatureContext) {
    let report: unknown;
    let file: vscode.Uri | undefined;
    const changed = new vscode.EventEmitter<Row | undefined>();
    const provider: vscode.TreeDataProvider<Row> = {
      onDidChangeTreeData: changed.event,
      getChildren: row => row ? children(row.value) : report ? [
        {key: headline(id, object(report)), value: null, heading: true},
        {key: 'Saved producer data; input identity is not revalidated', value: null, heading: true},
        {key: 'Report', value: report},
      ] : [{key: 'Open an rvw JSON report to show results', value: null, heading: true}],
      getTreeItem: row => {
        const item = new vscode.TreeItem(row.heading ? row.key : label(row), children(row.value).length ? vscode.TreeItemCollapsibleState.Collapsed : vscode.TreeItemCollapsibleState.None);
        item.tooltip = row.heading ? row.key : JSON.stringify(row.value, null, 2);
        // No success icons: saved claims and incomplete evidence must never imply acceptance.
        if (/inconclusive|incomplete|unsupported|unknown|stale/i.test(item.label as string)) item.iconPath = new vscode.ThemeIcon('warning', new vscode.ThemeColor('editorWarning.foreground'));
        return item;
      },
    };
    const view = vscode.window.createTreeView(`${id}.results`, {treeDataProvider: provider});
    const guard = (fn: () => Promise<unknown>) => async () => { try { await fn(); } catch (e) { void vscode.window.showErrorMessage(`${title}: ${String(e)}`); } };
    const register = (name: string, fn: () => Promise<unknown>) => context.subscriptions.push(vscode.commands.registerCommand(`${id}.${name}`, guard(fn)));
    async function pick(label: string, extensions?: string[]): Promise<vscode.Uri | undefined> {
      return (await vscode.window.showOpenDialog({title: label, canSelectMany: false, filters: extensions ? {[label]: extensions} : undefined}))?.[0];
    }
    async function load(uri: vscode.Uri): Promise<void> {
      // Clear old evidence before a failed load, so an old verdict cannot look current.
      report = undefined; file = uri; view.message = uri.fsPath; changed.fire(undefined);
      report = parseReport(id, Buffer.from(await vscode.workspace.fs.readFile(uri)).toString('utf8'));
      changed.fire(undefined);
    }
    register('open', async () => { const uri = await pick('Open rvw result', ['json']); if (uri) await load(uri); });
    register('refresh', async () => { if (file) await load(file); });
    register('raw', async () => { if (file) await vscode.window.showTextDocument(file); });
    register('source', async () => {
      if (!vscode.workspace.isTrusted) throw new Error('Trust the workspace before running rvw.');
      const db = await pick('Select the captured design database'); if (!db) return;
      const signal = await vscode.window.showInputBox({title: 'Signal path in the selected database', prompt: 'Select the database for this run. Report-to-database identity is not verified.'});
      if (!signal) return;
      const executable = vscode.workspace.getConfiguration(id).get<string>('rvwExecutable', 'rvw');
      const output = await new Promise<string>((resolve, reject) => execFile(executable, queryArgs(db.fsPath, signal), {cwd: vscode.workspace.getWorkspaceFolder(db)?.uri.fsPath, timeout: 30000, maxBuffer: 8 * 1024 * 1024}, (error, stdout, stderr) => {
        if (error) reject(new Error(`${error.message}\n${stdout}\n${stderr}`)); else resolve(stdout);
      }));
      const result: unknown = JSON.parse(output);
      context.log.info(output);
      const targets = sourceTargets(result);
      if (!targets.length) throw new Error(`Source mapping is unresolved, pruned, stale or inconclusive. See RISC-V Workstation output. ${String(object(result).cause ?? '')}`);
      const choice = targets.length === 1 ? targets[0] : (await vscode.window.showQuickPick(targets.map(target => ({label: `${target.file}:${target.line}`, target}))))?.target;
      if (!choice) return;
      const uri = vscode.Uri.file(choice.file);
      if (!sourceMatches(choice, await vscode.workspace.fs.readFile(uri))) throw new Error('Source changed since the query capture. Mapping is inconclusive.');
      const document = await vscode.workspace.openTextDocument(uri);
      if (choice.line > document.lineCount) throw new Error('Source line is unresolved.');
      await vscode.window.showTextDocument(document, {selection: new vscode.Range(choice.line - 1, 0, choice.line - 1, 0)});
    });
    // Process tasks use argument arrays. Paths and criteria never become shell text.
    async function launch(executable: string, args: string[]): Promise<void> {
      if (!vscode.workspace.isTrusted) throw new Error('Trust the workspace before opening native tools.');
      const task = new vscode.Task({type: id}, vscode.TaskScope.Workspace, title, id, new vscode.ProcessExecution(executable, args));
      await vscode.tasks.executeTask(task);
    }
    register('wave', async () => {
      const wave = await pick('Open waveform in Surfer', ['vcd', 'fst', 'gz']);
      if (wave) await launch(vscode.workspace.getConfiguration(id).get('surferExecutable', 'surfer'), [wave.fsPath]);
    });
    register('trace', async () => {
      const pdg = await pick('Select SpinalTrace pdg.json', ['json']); if (!pdg) return;
      const wave = await pick('Select SpinalTrace waveform', ['vcd', 'fst']); if (!wave) return;
      const criterion = await vscode.window.showInputBox({title: 'SpinalTrace criterion', prompt: 'Use signal:PATH, statement:NAME or line:FILE:LINE. The tool uses the end of the waveform.'});
      if (criterion) await launch(vscode.workspace.getConfiguration(id).get('spinaltraceExecutable', 'spinaltrace'), ['-p', pdg.fsPath, '-v', wave.fsPath, '-s', criterion]);
    });
    context.subscriptions.push(changed, view);
    return {load};
  }};
}
