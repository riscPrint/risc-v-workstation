import { createEngine, type Details, type Viewport } from '../../../../SpinalBlocks/engine/src/index.ts';
import { workerLayout } from '../../../../SpinalBlocks/engine/src/elk.ts';
import { isToWebview, type FromWebview, type SavedView, type ToWebview } from './protocol';

declare function acquireVsCodeApi(): { postMessage(value: FromWebview): void; getState(): SavedView | undefined; setState(state: SavedView): void };
const vscode = acquireVsCodeApi();
async function main(): Promise<void> {
  const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
  const canvas = $('canvas'), crumbs = $('crumbs'), details = $('details'), menu = $('menu'), status = $('status');
  const post = (value: FromWebview) => vscode.postMessage(value);
  let saved = vscode.getState();
  let labels = saved?.labels ?? true;
  let failed = false;
  let loading = false;
  let loads = 0;
  let revealing = false;
  let saveTimer: ReturnType<typeof setTimeout> | undefined;
  const theme = () => document.body.classList.contains('vscode-light') || document.body.classList.contains('vscode-high-contrast-light') ? 'light' as const : 'dark' as const;
  function persist(viewport?: Viewport): void {
    if (!engine.design || loading) return;
    saved = {state:engine.state, viewport:viewport ?? engine.viewport, labels};
    vscode.setState(saved);
    post({type:'save', saved});
  }
  function reportRendered(): void {
    if (failed || !engine.currentScene) return;
    post({type:'rendered', path:engine.state.path, blocks:engine.currentScene.blocks.length, theme:theme(), loads});
  }
  function openSource(loc: NonNullable<Details['loc']>): void { post({type:'openSource', loc}); }
  // VS Code resource URLs are served through the webview's service worker. A worker
  // cannot import that URL directly, so fetch here and give ELK a same-origin blob.
  const response = await fetch(canvas.dataset.worker!);
  if (!response.ok) throw new Error(`Could not load ELK worker: ${response.status}`);
  const workerUrl = URL.createObjectURL(new Blob([await response.text()], {type:'text/javascript'}));
  // The HTML parser attached canvas before this script runs. The renderer needs a live CSSStyleSheet.
  const engine = createEngine(canvas, {
    openSource,
    stateChanged(_state, viewport) { persist(viewport); syncToggles(); },
    navigated(path, modules) {
      crumbs.replaceChildren();
      [modules[0], ...path].forEach((name, i) => {
        if (i) crumbs.append(' › ');
        crumbs.append(button(name, () => run(() => engine.navigate(path.slice(0, i)))));
      });
      const module = document.createElement('span'); module.textContent = ` : ${modules.at(-1)}`; crumbs.append(module);
      post({type:'navigated', path, modules}); showDetails(null);
      persist();
    },
    selectionChanged(d) {
      showDetails(d ? engine.describe(d.target) : null);
      if (revealing && d) engine.reveal(d.target);
    },
    contextMenu(d, x, y) {
      menu.replaceChildren();
      if (d?.loc) for (const kind of ['drivers','loads'] as const) menu.append(button(`Show ${kind}`, () => post({type:'dependencies',kind,file:d.loc!.file,line:d.loc!.line})));
      if (d?.loc) menu.append(button('Open Source', () => openSource(d.loc!)));
      if (d?.module && d.target.kind === 'block') {
        const id = d.target.id;
        menu.append(button('Open Module', () => run(() => engine.descend(id))));
        const instance = engine.design?.modules[engine.module ?? '']?.instances.find(i => i.id === id);
        if (instance) menu.append(button('Show in Explorer tree', () => post({type:'revealTree', path:[...engine.state.path, instance.name]})));
      }
      if (d?.target.kind === 'block') {
        const id = d.target.id;
        const node = engine.design?.modules[engine.module ?? '']?.nodes.find(n => n.id === id);
        if (node?.compound) menu.append(button(d.kind === 'area (collapsed)' ? 'Expand Area' : 'Collapse Area', () => run(() => engine.toggleArea(id))));
      }
      menu.hidden = !menu.childElementCount;
      menu.style.left = `${Math.max(0, Math.min(x, innerWidth - menu.offsetWidth))}px`;
      menu.style.top = `${Math.max(0, Math.min(y, innerHeight - menu.offsetHeight))}px`;
      menu.querySelector('button')?.focus();
    },
    busy(value) { $('busy').hidden = !value; canvas.setAttribute('aria-busy', String(value)); post({type:'busy', value}); },
    error(error) { failed = true; status.textContent = error.message; post({type:'error', message:error.message}); },
  }, {layout:workerLayout(workerUrl), doubleClick:'source'});
  engine.setRenderOptions({theme:theme(), showEdgeLabels:labels});
  new MutationObserver(() => { engine.setRenderOptions({theme:theme()}); reportRendered(); }).observe(document.body, {attributes:true, attributeFilter:['class']});

  // Serialise file reloads and navigation so a slow earlier layout cannot replace a newer one.
  let queue = Promise.resolve();
  function run(action: () => Promise<void> | void): void {
    queue = queue.then(async () => {
      failed = false;
      await action();
      if (!failed) { status.textContent = engine.module ? `${engine.module} · ${engine.currentScene?.blocks.length ?? 0} blocks` : ''; reportRendered(); }
    }).catch(error => { loading = false; failed = true; status.textContent = String(error); post({type:'error', message:String(error)}); });
  }
  window.addEventListener('message', (event: MessageEvent<unknown>) => {
    if (!isToWebview(event.data)) return;
    const message: ToWebview = event.data;
    run(async () => {
      switch (message.type) {
        case 'load': {
          loads++;
          if (engine.design) persist();
          saved ??= message.saved;
          labels = saved?.labels ?? labels;
          engine.setRenderOptions({showEdgeLabels:labels});
          loading = true;
          showDetails(null);
          try { await engine.setDesign(new Uint8Array(message.bytes), saved?.state, saved?.viewport); }
          finally { loading = false; }
          post({type:'hierarchy', root:engine.hierarchy()});
          if (!failed) { persist(); syncToggles(); }
          break;
        }
        case 'navigate': await engine.navigate(message.path); break;
        case 'showLocation': {
          let found: boolean;
          revealing = true;
          try { found = await engine.showLocation(message.file, message.line); }
          finally { revealing = false; }
          if (document.body.dataset.test === 'true') post({type:'selected', file:message.file, line:message.line, found, kind:'block'});
          break;
        }
        case 'exportImage': await exportImage(message.format); break;
        case 'search': post({type:'searchResults', hits:engine.search(message.query), request:message.request}); break;
        case 'pick': engine.select(message.target); engine.reveal(message.target); persist(); break;
        case 'openModuleSource': {
          const loc = engine.design?.modules[engine.module ?? '']?.loc;
          if (loc) openSource(loc); else throw new Error('This module has no source location.');
          break;
        }
      }
    });
  });
  $('up').onclick = () => run(() => engine.up());
  $('fit').onclick = () => {engine.fit(); persist();};
  $('collapse').onclick = () => run(() => engine.setAllAreas(true));
  $('expand').onclick = () => run(() => engine.setAllAreas(false));
  $<HTMLInputElement>('clocks').onchange = event => run(() => engine.setOptions({showClocks:(event.target as HTMLInputElement).checked}));
  $<HTMLInputElement>('control').onchange = event => run(() => engine.setOptions({showControl:(event.target as HTMLInputElement).checked}));
  $<HTMLInputElement>('labels').onchange = event => { labels = (event.target as HTMLInputElement).checked; engine.setRenderOptions({showEdgeLabels:labels}); persist(); };
  async function exportImage(format: 'svg' | 'png'): Promise<void> {
    if (!engine.currentScene) return;
    const name = engine.module ?? 'diagram';
    if (format === 'svg') post({type:'export', svg:engine.exportSvg(), name});
    else post({type:'exportPng', bytes:await (await engine.exportPng(2)).arrayBuffer(), name});
  }
  $('export').onclick = () => run(() => exportImage('svg'));
  $('png').onclick = () => run(() => exportImage('png'));
  // The engine reports state changes for layouts; pan and zoom need a host-side save too.
  for (const event of ['pointerup','wheel','keydown']) canvas.addEventListener(event, () => {clearTimeout(saveTimer); saveTimer = setTimeout(() => persist(), 200);});
  window.addEventListener('pagehide', () => persist());
  document.addEventListener('click', event => {if (!menu.contains(event.target as Node)) menu.hidden = true;});
  menu.addEventListener('click', () => {menu.hidden = true;});
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {menu.hidden = true; engine.select(null);}
    if (event.key === 'Backspace' && !(event.target instanceof HTMLInputElement)) {event.preventDefault(); run(() => engine.up());}
  });
  function syncToggles(): void {
    $<HTMLInputElement>('clocks').checked = engine.state.options.showClocks;
    $<HTMLInputElement>('control').checked = engine.state.options.showControl;
    $<HTMLInputElement>('labels').checked = labels;
  }
  function button(text: string, action: () => void): HTMLButtonElement {
    const result = document.createElement('button'); result.textContent = text; result.onclick = action; return result;
  }
  function showDetails(d: Details | null): void {
    details.hidden = !d; details.replaceChildren();
    if (!d) return;
    const title = document.createElement('h3'); title.textContent = d.title;
    const subtitle = document.createElement('p'); subtitle.textContent = `${d.kind} · ${d.subtitle}`;
    details.append(button('Close', () => engine.select(null)), title, subtitle);
    if (d.loc) details.append(button(`Open Source (${d.loc.line})`, () => openSource(d.loc!)));
    if (d.module && d.target.kind === 'block') { const id = d.target.id; details.append(button('Open Module', () => run(() => engine.descend(id)))); }
    const rows = [
      ...d.signals.map(s => `${s.name}: ${s.type}[${s.width}]${s.reg ? ' register' : ''}`),
      ...d.ports.map(p => `${p.dir} ${p.name}: ${p.width} bit`),
      ...d.nets.map(n => `${n.name}: ${n.from} → ${n.to.join(', ')}`),
    ];
    const list = document.createElement('ul');
    for (const text of rows.slice(0, 200)) { const item = document.createElement('li'); item.textContent = text; list.append(item); }
    details.append(list);
    if (rows.length > 200) details.append(`Showing 200 of ${rows.length} entries.`);
  }
  post({type:'ready'});

}
void main().catch(error => vscode.postMessage({type:'error', message:String(error)}));
