import * as vscode from 'vscode';
import type { Feature, FeatureContext } from '../../../src/api';
import * as path from 'node:path';
import { locate, instancePaths } from '../../../../SpinalBlocks/engine/src/core.ts';
import type { HierarchyNode } from '../../../../SpinalBlocks/engine/src/engine.ts';
import { html } from './html';
import { Designs, designUri, moduleAt, type OpenRequest, type Choice, type DiagramKind, type SourceRequest } from './designs';
import { isFromWebview, type FromWebview, type ToWebview, type SavedView } from './protocol';

const viewType = 'spinalblocks.diagram';
interface Session { uri: vscode.Uri; kind: DiagramKind; panel: vscode.WebviewPanel; root: HierarchyNode | null; path: string[]; ready: boolean; initialized: boolean; revision: number; busy?: () => void }
interface TestEvent { uri: string; kind: DiagramKind; message: FromWebview }
export interface TestApi {
  events: vscode.Event<TestEvent>;
  send(uri: vscode.Uri, message: ToWebview, kind?: DiagramKind): Thenable<boolean>;
  snapshot(uri: vscode.Uri, kind?: DiagramKind): { root: HierarchyNode | null; path: string[] } | undefined;
}

const feature: Feature<TestApi | undefined> = {id: 'spinalblocks', activate};
export default feature;

function activate(context: FeatureContext): TestApi | undefined {
  const sessions = new Set<Session>();
  const designs = new Designs();
  let active: Session | undefined;
  let last: Session | undefined;
  const changes = new vscode.EventEmitter<HierarchyNode | undefined>();
  const lenses = new vscode.EventEmitter<void>();
  const events = new vscode.EventEmitter<TestEvent>();
  const current = () => active ?? last;
  const blockSession = () => current()?.kind === 'block' ? current() : [...sessions].find(s => s.kind === 'block');
  const updateTree = () => { changes.fire(undefined); void vscode.commands.executeCommand('setContext', 'spinalblocks.hasDiagram', [...sessions].some(s => s.kind === 'block')); };
  const tree: vscode.TreeDataProvider<HierarchyNode> = {
    onDidChangeTreeData: changes.event,
    getChildren: node => node?.children ?? (blockSession()?.root ? [blockSession()!.root!] : []),
    getParent(node) {
      const visit = (parent: HierarchyNode): HierarchyNode | undefined => parent.children.includes(node) ? parent : parent.children.map(visit).find(Boolean);
      const root = blockSession()?.root; return root && visit(root);
    },
    getTreeItem(node) {
      const item = new vscode.TreeItem(node.name, node.children.length ? (node.path.length ? vscode.TreeItemCollapsibleState.Collapsed : vscode.TreeItemCollapsibleState.Expanded) : vscode.TreeItemCollapsibleState.None);
      item.id = JSON.stringify(node.path); item.description = node.module;
      item.tooltip = `${node.path.join('/') || node.name}: ${node.module}`;
      item.command = {command:'spinalblocks.navigate', title:'Open Module', arguments:[node.path]};
      return item;
    },
  };
  const treeView = vscode.window.createTreeView('spinalblocks.hierarchy', {treeDataProvider:tree});
  context.subscriptions.push(designs, changes, lenses, events, treeView, designs.onDidChange(() => lenses.fire()));
  const fail = (e: unknown) => { void vscode.window.showErrorMessage(`SpinalBlocks: ${String(e)}`); };
  const savedKey = (s: Session) => `view:${s.uri.toString()}`;
  async function load(session: Session): Promise<void> {
    const revision = ++session.revision;
    try {
      const bytes = await vscode.workspace.fs.readFile(session.uri);
      if (revision === session.revision && sessions.has(session)) await session.panel.webview.postMessage({type:'load', bytes:Uint8Array.from(bytes).buffer, saved:session.kind === 'block' ? context.workspaceState.get<SavedView>(savedKey(session)) : undefined} satisfies ToWebview);
    } catch (e) { fail(e); }
  }
  async function find(session = blockSession()): Promise<void> {
    if (!session) { void vscode.window.showInformationMessage('Open a SpinalBlocks diagram first.'); return; }
    session.panel.reveal(undefined, true);
    const pick = vscode.window.createQuickPick<vscode.QuickPickItem & {target: Extract<ToWebview, {type:'pick'}>['target']}>();
    pick.placeholder = 'Search blocks, ports, signals and nets in this module'; pick.matchOnDescription = true;
    let request = 0;
    const listener = events.event(event => {
      if (event.uri !== session.uri.toString() || event.kind !== session.kind || event.message.type !== 'searchResults' || event.message.request !== request) return;
      pick.busy = false; pick.items = event.message.hits.map(hit => ({label:hit.text, description:`${hit.kind} · ${hit.context}`, target:hit.target}));
    });
    const input = pick.onDidChangeValue(query => { pick.busy = true; void session.panel.webview.postMessage({type:'search', query, request:++request} satisfies ToWebview); });
    const accept = pick.onDidAccept(() => { const hit = pick.selectedItems[0]; if (hit) void session.panel.webview.postMessage({type:'pick', target:hit.target} satisfies ToWebview); pick.hide(); });
    const closed = session.panel.onDidDispose(() => pick.hide());
    pick.onDidHide(() => { closed.dispose(); listener.dispose(); input.dispose(); accept.dispose(); pick.dispose(); }); pick.show();
  }
  async function message(session: Session, value: unknown): Promise<void> {
    if (!isFromWebview(value)) return;
    if (value.type === 'rendered') session.initialized = true;
    events.fire({uri:session.uri.toString(), kind:session.kind, message:value});
    switch (value.type) {
      case 'ready': session.busy?.(); session.busy = undefined; session.ready = true; await load(session); break;
      case 'save': if (session.kind === 'block') await context.workspaceState.update(savedKey(session), value.saved); break;
      case 'openSource': {
        if (!path.isAbsolute(value.loc.file)) { void vscode.window.showWarningMessage(`SpinalBlocks: source path is not absolute: ${value.loc.file}`); break; }
        const document = await vscode.workspace.openTextDocument(vscode.Uri.file(value.loc.file));
        const line = Math.min(value.loc.line - 1, document.lineCount - 1);
        const column = vscode.window.visibleTextEditors.find(e => e.document.uri.fsPath === value.loc.file)?.viewColumn ?? vscode.window.visibleTextEditors.find(e => /\.scala$/i.test(e.document.uri.path))?.viewColumn ?? vscode.ViewColumn.Beside;
        await vscode.window.showTextDocument(document, {viewColumn:column, selection:new vscode.Range(line, 0, line, 0), preserveFocus:false}); break;
      }
      case 'navigated': session.path = value.path; session.panel.title = `${value.modules.at(-1)} - ${path.basename(session.uri.path)}`; break;
      case 'hierarchy': session.root = value.root; updateTree(); break;
      case 'busy':
        if (value.value && !session.busy) void vscode.window.withProgress({location:{viewId:'spinalblocks.hierarchy'}, title:'SpinalBlocks layout'}, () => new Promise<void>(resolve => {session.busy = resolve;}));
        if (!value.value) { session.busy?.(); session.busy = undefined; } break;
      case 'error': fail(value.message); break;
      case 'find': await find(session); break;
      case 'revealTree': {
        active = session; last = session; updateTree();
        let node = session.root;
        for (const name of value.path) node = node?.children.find(n => n.name === name) ?? null;
        if (node) await treeView.reveal(node, {select:true, focus:true, expand:true}); break;
      }
      case 'export': case 'exportPng': {
        if (context.testMode) break;
        const name = value.name.replace(/[^a-zA-Z0-9_.-]/g, '_') || 'diagram';
        const ext = value.type === 'export' ? 'svg' : 'png';
        const target = await vscode.window.showSaveDialog({defaultUri:vscode.Uri.joinPath(session.uri, '..', `${name}.${ext}`), filters:{[`${ext.toUpperCase()} image`]:[ext]}});
        if (target) await vscode.workspace.fs.writeFile(target, value.type === 'export' ? Buffer.from(value.svg, 'utf8') : new Uint8Array(value.bytes)); break;
      }
    }
  }
  function setup(uri: vscode.Uri, panel: vscode.WebviewPanel, kind: DiagramKind): Session {
    const dist = context.dist;
    panel.webview.options = {enableScripts:true, localResourceRoots:[dist]};
    const session: Session = {uri, panel, kind, root:null, path:[], ready:false, initialized:false, revision:0};
    sessions.add(session); active = session; last = session; updateTree();
    const receive = panel.webview.onDidReceiveMessage(value => {void message(session, value).catch(fail);});
    const focus = panel.onDidChangeViewState(() => { if (panel.active) {active = session; last = session;} else if (active === session) active = undefined; updateTree(); });
    const watcher = vscode.workspace.createFileSystemWatcher(new vscode.RelativePattern(vscode.Uri.joinPath(uri, '..'), '*'));
    let timer: ReturnType<typeof setTimeout> | undefined;
    const changed = (file: vscode.Uri) => {
      if (file.toString() !== uri.toString()) return;
      designs.invalidate(uri); clearTimeout(timer);
      timer = setTimeout(() => { if (session.ready) void load(session); }, 200);
    };
    const change = watcher.onDidChange(changed), create = watcher.onDidCreate(changed);
    panel.onDidDispose(() => {
      clearTimeout(timer); session.revision++; session.busy?.(); receive.dispose(); focus.dispose(); watcher.dispose(); change.dispose(); create.dispose();
      sessions.delete(session); if (active === session) active = undefined; if (last === session) last = [...sessions].at(-1); updateTree();
    });
    panel.webview.html = html(panel.webview, dist, kind, context.testMode);
    return session;
  }
  const provider: vscode.CustomReadonlyEditorProvider = {
    openCustomDocument(uri) { return {uri, dispose() {}}; },
    resolveCustomEditor(document, panel) { setup(document.uri, panel, 'block'); },
  };
  context.subscriptions.push(vscode.window.registerCustomEditorProvider(viewType, provider, {supportsMultipleEditorsPerDocument:false, webviewOptions:{retainContextWhenHidden:true}}));
  async function openSession(uri: vscode.Uri, kind: DiagramKind): Promise<Session> {
    let session = [...sessions].find(s => s.uri.toString() === uri.toString() && s.kind === kind);
    if (!session) {
      if (kind === 'block') {
        await vscode.commands.executeCommand('vscode.openWith', uri, viewType, {viewColumn:vscode.ViewColumn.Beside});
        session = [...sessions].find(s => s.uri.toString() === uri.toString() && s.kind === kind);
      } else session = setup(uri, vscode.window.createWebviewPanel('spinalblocks.fsm', `State Machines - ${path.basename(uri.path)}`, vscode.ViewColumn.Beside, {retainContextWhenHidden:true}), kind);
    }
    if (!session) throw new Error('Diagram did not open.');
    session.panel.reveal(undefined, true);
    if (!session.initialized) await new Promise<void>((resolve, reject) => {
      const listener = events.event(event => {
        if (event.uri !== uri.toString() || event.kind !== kind) return;
        if (event.message.type === 'rendered') { finish(); resolve(); }
        if (event.message.type === 'error') { finish(); reject(new Error(event.message.message)); }
      });
      const closed = session!.panel.onDidDispose(() => { finish(); reject(new Error('Diagram closed.')); });
      const timer = setTimeout(() => {finish(); reject(new Error('Timed out opening diagram.'));}, 90000);
      function finish() {clearTimeout(timer); listener.dispose(); closed.dispose();}
    });
    return session;
  }
  function source(value?: OpenRequest | vscode.Uri): SourceRequest | undefined {
    const editor = vscode.window.activeTextEditor;
    if (value instanceof vscode.Uri) return /\.scala$/i.test(value.path) ? {file:value.fsPath, line:editor?.document.uri.toString() === value.toString() ? editor.selection.active.line + 1 : 1} : undefined;
    if (value && typeof value.file === 'string' && typeof value.line === 'number' && Number.isSafeInteger(value.line) && value.line > 0) return value as SourceRequest;
    return editor && /\.scala$/i.test(editor.document.uri.path) ? {file:editor.document.uri.fsPath, line:editor.selection.active.line + 1} : undefined;
  }
  async function choose(request: SourceRequest, kind: DiagramKind, atLine: boolean): Promise<Choice | undefined> {
    let choices = await designs.choices(request, kind, atLine);
    if (!choices.length) { void vscode.window.showInformationMessage(`SpinalBlocks: No ${kind === 'block' ? 'module' : 'state machine'} ${atLine ? 'at this line' : 'defined in this file'} in the configured design files. Generate the design or set spinalblocks.designFiles.`); return; }
    if (choices.length === 1) return choices[0];
    const key = `choice:${kind}:${request.file}`;
    const remembered = context.workspaceState.get<string>(key);
    const preferred = choices.filter(c => c.uri.toString() === remembered);
    if (preferred.length) choices = preferred;
    if (choices.length === 1) return choices[0];
    const pick = await vscode.window.showQuickPick(choices.map(choice => ({label:choice.fsm ? choice.design.modules[choice.module].fsms!.find(f => f.id === choice.fsm)!.name : choice.module, description:vscode.workspace.asRelativePath(choice.uri), detail:`${choice.module}: ${choice.path.join('/') || '(top)'}`, choice})), {placeHolder:kind === 'block' ? 'Choose the module and design' : 'Choose a state machine and design', matchOnDescription:true, matchOnDetail:true});
    if (pick) await context.workspaceState.update(key, pick.choice.uri.toString());
    return pick?.choice;
  }
  async function fromSource(kind: DiagramKind, atLine: boolean, value?: OpenRequest | vscode.Uri): Promise<void> {
    let request = source(value);
    let choice: Choice | undefined;
    if (value && !(value instanceof vscode.Uri) && value.design && value.module && !value.file) {
      const uri = designUri(value.design), design = await designs.read(uri);
      const module = design?.modules[value.module];
      const instancePath = design && module ? instancePaths(design, module.name, 1)[0] : undefined;
      if (!design || !module || !instancePath) throw new Error(`No instantiated module ${value.module} in ${value.design}.`);
      choice = {uri, design, module:module.name, path:instancePath, line:1};
      if (kind === 'fsm') {
        const machines = (module.fsms ?? []).filter(f => !value.fsm || f.id === value.fsm);
        const machine = machines.length === 1 ? machines[0] : (await vscode.window.showQuickPick(machines.map(fsm => ({label:fsm.name, fsm})), {placeHolder:'Choose a state machine'}))?.fsm;
        if (!machine) {if (!machines.length) throw new Error(`No matching state machine in ${module.name}.`); return;}
        choice.fsm = machine.id;
      }
    } else {
      if (!request) return;
      choice = await choose(request, kind, atLine);
    }
    if (!choice) return;
    const session = await openSession(choice.uri, kind);
    if (kind === 'fsm') await session.panel.webview.postMessage({type:'showFsm', module:choice.module, fsm:choice.fsm!} satisfies ToWebview);
    else if (!atLine || moduleAt(choice.design, session.path) !== choice.module) await session.panel.webview.postMessage({type:'navigate', path:choice.path} satisfies ToWebview);
    if (atLine && request) await session.panel.webview.postMessage({type:'showLocation', file:request.file, line:choice.line} satisfies ToWebview);
  }
  const command = (name: string, fn: (...args: any[]) => unknown) => context.subscriptions.push(vscode.commands.registerCommand(name, (...args: any[]) => Promise.resolve(fn(...args)).catch(fail)));
  command('spinalblocks.open', async (value?: OpenRequest | vscode.Uri) => {
    if (source(value) || (value && !(value instanceof vscode.Uri) && value.design && value.module)) return fromSource('block', false, value);
    let uri = value instanceof vscode.Uri ? value : undefined;
    const textUri = vscode.window.activeTextEditor?.document.uri;
    uri ??= textUri && /\.json(\.gz)?$/i.test(textUri.path) ? textUri : current()?.uri;
    uri ??= (await vscode.window.showOpenDialog({canSelectMany:false, filters:{'SpinalBlocks design':['json','gz']}}))?.[0];
    if (uri) await openSession(uri, 'block');
  });
  command('spinalblocks.showLocation', (value?: OpenRequest | vscode.Uri) => fromSource('block', true, value));
  command('spinalblocks.openFsm', (value?: OpenRequest | vscode.Uri) => fromSource('fsm', false, value));
  command('spinalblocks.showFsmLocation', (value?: OpenRequest | vscode.Uri) => fromSource('fsm', true, value));
  command('spinalblocks.forgetDesignChoice', async () => {
    for (const key of context.workspaceState.keys()) if (key.startsWith('choice:')) await context.workspaceState.update(key, undefined);
  });
  command('spinalblocks.find', () => find());
  command('spinalblocks.navigate', async (instancePath: string[]) => {
    const session = blockSession(); if (!session || !Array.isArray(instancePath) || !instancePath.every(p => typeof p === 'string')) return;
    session.panel.reveal(undefined, true); await session.panel.webview.postMessage({type:'navigate', path:instancePath} satisfies ToWebview);
  });
  const selector = {scheme:'file', pattern:'**/*.scala'};
  context.subscriptions.push(vscode.languages.registerCodeLensProvider(selector, {
    onDidChangeCodeLenses:lenses.event,
    async provideCodeLenses(document, token) {
      const result = new Map<string, vscode.CodeLens>();
      for (const {design} of await designs.all()) for (const m of Object.values(design.modules)) {
        const add = (line: number, kind: DiagramKind, fsm?: string) => {
          if (line < 1 || line > document.lineCount || token.isCancellationRequested) return;
          const args: SourceRequest = {file:document.uri.fsPath, line, module:m.name, fsm};
          const key = `${line}:${kind}:${fsm ?? ''}`;
          const existing = result.get(key);
          if (existing?.command) {
            const shared = existing.command.arguments![0] as SourceRequest;
            delete shared.module;
            return;
          }
          result.set(key, new vscode.CodeLens(new vscode.Range(line-1,0,line-1,0), {title:kind === 'block' ? 'Block Diagram' : 'State Machines Diagram', command:kind === 'block' ? 'spinalblocks.open' : 'spinalblocks.openFsm', arguments:[args]}));
        };
        if (m.loc?.file === document.uri.fsPath) add(m.loc.line, 'block');
        for (const f of m.fsms ?? []) if (f.loc?.file === document.uri.fsPath) add(f.loc.line, 'fsm', f.id);
      }
      return [...result.values()];
    },
  }), vscode.languages.registerHoverProvider(selector, {
    async provideHover(document, position, token) {
      const request = {file:document.uri.fsPath, line:position.line + 1};
      const [blocks, fsms] = await Promise.all([designs.choices(request, 'block', true), designs.choices(request, 'fsm', true)]);
      if (token.isCancellationRequested || (!blocks.length && !fsms.length)) return;
      const content = new vscode.MarkdownString();
      const commands: string[] = [];
      for (const [found, name, title] of [[blocks, 'spinalblocks.showLocation', 'Show in Block Diagram'], [fsms, 'spinalblocks.showFsmLocation', 'Show in State Machines Diagram']] as const) {
        if (!found.length) continue; commands.push(name);
        content.appendMarkdown(`[${title}](command:${name}?${encodeURIComponent(JSON.stringify([request]))})  \n`);
      }
      content.isTrusted = {enabledCommands:commands};
      return new vscode.Hover(content, document.getWordRangeAtPosition(position));
    },
  }), vscode.workspace.onDidChangeConfiguration(event => {if (event.affectsConfiguration('spinalblocks.designFiles')) designs.watch();}));
  let cursorTimer: ReturnType<typeof setTimeout> | undefined;
  let cursorRevision = 0;
  context.subscriptions.push({dispose() {clearTimeout(cursorTimer);}}, vscode.window.onDidChangeTextEditorSelection(event => {
    clearTimeout(cursorTimer); const revision = ++cursorRevision;
    if (!vscode.workspace.getConfiguration('spinalblocks').get('followCursor', false) || !/\.scala$/i.test(event.textEditor.document.uri.path)) return;
    const file = event.textEditor.document.uri.fsPath, line = event.selections[0]?.active.line;
    if (line === undefined) return;
    cursorTimer = setTimeout(() => { void (async () => {
      for (const session of sessions) {
        if (!session.initialized || !session.panel.visible) continue;
        const design = await designs.read(session.uri);
        if (!design || revision !== cursorRevision) continue;
        const hits = locate(design, file, line+1);
        if (session.kind === 'fsm') {
          const hit = hits.find(h => ['fsm','state','transition'].includes(h.kind));
          if (!hit) continue;
          await session.panel.webview.postMessage({type:'showFsm', module:hit.module, fsm:hit.id} satisfies ToWebview);
          await session.panel.webview.postMessage({type:'showLocation', file, line:hit.loc.line} satisfies ToWebview);
        } else if (hits.some(h => h.module === moduleAt(design, session.path) && !['module','fsm','state','transition'].includes(h.kind))) await session.panel.webview.postMessage({type:'showLocation', file, line:line+1} satisfies ToWebview);
      }
    })().catch(fail); }, 180);
  }));
  if (context.testMode) return {
    events:events.event,
    send(uri, value, kind = 'block') { const session = [...sessions].find(s => s.uri.toString() === uri.toString() && s.kind === kind); return session?.panel.webview.postMessage(value) ?? Promise.resolve(false); },
    snapshot(uri, kind = 'block') { const session = [...sessions].find(s => s.uri.toString() === uri.toString() && s.kind === kind); return session && {root:session.root, path:session.path}; },
  };
}
