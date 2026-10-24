// Browser host: file loading, hierarchy tree, breadcrumbs, search, details panel. The diagram itself is the engine.

import { createEngine, createFsmView, initialView, loadDesign } from '../../../engine/src/index.ts';
import type { Details, FsmDetails, FsmEntry, HierarchyNode, Loc, SearchHit, ViewState, Viewport } from '../../../engine/src/index.ts';
import { workerLayout } from '../../../engine/src/elk.ts';

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const canvas = $('canvas'), crumbs = $('crumbs'), tree = $('tree'), details = $('details'), hitsEl = $<HTMLUListElement>('hits');
const search = $<HTMLInputElement>('search'), status = $('status'), busy = $('busy'), drop = $('drop');
const editor = $<HTMLSelectElement>('editor');

editor.value = localStorage.getItem('spinalblocks.editor') ?? 'vscode';
editor.onchange = () => localStorage.setItem('spinalblocks.editor', editor.value);

function sourceUrl(loc: Loc): string | null {
  if (!loc.file.startsWith('/')) return null; // e.g. spinal.lib sources, not on disk
  switch (editor.value) {
    case 'cursor': return `cursor://file${loc.file}:${loc.line}`;
    case 'idea': return `idea://open?file=${encodeURIComponent(loc.file)}&line=${loc.line}`;
    case 'file': return `file://${loc.file}`;
    default: return `vscode://file${loc.file}:${loc.line}`;
  }
}

function openSource(loc: Loc): void {
  const url = sourceUrl(loc);
  if (!url) { status.textContent = `${loc.file}:${loc.line} is not a local file`; return; }
  const a = document.createElement('a');
  a.href = url;
  a.click();
}

let stateKey = '';
let saveTimer = 0;

const engine = createEngine(canvas, {
  openSource,
  stateChanged(state: ViewState, viewport: Viewport) {
    clearTimeout(saveTimer);
    saveTimer = window.setTimeout(() => localStorage.setItem(stateKey, JSON.stringify({ state, viewport })), 300);
  },
  navigated(path, modules) {
    const hash = '#/' + path.join('/');
    if (location.hash !== hash) history.pushState(null, '', hash);
    renderCrumbs(path, modules);
    if (engine.design) refreshFsmList();
    markTree(path);
    const scene = engine.currentScene;
    status.textContent = scene ? `${modules.at(-1)} · ${scene.blocks.length} blocks · ${scene.edges.length} wires` : '';
    showDetails(null);
  },
  selectionChanged: showDetails,
  contextMenu: blockMenu,
  busy(b) { busy.hidden = !b; },
  error(e) { status.textContent = `Error: ${e.message}`; console.error(e); },
}, { layout: workerLayout(new URL('elk-worker.js', location.href).href) });

// ---------------------------------------------------------------------------------------------
// State machines

const fsmCanvas = $('fsm-canvas'), fsmPick = $<HTMLSelectElement>('fsm-pick');
const fsms = createFsmView(fsmCanvas, {
  openSource,
  selectionChanged: showFsmDetails,
  contextMenu: (d, x, y) => showMenu(x, y, d?.loc ? [['Open Source', () => openSource(d.loc!)]] : []),
  busy(b) { busy.hidden = !b; },
  error(e) { status.textContent = `Error: ${e.message}`; console.error(e); },
}, { layout: workerLayout(new URL('elk-worker.js', location.href).href) });
let mode: 'blocks' | 'fsm' = 'blocks';
let fsmEntries: FsmEntry[] = [];

/** State machines of the shown module (all of the design's when it has none). */
function refreshFsmList(): void {
  const all = fsms.list();
  const here = all.filter(e => e.module === engine.module);
  fsmEntries = here.length ? here : all;
  $('fsm-count').textContent = here.length ? `(${here.length})` : all.length ? `(${all.length} in design)` : '';
  $<HTMLButtonElement>('mode-fsm').disabled = all.length === 0;
  fsmPick.replaceChildren(...fsmEntries.map((e, i) => {
    const o = document.createElement('option');
    o.value = String(i);
    o.textContent = here.length ? e.fsm.name : `${e.module} · ${e.fsm.name}`;
    return o;
  }));
  if (mode === 'fsm') void showFsm(0);
}

async function showFsm(i: number): Promise<void> {
  const e = fsmEntries[i];
  if (!e) return;
  fsmPick.value = String(i);
  await fsms.show(e.module, e.fsm.id);
  fsms.fit();
  const s = fsms.currentScene;
  status.textContent = s ? `${e.module} · ${e.fsm.name} · ${s.states.length} states · ${s.transitions.length} transitions` : '';
}

function setMode(m: 'blocks' | 'fsm', fsmIndex = 0): void {
  mode = m;
  $('mode-blocks').classList.toggle('on', m === 'blocks');
  $('mode-fsm').classList.toggle('on', m === 'fsm');
  canvas.hidden = m !== 'blocks';
  fsmCanvas.hidden = m !== 'fsm';
  $('blocks-tools').hidden = m !== 'blocks';
  $('fsm-tools').hidden = m !== 'fsm';
  showDetails(null);
  if (m === 'fsm') void showFsm(fsmIndex);
  else engine.fit();
}

$('mode-blocks').onclick = () => setMode('blocks');
$('mode-fsm').onclick = () => setMode('fsm');
fsmPick.onchange = () => void showFsm(Number(fsmPick.value));
$<HTMLInputElement>('conditions').onchange = e => fsms.setOptions({ showConditions: (e.target as HTMLInputElement).checked });
$<HTMLInputElement>('comments').onchange = e => fsms.setOptions({ showComments: (e.target as HTMLInputElement).checked });

function showFsmDetails(d: FsmDetails | null): void {
  details.hidden = !d;
  if (!d) return;
  details.replaceChildren();
  const h = document.createElement('h2');
  h.textContent = d.title;
  const sub = document.createElement('div');
  sub.className = 'sub';
  sub.textContent = d.kind;
  details.append(h, sub);
  const actions = document.createElement('div');
  actions.className = 'actions';
  if (d.loc) actions.append(button(`Source: ${d.loc.file.split('/').pop()}:${d.loc.line}`, () => openSource(d.loc!)));
  details.append(actions);
  if (d.transitions.length) section(`Transitions (${d.transitions.length})`, d.transitions.map(t =>
    [locLink(`${t.from ?? 'any'} → ${t.to ?? '?'}`, t.loc), t.condition ?? '', t.comment ?? '']));
}

// ---------------------------------------------------------------------------------------------
// Context menu

type MenuItem = [string, () => void] | null;

function showMenu(x: number, y: number, items: MenuItem[]): void {
  const menu = $<HTMLUListElement>('menu');
  if (!items.length) { menu.hidden = true; return; }
  menu.replaceChildren(...items.map(it => {
    const li = document.createElement('li');
    if (!it) { li.className = 'sep'; return li; }
    li.textContent = it[0];
    li.onclick = () => { menu.hidden = true; it[1](); };
    return li;
  }));
  menu.hidden = false;
  menu.style.left = `${Math.min(x, innerWidth - 200)}px`;
  menu.style.top = `${Math.min(y, innerHeight - menu.offsetHeight - 8)}px`;
}
document.addEventListener('pointerdown', e => { if (!(e.target as HTMLElement).closest('#menu')) $('menu').hidden = true; });

function blockMenu(d: Details | null, x: number, y: number): void {
  const items: MenuItem[] = [];
  if (d) {
    if (d.module && d.target.kind === 'block') { const id = d.target.id; items.push([`Open Module ${d.module}`, () => engine.descend(id)]); }
    if (d.loc) items.push(['Open Source', () => openSource(d.loc!)]);
    if (d.target.kind === 'block' && d.kind.startsWith('area')) {
      const id = d.target.id;
      items.push([d.kind.includes('collapsed') ? 'Expand Area' : 'Collapse Area', () => engine.toggleArea(id)]);
    }
    const id = d.target.kind === 'block' ? d.target.id : null;
    const i = fsmEntries.findIndex(e => e.module === engine.module && id !== null && (e.fsm.node === id || e.fsm.node?.startsWith(id + '/')));
    if (i >= 0) items.push([`Show State Machine ${fsmEntries[i].fsm.name}`, () => setMode('fsm', i)]);
    items.push(null);
  }
  items.push(['Fit', () => engine.fit()]);
  if (engine.state.path.length) items.push(['Up', () => engine.up()]);
  showMenu(x, y, items);
}

// ---------------------------------------------------------------------------------------------
// Loading

async function load(bytes: ArrayBuffer, name: string): Promise<void> {
  status.textContent = `Loading ${name}…`;
  drop.hidden = true;
  try {
    const design = await loadDesign(bytes);
    stateKey = `spinalblocks.view.${design.top}`;
    const saved = JSON.parse(localStorage.getItem(stateKey) ?? 'null') as { state: ViewState; viewport: Viewport } | null;
    const fromHash = hashPath();
    // A link to an instance (#/tile/core) wins over the saved path.
    const state = saved?.state ?? (fromHash ? initialView() : undefined);
    if (state && fromHash) state.path = fromHash;
    await engine.setDesign(design, state, fromHash && saved && fromHash.join('/') !== saved.state.path.join('/') ? undefined : saved?.viewport);
    await fsms.setDesign(design);
    refreshFsmList();
    buildTree();
    syncToggles();
  } catch (e) {
    drop.hidden = false;
    status.textContent = `Could not load ${name}: ${(e as Error).message}`;
  }
}

function hashPath(): string[] | null {
  if (!location.hash.startsWith('#/')) return null;
  return location.hash.slice(2).split('/').filter(Boolean).map(decodeURIComponent);
}

window.addEventListener('popstate', () => {
  const p = hashPath() ?? [];
  if (engine.design && p.join('/') !== engine.state.path.join('/')) engine.navigate(p).catch(() => {});
});

$('open').onclick = () => $('file').click();
$<HTMLInputElement>('file').onchange = async e => {
  const f = (e.target as HTMLInputElement).files?.[0];
  if (f) await load(await f.arrayBuffer(), f.name);
};
canvas.addEventListener('dragover', e => { e.preventDefault(); drop.classList.add('over'); });
canvas.addEventListener('dragleave', () => drop.classList.remove('over'));
canvas.addEventListener('drop', async e => {
  e.preventDefault();
  drop.classList.remove('over');
  const f = e.dataTransfer?.files[0];
  if (f) await load(await f.arrayBuffer(), f.name);
});

const fileParam = new URLSearchParams(location.search).get('file');
if (fileParam) {
  fetch(fileParam).then(async r => {
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    await load(await r.arrayBuffer(), fileParam);
  }).catch(e => { status.textContent = `Could not fetch ${fileParam}: ${e.message}`; });
}

// ---------------------------------------------------------------------------------------------
// Breadcrumbs and hierarchy

function renderCrumbs(path: string[], modules: string[]): void {
  crumbs.replaceChildren();
  const add = (text: string, target: string[], last: boolean, mod: string) => {
    const a = document.createElement('a');
    a.textContent = text;
    a.onclick = () => engine.navigate(target);
    crumbs.append(a);
    if (last) {
      const m = document.createElement('span');
      m.className = 'mod';
      m.textContent = `: ${mod}`;
      crumbs.append(m);
    } else {
      const s = document.createElement('span');
      s.className = 'sep';
      s.textContent = '›';
      crumbs.append(s);
    }
  };
  add(engine.design!.top, [], path.length === 0, modules[0]);
  path.forEach((name, i) => add(name, path.slice(0, i + 1), i === path.length - 1, modules[i + 1]));
}

function buildTree(): void {
  const root = engine.hierarchy();
  tree.replaceChildren();
  if (root) tree.append(treeNode(root, true));
  markTree(engine.state.path);
}

function treeNode(n: HierarchyNode, open: boolean): HTMLElement {
  const label = document.createElement('span');
  label.append(n.name);
  const mod = document.createElement('span');
  mod.className = 'mod';
  mod.textContent = n.module;
  label.append(mod);
  label.dataset.path = n.path.join('/');
  label.onclick = e => { e.preventDefault(); engine.navigate(n.path); };
  if (!n.children.length) {
    const leaf = document.createElement('div');
    leaf.className = 'leaf';
    leaf.append(label);
    leaf.dataset.path = label.dataset.path;
    leaf.dataset.text = `${n.name} ${n.module}`.toLowerCase();
    return leaf;
  }
  const d = document.createElement('details');
  d.open = open;
  const s = document.createElement('summary');
  s.append(label);
  s.dataset.path = label.dataset.path;
  d.dataset.text = `${n.name} ${n.module}`.toLowerCase();
  d.append(s, ...n.children.map(c => treeNode(c, false)));
  return d;
}

function markTree(path: string[]): void {
  const key = path.join('/');
  for (const el of tree.querySelectorAll<HTMLElement>('.current')) el.classList.remove('current');
  const hit = tree.querySelector<HTMLElement>(`summary[data-path="${CSS.escape(key)}"], .leaf[data-path="${CSS.escape(key)}"]`);
  if (!hit) return;
  hit.classList.add('current');
  for (let p = hit.parentElement; p && p !== tree; p = p.parentElement) if (p instanceof HTMLDetailsElement) p.open = true;
  hit.scrollIntoView({ block: 'nearest' });
}

$<HTMLInputElement>('tree-filter').oninput = e => {
  const q = (e.target as HTMLInputElement).value.trim().toLowerCase();
  // Show an entry when it or a descendant matches.
  const visit = (el: HTMLElement): boolean => {
    const kids = [...el.children].filter((c): c is HTMLElement => c instanceof HTMLDetailsElement || c.classList.contains('leaf'));
    const childHit = kids.map(visit).some(Boolean);
    const self = !q || (el.dataset.text ?? '').includes(q);
    el.style.display = self || childHit ? '' : 'none';
    if (q && childHit && el instanceof HTMLDetailsElement) el.open = true;
    return self || childHit;
  };
  for (const c of tree.children) visit(c as HTMLElement);
};
$('toggle-tree').onclick = () => $('tree-panel').classList.toggle('hidden');

// ---------------------------------------------------------------------------------------------
// Toolbar

$('up').onclick = () => engine.up();
$('fit').onclick = () => (mode === 'fsm' ? fsms.fit() : engine.fit());
$('collapse').onclick = () => engine.setAllAreas(true);
$('expand').onclick = () => engine.setAllAreas(false);
$<HTMLInputElement>('labels').onchange = e => engine.setRenderOptions({ showEdgeLabels: (e.target as HTMLInputElement).checked });
$<HTMLInputElement>('control').onchange = e => engine.setOptions({ showControl: (e.target as HTMLInputElement).checked });
$<HTMLInputElement>('clocks').onchange = e => engine.setOptions({ showClocks: (e.target as HTMLInputElement).checked });
$<HTMLInputElement>('buses').onchange = e => engine.setOptions({ busThreshold: (e.target as HTMLInputElement).checked ? 3 : 0 });
function download(blob: Blob, name: string): void {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
const exportName = () => (mode === 'fsm' ? fsms.shown?.fsm.name : engine.module) ?? 'diagram';
$('export').onclick = () =>
  download(new Blob([mode === 'fsm' ? fsms.exportSvg() : engine.exportSvg()], { type: 'image/svg+xml' }), `${exportName()}.svg`);
$('export-png').onclick = async () => download(await (mode === 'fsm' ? fsms.exportPng(2) : engine.exportPng(2)), `${exportName()}.png`);

function syncToggles(): void {
  $<HTMLInputElement>('control').checked = engine.state.options.showControl;
  $<HTMLInputElement>('clocks').checked = engine.state.options.showClocks;
  $<HTMLInputElement>('buses').checked = engine.state.options.busThreshold > 0;
}

// ---------------------------------------------------------------------------------------------
// Search

let hits: SearchHit[] = [];
let active = 0;

search.oninput = () => {
  hits = engine.search(search.value, 100);
  active = 0;
  renderHits();
};
search.onkeydown = e => {
  if (e.key === 'ArrowDown') { active = Math.min(active + 1, hits.length - 1); renderHits(); e.preventDefault(); }
  else if (e.key === 'ArrowUp') { active = Math.max(active - 1, 0); renderHits(); e.preventDefault(); }
  else if (e.key === 'Enter' && hits[active]) pick(hits[active]);
  else if (e.key === 'Escape') { search.value = ''; hits = []; renderHits(); search.blur(); }
};

function renderHits(): void {
  hitsEl.hidden = hits.length === 0;
  hitsEl.replaceChildren(...hits.map((h, i) => {
    const li = document.createElement('li');
    if (i === active) li.className = 'active';
    const text = document.createElement('span');
    text.textContent = h.text;
    const kind = document.createElement('span');
    kind.className = 'kind';
    kind.textContent = h.kind;
    const ctx = document.createElement('span');
    ctx.className = 'ctx';
    ctx.textContent = h.context;
    li.append(text, kind, ctx);
    li.onmousedown = e => { e.preventDefault(); pick(h); };
    return li;
  }));
  hitsEl.querySelector('.active')?.scrollIntoView({ block: 'nearest' });
}

function pick(h: SearchHit): void {
  engine.reveal(h.target);
  engine.select(h.target);
}

document.addEventListener('keydown', e => {
  const typing = e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement;
  if ((e.metaKey || e.ctrlKey) && e.key === 'f') { e.preventDefault(); search.focus(); search.select(); }
  else if (typing) return;
  else if (e.key === 'Backspace') { e.preventDefault(); engine.up(); }
  else if (e.key === 'f') (mode === 'fsm' ? fsms.fit() : engine.fit());
  else if (e.key === 'Escape') engine.select(null);
});

// ---------------------------------------------------------------------------------------------
// Details panel

function showDetails(d: Details | null): void {
  details.hidden = !d;
  if (!d) return;
  details.replaceChildren();
  const h = document.createElement('h2');
  h.textContent = d.title;
  const sub = document.createElement('div');
  sub.className = 'sub';
  sub.textContent = `${d.kind} · ${d.subtitle}`;
  details.append(h, sub);

  const actions = document.createElement('div');
  actions.className = 'actions';
  if (d.loc) actions.append(button(`Source: ${d.loc.file.split('/').pop()}:${d.loc.line}`, () => openSource(d.loc!)));
  if (d.module && d.target.kind === 'block') actions.append(button(`Open ${d.module}`, () => engine.descend(d.target.kind === 'block' ? d.target.id : '')));
  details.append(actions);

  if (d.signals.length) section(`Signals (${d.signals.length})`, d.signals.slice(0, 500).map(s =>
    [locLink(s.name, s.loc), `${s.type}${s.width > 1 ? `[${s.width}]` : ''}`, s.reg ? 'reg' : '']));
  if (d.ports.length) section(`Ports (${d.ports.length})`, d.ports.slice(0, 500).map(p => [locLink(p.name, p.loc), p.dir, String(p.width)]));
  if (d.nets.length) section(`Nets (${d.nets.length})`, d.nets.slice(0, 500).map(n =>
    [n.name + (n.control ? ' (ctl)' : ''), `${n.from} → ${n.to.join(', ')}`, String(n.width)]));
}

function section(title: string, rows: (string | Node)[][]): void {
  const h = document.createElement('h3');
  h.textContent = title;
  const table = document.createElement('table');
  for (const r of rows) {
    const tr = table.insertRow();
    for (const c of r) tr.insertCell().append(c);
  }
  details.append(h, table);
}

function locLink(text: string, loc: Loc | null): string | Node {
  if (!loc || !sourceUrl(loc)) return text;
  const a = document.createElement('a');
  a.textContent = text;
  a.title = `${loc.file}:${loc.line}`;
  a.onclick = () => openSource(loc);
  return a;
}

function button(text: string, f: () => void): HTMLButtonElement {
  const b = document.createElement('button');
  b.textContent = text;
  b.onclick = f;
  return b;
}
