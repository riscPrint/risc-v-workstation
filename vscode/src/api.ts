import * as vscode from 'vscode';

/**
 * What the extension gives each feature. A feature is one tool's part of the extension
 * (SpinalBlocks diagrams, and later waveforms, traces, simulation runs ...). See README.md.
 */
export interface FeatureContext {
  /** The feature's id, as in its feature.json. */
  readonly id: string;
  /** The extension's own context. Prefer the scoped members below where one exists. */
  readonly extension: vscode.ExtensionContext;
  /** Disposed when the extension deactivates. */
  readonly subscriptions: { dispose(): unknown }[];
  /** Workspace state, with keys private to this feature. */
  readonly workspaceState: vscode.Memento;
  /** Global state, with keys private to this feature. */
  readonly globalState: vscode.Memento;
  /** `dist/<id>/`: this feature's webview bundles and assets from its feature.json. */
  readonly dist: vscode.Uri;
  /** Shared output channel; lines are prefixed with the feature id. */
  readonly log: vscode.LogOutputChannel;
  /** True when running under the extension test runner. */
  readonly testMode: boolean;
}

export interface Feature<Api = unknown> {
  readonly id: string;
  /** Registers the feature's commands, editors and views. The returned value is exposed to other
   * features and tests as `exports.features[id]`. */
  activate(context: FeatureContext): Api | Promise<Api>;
}

/** The extension's exports. */
export interface WorkstationApi {
  readonly features: Readonly<Record<string, unknown>>;
}

/** A Memento whose keys are prefixed, so features cannot see or clear each other's state. */
export function scopedMemento(base: vscode.Memento, prefix: string): vscode.Memento {
  const p = `${prefix}:`;
  return {
    keys: () => base.keys().filter(k => k.startsWith(p)).map(k => k.slice(p.length)),
    get: <T>(key: string, fallback?: T) => base.get<T>(p + key, fallback as T),
    update: (key: string, value: unknown) => base.update(p + key, value),
  } as vscode.Memento;
}
