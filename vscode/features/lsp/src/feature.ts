import * as vscode from 'vscode';
import { LanguageClient, TransportKind } from 'vscode-languageclient/node';
import type { Feature, FeatureContext } from '../../../src/api';

const feature: Feature = { id: 'lsp', activate(context: FeatureContext) {
  let client: LanguageClient | undefined;
  context.subscriptions.push(vscode.commands.registerCommand('lsp.start', async () => {
    if (!vscode.workspace.isTrusted) throw new Error('Trust the workspace before starting rvw lsp.');
    if (client) await client.stop();
    const cfg = vscode.workspace.getConfiguration('lsp');
    const db = cfg.get<string>('database', '');
    const args = ['lsp'];
    if (db) args.push('--db', db);
    const lint = cfg.get<string>('lintSettings', '');
    if (lint) args.push('--lint-settings', lint);
    const cwd = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    client = new LanguageClient('rvw-design', 'RVW Design Database', {
      command: cfg.get<string>('executable', 'rvw'), args,
      transport: TransportKind.stdio, options: {cwd},
    }, { documentSelector: [{scheme: 'file', language: 'scala'}, {scheme: 'file', language: 'verilog'},
      {scheme: 'file', language: 'systemverilog'}, {scheme: 'file', language: 'vhdl'}] });
    await client.start();
    context.log.info('Started rvw lsp. Rebuild the database after source changes.');
  }));
  context.subscriptions.push({dispose() { if (client) void client.stop(); }});
}};
export default feature;
