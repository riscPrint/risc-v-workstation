import * as vscode from 'vscode';
import { execFile } from 'node:child_process';
import { dirname, isAbsolute, join } from 'node:path';
import type { Feature, FeatureContext } from '../../../src/api';
import { headline, messageText, parseLint, waiver, ruleGroups, type LintDiagnostic, type LintSummary } from './model';

/** `rvw lint` findings in the Problems panel: run with a settings file, or open a saved
 * rvw.lint/1 report or SARIF log. Waived findings show as hints with their reason. */
const feature: Feature = {id: 'lint', activate(context: FeatureContext) {
  const collection = vscode.languages.createDiagnosticCollection('rvw-lint');
  const status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left);
  status.command = 'lint.open';
  context.subscriptions.push(collection, status);
  const config = () => vscode.workspace.getConfiguration('lint');
  let lastSettings: string | undefined;
  let lastConfig: string | undefined;
  type Group = {rule:string;findings:LintDiagnostic[]};
  type Entry = Group | LintDiagnostic;
  let groups:Group[]=[];
  let reportBase='';
  const changed=new vscode.EventEmitter<Entry|undefined>();
  context.subscriptions.push(changed,vscode.window.createTreeView('lint.rules',{treeDataProvider:{onDidChangeTreeData:changed.event,
    getChildren:(row?:Entry)=>row&&'findings' in row?row.findings:row?[]:groups,
    getTreeItem:(row:Entry)=>{const group='findings' in row;
      const item=new vscode.TreeItem(group?`${row.rule}: ${row.findings.length}`:messageText(row),group?1:0);
      if(!group){item.description=row.backend;item.contextValue='lint.finding';item.command={command:'lint.findingSource',title:'Open source',arguments:[row]};}return item;}}}));
  context.subscriptions.push(vscode.commands.registerCommand('lint.findingSource',async(d:LintDiagnostic)=>{
    try{if(!d.file)throw new Error('No source location for this finding.');
      await vscode.window.showTextDocument(await vscode.workspace.openTextDocument(vscode.Uri.file(isAbsolute(d.file)?d.file:join(reportBase,d.file))),{selection:new vscode.Range(Math.max(0,d.line-1),0,Math.max(0,d.line-1),0)});
    }catch(e){void vscode.window.showErrorMessage(`Lint: ${String(e)}`);}
  }));
  const source = new WeakMap<vscode.Diagnostic, LintDiagnostic>();

  const level: Record<LintDiagnostic['severity'], vscode.DiagnosticSeverity> = {
    error: vscode.DiagnosticSeverity.Error, warning: vscode.DiagnosticSeverity.Warning,
    info: vscode.DiagnosticSeverity.Information, hint: vscode.DiagnosticSeverity.Hint};

  function show(summary: LintSummary, base: string, fallback: vscode.Uri): void {
    collection.clear();
    groups=ruleGroups(summary);reportBase=base;changed.fire(undefined);
    lastConfig = summary.config;
    const byFile = new Map<string, vscode.Diagnostic[]>();
    for (const d of summary.diagnostics) {
      const file = d.file ? (isAbsolute(d.file) ? d.file : join(base, d.file)) : fallback.fsPath;
      const pos = new vscode.Position(Math.max(0, d.line - 1), Math.max(0, d.column - 1));
      const diag = new vscode.Diagnostic(new vscode.Range(pos, pos.translate(0, 200)), messageText(d), level[d.severity]);
      diag.code = d.rule;
      diag.source = `rvw lint${d.backend ? ` ${d.backend}` : ''}`;
      if (d.waived !== undefined) diag.tags = [vscode.DiagnosticTag.Unnecessary];
      source.set(diag, d);
      byFile.set(file, [...(byFile.get(file) ?? []), diag]);
    }
    for (const [file, list] of byFile) collection.set(vscode.Uri.file(file), list);
    status.text = `$(checklist) ${headline(summary)}`;
    status.show();
    context.log.info(headline(summary));
  }

  function rvw(argv: string[], cwd: string): Promise<string> {
    if (!vscode.workspace.isTrusted) throw new Error('Trust the workspace before running rvw.');
    const executable = config().get<string>('rvwExecutable', 'rvw');
    return new Promise((resolve, reject) => execFile(executable, argv, {cwd, timeout: config().get<number>('timeoutMs', 600000),
      maxBuffer: 64 * 1024 * 1024}, (error, stdout, stderr) => {
      context.log.info(`rvw ${argv.join(' ')}\n${stderr}`);
      // Findings exit 1 and inconclusive exits 3; both still print the JSON report.
      if (stdout.trim().startsWith('{')) resolve(stdout);
      else reject(new Error(error ? `${error.message}\n${stderr}` : 'rvw printed no JSON'));
    }));
  }

  const guard = (fn: () => Promise<unknown>) => async () => {
    try { await fn(); } catch (e) { void vscode.window.showErrorMessage(`Lint: ${String(e)}`); }
  };
  const register = (name: string, fn: () => Promise<unknown>) =>
    context.subscriptions.push(vscode.commands.registerCommand(`lint.${name}`, guard(fn)));

  async function run(settings?: string): Promise<void> {
    if (!settings) {
      const configured = config().get<string>('settings', '');
      const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
      settings = configured ? (isAbsolute(configured) || !root ? configured : join(root, configured))
        : (await vscode.window.showOpenDialog({title: 'Lint settings (rvw.lint-settings/1)', canSelectMany: false,
          filters: {JSON: ['json']}}))?.[0]?.fsPath;
    }
    if (!settings) return;
    lastSettings = settings;
    const text = await vscode.window.withProgress({location: vscode.ProgressLocation.Window, title: 'rvw lint'},
      () => rvw(['lint', '--settings', settings!, '--json'], dirname(settings!)));
    show(parseLint(text), dirname(settings), vscode.Uri.file(settings));
  }

  register('run', () => run());
  register('rerun', () => run(lastSettings));
  register('open', async () => {
    const file = (await vscode.window.showOpenDialog({title: 'rvw lint report or SARIF log', canSelectMany: false,
      filters: {'Lint results': ['json', 'sarif']}}))?.[0];
    if (!file) return;
    const text = new TextDecoder().decode(await vscode.workspace.fs.readFile(file));
    show(parseLint(text), dirname(file.fsPath), file);
  });
  register('clear', async () => { collection.clear(); groups=[];changed.fire(undefined);status.hide(); });
  context.subscriptions.push(vscode.commands.registerCommand('lint.copyWaiver', async (d: LintDiagnostic) => {
    try {
      await vscode.env.clipboard.writeText(JSON.stringify(waiver(d, lastConfig), null, 2));
      void vscode.window.showInformationMessage('Lint: waiver copied. Write its reason, then add it to the settings waivers.');
    } catch (e) { void vscode.window.showErrorMessage(`Lint: ${String(e)}`); }
  }));
  context.subscriptions.push(vscode.languages.registerCodeActionsProvider({scheme: 'file'}, {
    provideCodeActions: (_doc, _range, ctx) => ctx.diagnostics.flatMap(diag => {
      const d = source.get(diag);
      if (!d || !d.id || d.waived !== undefined || d.rule === 'lint.stale_waiver') return [];
      const action = new vscode.CodeAction(`Copy rvw lint waiver for ${d.rule}`, vscode.CodeActionKind.QuickFix);
      action.diagnostics = [diag];
      action.command = {command: 'lint.copyWaiver', title: 'Copy waiver', arguments: [d]};
      return [action];
    }),
  }, {providedCodeActionKinds: [vscode.CodeActionKind.QuickFix]}));
  return {parseLint};
}};
export default feature;
