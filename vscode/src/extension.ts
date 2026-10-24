import * as vscode from 'vscode';
import { scopedMemento, type FeatureContext, type WorkstationApi } from './api';
import { features } from './features';

export async function activate(context: vscode.ExtensionContext): Promise<WorkstationApi> {
  const log = vscode.window.createOutputChannel('RISC-V Workstation', {log: true});
  context.subscriptions.push(log);
  const apis: Record<string, unknown> = {};
  // Features start independently: one failing feature must not take the others down.
  for (const feature of features) {
    const scoped: FeatureContext = {
      id: feature.id,
      extension: context,
      subscriptions: context.subscriptions,
      workspaceState: scopedMemento(context.workspaceState, feature.id),
      globalState: scopedMemento(context.globalState, feature.id),
      dist: vscode.Uri.joinPath(context.extensionUri, 'dist', feature.id),
      log: prefixed(log, feature.id),
      testMode: context.extensionMode === vscode.ExtensionMode.Test,
    };
    try {
      apis[feature.id] = await feature.activate(scoped);
    } catch (e) {
      log.error(`[${feature.id}] failed to start: ${e instanceof Error ? e.stack ?? e.message : String(e)}`);
      void vscode.window.showErrorMessage(`RISC-V Workstation: ${feature.id} failed to start. See the output channel.`);
    }
  }
  return {features: apis};
}

export function deactivate(): void {}

function prefixed(log: vscode.LogOutputChannel, id: string): vscode.LogOutputChannel {
  const tag = (message: string) => `[${id}] ${message}`;
  return {
    get name() { return log.name; },
    get logLevel() { return log.logLevel; },
    onDidChangeLogLevel: log.onDidChangeLogLevel,
    trace: (m, ...a) => log.trace(tag(m), ...a),
    debug: (m, ...a) => log.debug(tag(m), ...a),
    info: (m, ...a) => log.info(tag(m), ...a),
    warn: (m, ...a) => log.warn(tag(m), ...a),
    error: (m, ...a) => log.error(typeof m === 'string' ? tag(m) : m, ...a),
    append: value => log.append(value),
    appendLine: value => log.appendLine(tag(value)),
    replace: value => log.replace(value),
    clear: () => log.clear(),
    show: (preserveFocus?: boolean) => log.show(preserveFocus),
    hide: () => log.hide(),
    dispose: () => {}, // the shared channel belongs to the extension
  } as vscode.LogOutputChannel;
}
