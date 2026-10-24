import * as vscode from 'vscode';
import * as path from 'node:path';
import { loadDesign, locate, modulesDefinedIn, instancePaths, type Design } from '../../../../SpinalBlocks/engine/src/core.ts';

export const defaultDesignFiles = ['**/blocks/*.json.gz', '**/*.spinalblocks.json'];
export type DiagramKind = 'block' | 'fsm';
export const designUri = (value: string): vscode.Uri => (path.isAbsolute(value) || path.win32.isAbsolute(value)) ? vscode.Uri.file(value) : vscode.Uri.parse(value);
export interface SourceRequest { file: string; line: number; design?: string; module?: string; fsm?: string }
export type OpenRequest = Partial<SourceRequest>;
export function moduleAt(design: Design, names: string[]): string | undefined {
  let module = design.top;
  for (const name of names) {
    const next = design.modules[module]?.instances.find(i => i.name === name)?.module;
    if (!next) return;
    module = next;
  }
  return module;
}
export interface Choice { uri: vscode.Uri; design: Design; module: string; path: string[]; fsm?: string; line: number }

export class Designs implements vscode.Disposable {
  private cache = new Map<string, Promise<Design | undefined>>();
  private watchers: vscode.Disposable[] = [];
  private changed = new vscode.EventEmitter<void>();
  readonly onDidChange = this.changed.event;
  private files: Promise<vscode.Uri[]> | undefined;
  constructor() { this.watch(); }
  watch(): void {
    this.watchers.forEach(w => w.dispose());
    this.watchers = [];
    for (const glob of vscode.workspace.getConfiguration('spinalblocks').get<string[]>('designFiles', defaultDesignFiles)) {
      const watcher = vscode.workspace.createFileSystemWatcher(glob);
      const invalidate = (uri: vscode.Uri) => this.invalidate(uri);
      this.watchers.push(watcher, watcher.onDidChange(invalidate), watcher.onDidCreate(invalidate), watcher.onDidDelete(invalidate));
    }
    this.cache.clear(); this.files = undefined; this.changed.fire();
  }
  invalidate(uri: vscode.Uri): void { this.cache.delete(uri.toString()); this.files = undefined; this.changed.fire(); }
  async read(uri: vscode.Uri): Promise<Design | undefined> {
    const key = uri.toString();
    let value = this.cache.get(key);
    if (!value) {
      value = Promise.resolve(vscode.workspace.fs.readFile(uri)).then(bytes => loadDesign(bytes)).then(d => d, () => undefined);
      this.cache.set(key, value);
    }
    return value;
  }
  async all(): Promise<{uri: vscode.Uri; design: Design}[]> {
    this.files ??= Promise.all(vscode.workspace.getConfiguration('spinalblocks').get<string[]>('designFiles', defaultDesignFiles)
      .map(glob => vscode.workspace.findFiles(glob, '**/{node_modules,.git,.vscode-test}/**'))).then(groups => [...new Map(groups.flat().map(uri => [uri.toString(), uri])).values()].sort((a,b) => a.toString().localeCompare(b.toString())));
    const files = await this.files;
    const designs = await Promise.all(files.map(async uri => ({uri, design:await this.read(uri)})));
    return designs.filter((entry): entry is {uri:vscode.Uri; design:Design} => !!entry.design);
  }
  async choices(source: SourceRequest, kind: DiagramKind, atLine: boolean): Promise<Choice[]> {
    const entries = source.design ? [{uri:designUri(source.design), design:await this.read(designUri(source.design))}] : await this.all();
    return entries.flatMap(({uri, design}) => {
      if (!design) return [];
      const hits = atLine ? locate(design, source.file, source.line) : [];
      const defined = modulesDefinedIn(design, source.file);
      // Older exports sometimes point module locations at a shared base class.
      const inCursor = !atLine && kind === 'block' && !defined.length ? locate(design, source.file, source.line).filter(h => !['fsm','state','transition'].includes(h.kind)).map(h => h.module) : [];
      const inFile = !atLine && kind === 'block' && !defined.length && !inCursor.length ? Object.values(design.modules).filter(m => [...m.ports, ...m.instances, ...m.nodes].some(x => x.loc?.file === source.file)).map(m => m.name) : [];
      const modules = atLine ? [...new Set(hits.filter(h => kind === 'fsm' ? ['fsm','state','transition'].includes(h.kind) : !['fsm','state','transition'].includes(h.kind)).map(h => h.module))]
        : kind === 'block' ? [...new Set([...defined, ...inCursor, ...inFile])] : Object.keys(design.modules);
      return modules.flatMap(module => {
        if (source.module && source.module !== module) return [];
        const p = instancePaths(design, module, 1)[0];
        if (!p) return [];
        if (kind === 'block') return [{uri, design, module, path:p, line:hits.find(h => h.module === module)?.loc.line ?? source.line}];
        return (design.modules[module].fsms ?? []).filter(f => (!source.fsm || source.fsm === f.id) && (atLine
          ? hits.some(h => h.module === module && h.id === f.id && ['fsm','state','transition'].includes(h.kind))
          : f.loc?.file === source.file)).map(f => ({uri, design, module, path:p, fsm:f.id, line:hits.find(h => h.module === module && h.id === f.id)?.loc.line ?? source.line}));
      });
    });
  }
  dispose(): void { this.watchers.forEach(w => w.dispose()); this.changed.dispose(); }
}
