import * as vscode from 'vscode';
import assert from 'node:assert/strict';
import * as fs from 'node:fs/promises';
import * as path from 'node:path';
import { gunzipSync } from 'node:zlib';
import { chromium, type Frame, type Page } from 'playwright-core';
import { instancePaths, type Design } from '../../../../SpinalBlocks/engine/src/core.ts';
import type { FromWebview, ToWebview } from '../src/protocol';
import type { WorkstationApi } from '../../../src/api';

// The test-only API and the location/FSM messages as planned by the extension. Typed here, so the
// test states the contract it relies on.
type Kind = 'block' | 'fsm';
type Selected = { type: 'selected'; file: string; line: number; found: boolean; kind: Kind };
type Rendered = Extract<FromWebview, {type:'rendered'}> & { fsm?: string };
type Message = Exclude<FromWebview, {type:'rendered'}> | Rendered | Selected;
type Outgoing = ToWebview
  | { type: 'showLocation'; file: string; line: number }
  | { type: 'showFsm'; module: string; fsm: string }
  | { type: 'exportImage'; format: 'svg' | 'png' };
interface TestEvent { uri: string; message: Message; kind?: Kind }
interface TestApi {
  events: vscode.Event<TestEvent>;
  send(uri: vscode.Uri, message: Outgoing, kind?: Kind): Thenable<boolean>;
  snapshot(uri: vscode.Uri, kind?: Kind): unknown;
}
interface Loc { file: string; line: number }

export async function run(): Promise<void> {
  const extension = vscode.extensions.getExtension<WorkstationApi>('riscprint.risc-v-workstation');
  assert.ok(extension);
  const exported = (await extension.activate()).features.spinalblocks as TestApi | undefined;
  assert.ok(exported, 'test-only API should be enabled');
  const api: TestApi = exported;
  const uri = vscode.Uri.file(process.env.SPINALBLOCKS_TEST_DESIGN!);
  const fsmUri = vscode.Uri.file(process.env.SPINALBLOCKS_TEST_FSM_DESIGN!);
  const fsmSource = process.env.SPINALBLOCKS_TEST_FSM_SOURCE!;
  const diagnosticBrowser = await chromium.connectOverCDP(`http://127.0.0.1:${process.env.SPINALBLOCKS_CDP_PORT}`);
  for (const page of diagnosticBrowser.contexts().flatMap(c => c.pages())) {
    page.on('console', message => {if (message.type() === 'error') console.error('BROWSER', message.text());});
    page.on('pageerror', error => console.error('PAGEERROR', error));
  }
  /** Next message from the `kind` panel of design `target` that matches; an error message from it fails. */
  function on<T extends Message = Message>(target: vscode.Uri, kind: Kind, predicate: (message: Message) => boolean, timeout = 90000): Promise<T> {
    return new Promise((resolve, reject) => {
      const listener = api.events(event => {
        if (event.uri !== target.toString() || (event.kind ?? 'block') !== kind) return;
        if (event.message.type === 'error') { clearTimeout(timer); listener.dispose(); reject(new Error(`${kind}: ${event.message.message}`)); }
        else if (predicate(event.message)) { clearTimeout(timer); listener.dispose(); resolve(event.message as T); }
      });
      const timer = setTimeout(() => { listener.dispose(); reject(new Error(`Timed out waiting for ${kind} webview message from ${path.basename(target.fsPath)}`)); }, timeout);
    });
  }
  const next = <T extends Message = Message>(predicate: (message: Message) => boolean, timeout?: number) => on<T>(uri, 'block', predicate, timeout);
  const rendered = (m: Message): m is Rendered => m.type === 'rendered';
  const selected = (m: Message): m is Selected => m.type === 'selected';
  /** Shows `file` in a text editor with the cursor at the start of `line` (1-based). */
  async function editAt(file: string, line: number): Promise<vscode.TextEditor> {
    const document = await vscode.workspace.openTextDocument(vscode.Uri.file(file));
    const at = new vscode.Range(line - 1, 0, line - 1, 0);
    const editor = await vscode.window.showTextDocument(document, {viewColumn:vscode.ViewColumn.One, selection:at, preserveFocus:false});
    assert.equal(vscode.window.activeTextEditor?.document.uri.fsPath, file);
    return editor;
  }
  async function workbench(): Promise<Page> {
    const page = diagnosticBrowser.contexts().flatMap(c => c.pages()).find(p => p.url().includes('workbench'));
    assert.ok(page, 'VS Code workbench CDP target');
    return page;
  }
  /** The webview frame that currently contains `selector` (frames change when panels are reopened). */
  async function frameWith(page: Page, selector: string, hasText?: string): Promise<Frame> {
    for (let attempt = 0; attempt < 50; attempt++) {
      for (const candidate of page.frames()) {
        try { if (await candidate.locator(selector, hasText ? {hasText} : undefined).count()) return candidate; } catch { /* detached */ }
      }
      await new Promise(resolve => setTimeout(resolve, 200));
    }
    assert.fail(`no webview frame with ${selector}${hasText ? ` "${hasText}"` : ''}`);
  }
  async function checkExports(target: vscode.Uri, kind: Kind): Promise<void> {
    const svg = on<Extract<FromWebview,{type:'export'}>>(target, kind, m => m.type === 'export');
    await api.send(target, {type:'exportImage',format:'svg'}, kind);
    assert.match((await svg).svg, /<svg[\s>]/);
    const png = on<Extract<FromWebview,{type:'exportPng'}>>(target, kind, m => m.type === 'exportPng');
    await api.send(target, {type:'exportImage',format:'png'}, kind);
    const bytes = new Uint8Array((await png).bytes);
    assert.deepEqual(Array.from(bytes.slice(0,8)), [137,80,78,71,13,10,26,10], 'PNG signature');
    assert.ok(bytes.length > 100, 'nonempty PNG image');
  }
  async function quiet(): Promise<void> {
    await vscode.commands.executeCommand('workbench.action.closeAuxiliaryBar');
    const commands = await vscode.commands.getCommands(true);
    for (const command of ['notifications.clearAll', 'spinalblocks.hierarchy.focus']) {
      if (commands.includes(command)) await vscode.commands.executeCommand(command);
    }
  }
  const themes = {
    light: ['Default Light Modern', 'light'], dark: ['Default Dark Modern', 'dark'], 'high-contrast': ['Default High Contrast', 'dark'],
  } as const;
  const screenshotDir = path.join(extension.extensionPath, '.vscode-test', 'screenshots', 'spinalblocks');
  await fs.mkdir(screenshotDir, {recursive:true});

  try {
    // --- Block diagram: open, navigate, open source, search, reload, reopen. ---
    const initial = next(m => rendered(m) && m.blocks > 0);
    await vscode.commands.executeCommand('vscode.openWith', uri, 'spinalblocks.diagram');
    console.log('INITIAL', await initial);
    const navigation = next(m => rendered(m) && m.path.join('/') === 'tile/core');
    await vscode.commands.executeCommand('spinalblocks.navigate', ['tile','core']);
    console.log('NAVIGATED', await navigation);
    const design = JSON.parse(gunzipSync(await fs.readFile(uri.fsPath)).toString('utf8'));
    let module = design.top;
    for (const name of ['tile','core']) module = design.modules[module].instances.find((i: {name:string}) => i.name === name).module;
    assert.equal(module, 'BoomCore');
    const core = design.modules[module];
    const loc = core.loc as Loc;
    assert.ok(path.isAbsolute(loc.file));
    const baseDocument = await vscode.workspace.openTextDocument(vscode.Uri.file(loc.file));
    const baseLenses = await vscode.commands.executeCommand<vscode.CodeLens[]>('vscode.executeCodeLensProvider', baseDocument.uri);
    assert.equal(baseLenses?.filter(l => l.range.start.line === loc.line-1 && l.command?.title === 'Block Diagram').length, 1, 'shared class locations have one block Code Lens');
    const sourceMessage = next<Extract<FromWebview,{type:'openSource'}>>(m => m.type === 'openSource');
    const sourceOpened = new Promise<vscode.TextEditor>((resolve, reject) => {
      const check = (editor: vscode.TextEditor | undefined) => {
        if (editor?.document.uri.fsPath === loc.file && editor.selection.start.line === loc.line - 1) {
          clearTimeout(timer); activated.dispose(); selection.dispose(); resolve(editor);
        }
      };
      const activated = vscode.window.onDidChangeActiveTextEditor(check);
      const selection = vscode.window.onDidChangeTextEditorSelection(event => check(event.textEditor));
      const timer = setTimeout(() => {activated.dispose(); selection.dispose(); reject(new Error(`Source did not open at line ${loc.line}: ${loc.file}`));}, 15000);
    });
    await api.send(uri, {type:'openModuleSource'});
    assert.deepEqual((await sourceMessage).loc, loc);
    const editor = await sourceOpened;
    assert.equal(editor.selection.start.line, loc.line - 1);
    console.log('SOURCE', editor.document.uri.fsPath, editor.selection.start.line + 1);
    await vscode.commands.executeCommand('workbench.action.closeActiveEditor');
    await vscode.commands.executeCommand('vscode.openWith', uri, 'spinalblocks.diagram');
    // Search runs inside the same webview and returns engine targets, then reveal/select uses them.
    const results = next<Extract<FromWebview,{type:'searchResults'}>>(m => m.type === 'searchResults' && m.request === 1);
    await api.send(uri, {type:'search',query:'rob',request:1});
    const hits = (await results).hits;
    assert.ok(hits.length > 0);
    await api.send(uri, {type:'pick',target:hits[0].target});
    const reloaded = next(m => rendered(m) && m.loads > 1 && m.path.join('/') === 'tile/core');
    await fs.writeFile(uri.fsPath, await fs.readFile(uri.fsPath));
    console.log('RELOAD', await reloaded);
    assert.deepEqual((api.snapshot(uri) as {path?: string[]} | undefined)?.path, ['tile','core']);
    await vscode.commands.executeCommand('workbench.action.closeActiveEditor');
    const reopened = next(m => rendered(m) && m.path.join('/') === 'tile/core');
    await vscode.commands.executeCommand('vscode.openWith', uri, 'spinalblocks.diagram');
    console.log('REOPEN', await reopened);
    const page = await workbench();
    const frame = await frameWith(page, '#canvas .sb-svg');
    assert.ok(await frame.locator('.sb-blk').count() > 0);
    const fill = await frame.locator('.sb-frame').first().evaluate(el => getComputedStyle(el).fill);
    assert.notEqual(fill, 'rgb(0, 0, 0)', 'CSP must allow renderer CSSOM rules');
    await quiet();
    for (const name of ['light', 'dark', 'high-contrast'] as const) {
      const [theme, mode] = themes[name];
      const themed = next(m => rendered(m) && m.theme === mode);
      await vscode.workspace.getConfiguration('workbench').update('colorTheme', theme, vscode.ConfigurationTarget.Global);
      await themed;
      await frame.locator('#fit').click();
      await page.screenshot({path:path.join(screenshotDir, `${name}.png`)});
    }
    console.log('SCREENSHOTS and CSP styles verified');

    // --- Scala editor -> block diagram: Open discovers the design, Show at source selects the element. ---
    // BoomCore's own loc is the shared BoomModule base class, so pick a line in exu/core.scala that
    // holds an instance and one that holds a port of BoomCore.
    const instanceLoc = (core.instances.find((i: {name:string}) => i.name === 'fp_pipeline') ?? core.instances.find((i: {loc:Loc|null}) => i.loc))?.loc as Loc;
    assert.ok(instanceLoc && path.isAbsolute(instanceLoc.file), 'BoomCore instance with a source location');
    const portLoc = (core.ports as {loc:Loc|null}[]).map(p => p.loc).find(l => l?.file === instanceLoc.file && l.line !== instanceLoc.line) as Loc;
    assert.ok(portLoc, 'BoomCore port declared in the same Scala file');
    await fs.access(instanceLoc.file);
    await vscode.commands.executeCommand('workbench.action.closeAllEditors');
    await editAt(instanceLoc.file, instanceLoc.line);
    const fromScala = next(m => rendered(m) && m.blocks > 0);
    await vscode.commands.executeCommand('spinalblocks.open');
    console.log('OPEN FROM SCALA', path.basename(instanceLoc.file), await fromScala);
    // Without arguments the command uses the Scala editor's cursor.
    await editAt(instanceLoc.file, instanceLoc.line);
    const atCursor = next<Selected>(m => selected(m) && m.line === instanceLoc.line);
    await vscode.commands.executeCommand('spinalblocks.showLocation');
    const cursorHit = await atCursor;
    console.log('SHOW AT CURSOR', cursorHit);
    assert.equal(cursorHit.found, true, `nothing found at ${instanceLoc.file}:${instanceLoc.line}`);
    assert.equal(cursorHit.kind, 'block');
    assert.equal(path.resolve(cursorHit.file), instanceLoc.file);
    assert.deepEqual((api.snapshot(uri) as {path?: string[]} | undefined)?.path, ['tile','core'], 'the hit is inside BoomCore');
    // Explicit arguments, as used by other commands and links.
    const atPort = next<Selected>(m => selected(m) && m.line === portLoc.line);
    await vscode.commands.executeCommand('spinalblocks.showLocation', {file:portLoc.file, line:portLoc.line});
    const portHit = await atPort;
    console.log('SHOW AT PORT', portHit);
    assert.equal(portHit.found, true);
    assert.equal(portHit.kind, 'block');
    // A line with no declaration is reported as not found rather than selecting something else.
    const miss = next<Selected>(m => selected(m) && m.line === 1);
    await api.send(uri, {type:'showLocation', file:instanceLoc.file, line:1});
    const missHit = await miss;
    assert.equal(missHit.found, false);
    assert.equal(missHit.kind, 'block');
    const selectedFrame = await frameWith(page, '#canvas .sb-svg');
    assert.ok(await selectedFrame.locator('.sb-sel').count() > 0, 'Show selects a rendered SVG element');
    await checkExports(uri, 'block');
    const typedDesign = design as Design;
    const repeated = Object.values(typedDesign.modules).map(m => ({module:m, paths:instancePaths(typedDesign, m.name, 2)})).find(x => x.paths.length === 2 && x.module.ports.some(p => p.loc));
    if (repeated) {
      const declaration = repeated.module.ports.find(p => p.loc)!.loc!;
      const repeatedPath = repeated.paths[1];
      const inSecond = next(m => rendered(m) && m.path.join('/') === repeatedPath.join('/'));
      await api.send(uri, {type:'navigate',path:repeatedPath}); await inSecond;
      const kept = next<Selected>(m => selected(m) && m.file === declaration.file && m.line === declaration.line);
      await vscode.commands.executeCommand('spinalblocks.showLocation', {file:declaration.file,line:declaration.line,design:uri.fsPath,module:repeated.module.name});
      assert.equal((await kept).found, true);
      assert.deepEqual((api.snapshot(uri) as {path:string[]}).path, repeatedPath, 'Show preserves the current instance of a reused module');
      const restored = next(m => rendered(m) && m.path.join('/') === 'tile/core');
      await api.send(uri, {type:'navigate',path:['tile','core']}); await restored;
    }
    await editAt(portLoc.file, portLoc.line);
    await vscode.workspace.getConfiguration('spinalblocks').update('followCursor', true, vscode.ConfigurationTarget.Workspace);
    const followed = next<Selected>(m => selected(m) && m.line === instanceLoc.line);
    await editAt(instanceLoc.file, instanceLoc.line);
    assert.equal((await followed).found, true, 'visible block diagram follows Scala cursor');
    await vscode.workspace.getConfiguration('spinalblocks').update('followCursor', false, vscode.ConfigurationTarget.Workspace);
    const selectedBox = await selectedFrame.locator('.sb-sel > .sb-box').first().boundingBox();
    const canvasBox = await selectedFrame.locator('#canvas').boundingBox();
    assert.ok(selectedBox && canvasBox);
    assert.ok(Math.abs(selectedBox.x + selectedBox.width/2 - canvasBox.x - canvasBox.width/2) < 3, 'selection stays centred after opening details');
    for (const name of ['light','dark'] as const) {
      const [theme, mode] = themes[name];
      const themed = next(m => rendered(m) && m.theme === mode);
      await vscode.workspace.getConfiguration('workbench').update('colorTheme', theme, vscode.ConfigurationTarget.Global);
      await themed;
      await page.screenshot({path:path.join(screenshotDir, `editor-${name}.png`)});
    }
    console.log('SHOW AT SOURCE, cursor following and exports verified');

    // Check generated FSM data when present, then use a stable synthetic design for source links.
    const realFsmModule = Object.values(typedDesign.modules).find(m => m.fsms?.some(f => f.states.length > 0));
    if (realFsmModule) {
      const realFsm = realFsmModule.fsms!.find(f => f.states.length > 0)!;
      const realShown = on<Rendered>(uri, 'fsm', m => rendered(m) && m.fsm === realFsm.id && m.blocks > 0);
      await vscode.commands.executeCommand('spinalblocks.openFsm', {design:uri.fsPath,module:realFsmModule.name,fsm:realFsm.id});
      console.log('GENERATED FSM', await realShown);
    }
    // --- Scala editor -> FSM panel on a synthetic design. ---
    const fsmDesign = JSON.parse(await fs.readFile(fsmUri.fsPath, 'utf8'));
    const fsmModule = fsmDesign.modules[fsmDesign.top];
    type FsmData = {id:string; name:string; loc:Loc; states:{name:string; loc:Loc}[]};
    const [ctrl, mode] = fsmModule.fsms as FsmData[];
    const isFsm = (m: Rendered, fsm: FsmData) => m.fsm === fsm.id || m.fsm === fsm.name;
    const waitState = ctrl.states.find(s => s.name === 'WAIT_RSP')!;
    assert.equal(waitState.loc.file, fsmSource);
    await vscode.commands.executeCommand('workbench.action.closeAllEditors');
    await editAt(fsmSource, waitState.loc.line);
    const fsmShown = on<Rendered>(fsmUri, 'fsm', m => rendered(m) && isFsm(m, ctrl));
    const fsmSelected = on<Selected>(fsmUri, 'fsm', m => selected(m) && m.line === waitState.loc.line);
    await vscode.commands.executeCommand('spinalblocks.showFsmLocation');
    console.log('FSM AT CURSOR', await fsmShown);
    const stateHit = await fsmSelected;
    console.log('FSM SELECTED', stateHit);
    assert.equal(stateHit.found, true, 'WAIT_RSP state found');
    assert.equal(stateHit.kind, 'fsm');
    assert.ok(api.snapshot(fsmUri, 'fsm'), 'FSM panel session');
    // Switch machines inside the panel, then back with the command and explicit arguments.
    const switched = on<Rendered>(fsmUri, 'fsm', m => rendered(m) && isFsm(m, mode));
    await api.send(fsmUri, {type:'showFsm', module:fsmModule.name, fsm:mode.id}, 'fsm');
    console.log('FSM SWITCHED', await switched);
    const byLocation = on<Rendered>(fsmUri, 'fsm', m => rendered(m) && isFsm(m, ctrl));
    await vscode.commands.executeCommand('spinalblocks.openFsm', {file:fsmSource, line:ctrl.loc.line, module:fsmModule.name, fsm:ctrl.id});
    console.log('OPEN FSM BY LOCATION', await byLocation);
    const byName = on<Rendered>(fsmUri, 'fsm', m => rendered(m) && isFsm(m, mode));
    await vscode.commands.executeCommand('spinalblocks.openFsm', {design:fsmUri.fsPath, module:fsmModule.name, fsm:mode.id});
    console.log('OPEN FSM BY NAME', await byName);
    const back = on<Rendered>(fsmUri, 'fsm', m => rendered(m) && isFsm(m, ctrl));
    await api.send(fsmUri, {type:'showFsm', module:fsmModule.name, fsm:ctrl.id}, 'fsm');
    await back;
    const fsmMiss = on<Selected>(fsmUri, 'fsm', m => selected(m) && m.line === 1);
    await api.send(fsmUri, {type:'showLocation', file:fsmSource, line:1}, 'fsm');
    assert.equal((await fsmMiss).found, false);
    const stateAgain = on<Selected>(fsmUri, 'fsm', m => selected(m) && m.line === waitState.loc.line);
    await api.send(fsmUri, {type:'showLocation', file:fsmSource, line:waitState.loc.line}, 'fsm');
    assert.equal((await stateAgain).found, true);
    const fsmFrame = await frameWith(page, 'svg text', 'WAIT_RSP');
    assert.ok(await fsmFrame.locator('.sb-sel').count() > 0, 'Show selects a rendered FSM element');
    const fsmDocument = await vscode.workspace.openTextDocument(vscode.Uri.file(fsmSource));
    const codeLenses = await vscode.commands.executeCommand<vscode.CodeLens[]>('vscode.executeCodeLensProvider', fsmDocument.uri);
    assert.ok(codeLenses?.some(l => l.command?.title === 'Block Diagram'), 'Component class Code Lens');
    assert.equal(codeLenses?.filter(l => l.command?.title === 'State Machines Diagram').length, 2, 'one Code Lens per machine');
    const hovers = await vscode.commands.executeCommand<vscode.Hover[]>('vscode.executeHoverProvider', fsmDocument.uri, new vscode.Position(waitState.loc.line-1, 8));
    assert.ok(hovers?.some(h => h.contents.some(c => typeof c === 'object' && 'value' in c && String(c.value).includes('spinalblocks.showFsmLocation'))), 'FSM hover contains the command link');
    await checkExports(fsmUri, 'fsm');
    for (const state of ctrl.states) assert.ok(await fsmFrame.locator('svg text', {hasText:state.name}).count() > 0, `state ${state.name} drawn`);
    await quiet();
    for (const name of ['light', 'dark'] as const) {
      const [theme, themeMode] = themes[name];
      const themed = on(fsmUri, 'fsm', m => rendered(m) && m.theme === themeMode);
      await vscode.workspace.getConfiguration('workbench').update('colorTheme', theme, vscode.ConfigurationTarget.Global);
      await themed;
      if (await fsmFrame.locator('#fit').count()) await fsmFrame.locator('#fit').click();
      await page.screenshot({path:path.join(screenshotDir, `fsm-${name}.png`)});
    }
    const fsmReload = on<Rendered>(fsmUri, 'fsm', m => rendered(m) && m.loads > 1 && isFsm(m, ctrl));
    await fs.writeFile(fsmUri.fsPath, await fs.readFile(fsmUri.fsPath));
    await fsmReload;
    console.log('FSM live reload, panel and screenshots verified');
    console.log('SpinalBlocks integration passed');
  } finally { await diagnosticBrowser.close(); }
}
