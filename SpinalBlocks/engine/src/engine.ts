// The engine a host embeds: holds the design and the view state, runs graph building and layout,
// drives a renderer, and talks to the host only through the Host interface. Hosts own everything
// around the diagram (panels, menus, file access, opening editors).

import type { Design, Loc, Net, Port, Signal } from './core/model.ts';
import { loadDesign, ModuleIndex, resolvePath } from './core/model.ts';
import type { ViewOptions, ViewState } from './core/view.ts';
import { initialView, moduleView, updateModuleView } from './core/view.ts';
import type { VPort, ViewGraph } from './core/graph.ts';
import { buildViewGraph, collapsedAreas } from './core/graph.ts';
import type { LayoutEngine } from './core/layout.ts';
import type { LocationHit } from './core/locate.ts';
import { instancePaths, locate, modulesDefinedIn } from './core/locate.ts';
import { layoutGraph } from './core/layout.ts';
import type { Metrics, Scene } from './core/scene.ts';
import { defaultMetrics } from './core/scene.ts';
import type { Renderer, RendererEvents, RenderOptions, Target, Viewport } from './render/types.ts';

/** What the engine asks of its host. Only `openSource` is required. */
export interface Host {
  /** Open a Scala source location (editor, new tab, `vscode.window.showTextDocument`...). */
  openSource(loc: Loc): void;
  /** The view changed (navigation, collapse, options, viewport); persist it if you like. */
  stateChanged?(state: ViewState, viewport: Viewport): void;
  /** A different module is shown. `path` = instance names from the top, `modules` = module names along it. */
  navigated?(path: string[], modules: string[]): void;
  selectionChanged?(details: Details | null): void;
  hoverChanged?(details: Details | null): void;
  contextMenu?(details: Details | null, clientX: number, clientY: number): void;
  /** Layout is running (large modules take a second or two). */
  busy?(busy: boolean): void;
  error?(error: Error): void;
}

export interface EngineOptions {
  /** ELK instance (`new ELK()` or a worker-backed one): the host decides where layout runs. */
  layout: LayoutEngine;
  /** Renderer factory; the default SVG renderer is wired up by `createEngine` in index.ts. */
  renderer: (container: HTMLElement, events: RendererEvents) => Renderer;
  metrics?: Metrics;
  /** Extra ELK options merged into the root graph. */
  elkOptions?: Record<string, string>;
  /** Double click on an instance: open its source (Sigasi's convention, default) or go inside it.
   *  The instance's open glyph and `descend()` always go inside. */
  doubleClick?: 'source' | 'descend';
}

/** A row in the instance hierarchy. */
export interface HierarchyNode {
  name: string;
  module: string;
  path: string[];
  children: HierarchyNode[];
}

/** Everything a host may want to show about a target (details panel, tooltip, quick pick). */
export interface Details {
  target: Target;
  kind: string;
  title: string;
  subtitle: string;
  loc: Loc | null;
  /** Module to descend into (instances). */
  module: string | null;
  /** Signals of a logic block. */
  signals: Signal[];
  /** Real ports behind a (bundle) port. */
  ports: Port[];
  /** Nets touching the target. */
  nets: NetInfo[];
}

export interface NetInfo {
  id: string;
  name: string;
  width: number;
  from: string;
  to: string[];
  via: string[];
  control: boolean;
  clock: boolean;
}

export interface SearchHit {
  /** What matched: block/port label, or a signal/net name inside a block. */
  text: string;
  kind: string;
  target: Target;
  /** For matches inside a block: the block it is drawn in. */
  context: string;
}

export class BlockDiagramEngine {
  private readonly host: Host;
  private readonly options: EngineOptions;
  private readonly renderer: Renderer;
  private readonly metrics: Metrics;
  private designValue: Design | null = null;
  private stateValue: ViewState = initialView();
  private graph: ViewGraph | null = null;
  private scene: Scene | null = null;
  private generation = 0;
  private selected: Target | null = null;

  constructor(container: HTMLElement, host: Host, options: EngineOptions) {
    this.host = host;
    this.options = options;
    this.metrics = options.metrics ?? defaultMetrics;
    this.renderer = options.renderer(container, {
      select: t => this.onSelect(t),
      hover: t => {
        this.renderer.highlight(t ? [t] : this.selected ? [this.selected] : []);
        this.host.hoverChanged?.(t ? this.describe(t) : null);
      },
      activate: t => void this.activate(t),
      toggleArea: id => void this.toggleArea(id),
      toggleBundle: (owner, portId) => void this.toggleBundleByPort(owner, portId),
      contextMenu: (t, x, y) => this.host.contextMenu?.(t ? this.describe(t) : null, x, y),
      open: id => void this.descend(id),
    });
  }

  get design(): Design | null { return this.designValue; }
  get state(): ViewState { return this.stateValue; }
  get currentScene(): Scene | null { return this.scene; }
  /** Module names from the top to the shown module. */
  get modulePath(): string[] {
    return (this.designValue && resolvePath(this.designValue, this.stateValue.path)) ?? [];
  }
  get module(): string | null { return this.modulePath.at(-1) ?? null; }

  /** Loads a design (object, JSON text, or the gzip+base64 wrapper) and shows it. An invalid saved
   *  state (path no longer exists) falls back to the top. */
  async setDesign(input: Design | string | unknown, state?: ViewState, viewport?: Viewport): Promise<void> {
    this.designValue = await loadDesign(input);
    const s = state ?? initialView();
    this.stateValue = resolvePath(this.designValue, s.path) ? s : { ...s, path: [] };
    this.selected = null;
    await this.refresh(false);
    if (viewport) this.renderer.setViewport(viewport);
    this.notifyNavigated();
  }

  // ---- navigation ----

  async navigate(path: string[]): Promise<void> {
    if (!this.designValue || !resolvePath(this.designValue, path)) throw new Error(`no instance path ${path.join('/')}`);
    this.stateValue = { ...this.stateValue, path: [...path] };
    this.selected = null;
    await this.refresh(false);
    this.notifyNavigated();
  }

  async descend(instanceId: string): Promise<void> {
    const mod = this.module;
    if (!this.designValue || !mod) return;
    const inst = this.designValue.modules[mod].instances.find(i => i.id === instanceId || i.name === instanceId);
    if (inst) await this.navigate([...this.stateValue.path, inst.name]);
  }

  async up(): Promise<void> {
    if (this.stateValue.path.length) await this.navigate(this.stateValue.path.slice(0, -1));
  }

  // ---- view changes ----

  async setOptions(options: Partial<ViewOptions>): Promise<void> {
    this.stateValue = { ...this.stateValue, options: { ...this.stateValue.options, ...options } };
    await this.refresh(true);
  }

  setRenderOptions(options: Partial<RenderOptions>): void {
    this.renderer.setOptions(options);
  }

  /** Collapse or expand an area (toggles when `collapsed` is omitted). */
  async toggleArea(areaId: string, collapsed?: boolean): Promise<void> {
    const mod = this.module;
    if (!mod || !this.designValue) return;
    const now = this.isCollapsed(areaId);
    this.stateValue = updateModuleView(this.stateValue, mod, v => ({ ...v, areas: { ...v.areas, [areaId]: collapsed ?? !now } }));
    await this.refresh(true);
  }

  async setAllAreas(collapsed: boolean): Promise<void> {
    const mod = this.module;
    if (!mod || !this.designValue) return;
    const areas: Record<string, boolean> = {};
    for (const n of new ModuleIndex(this.designValue, mod).nodeList) if (n.compound) areas[n.id] = collapsed;
    this.stateValue = updateModuleView(this.stateValue, mod, v => ({ ...v, areas }));
    await this.refresh(false);
  }

  /** Open or close a port bundle. owner = "" for the module's own ports, else the instance id. */
  async toggleBundle(owner: string, bundle: string, open?: boolean): Promise<void> {
    const mod = this.module;
    if (!mod) return;
    const key = `${owner}|${bundle}`;
    const now = this.isBundleOpen(owner, bundle);
    this.stateValue = updateModuleView(this.stateValue, mod, v => ({ ...v, bundles: { ...v.bundles, [key]: open ?? !now } }));
    await this.refresh(true);
  }

  // ---- queries ----

  hierarchy(): HierarchyNode | null {
    const d = this.designValue;
    if (!d) return null;
    const build = (name: string, module: string, path: string[], depth: number): HierarchyNode => ({
      name, module, path,
      children: depth > 64 ? [] : (d.modules[module]?.instances ?? []).map(i => build(i.name, i.module, [...path, i.name], depth + 1)),
    });
    return build(d.top, d.top, [], 0);
  }

  /** Searches the shown module: blocks, ports, instance ports, signals inside blocks, nets. */
  search(query: string, limit = 200): SearchHit[] {
    const g = this.graph, d = this.designValue, mod = this.module;
    if (!g || !d || !mod || !query.trim()) return [];
    const q = query.trim().toLowerCase();
    const hits: SearchHit[] = [];
    const add = (h: SearchHit) => { if (hits.length < limit) hits.push(h); };
    const idx = new ModuleIndex(d, mod);
    const shownBlock = this.visibleBlockOf(idx);
    for (const b of g.blocks) if (b.label.toLowerCase().includes(q)) add({ text: b.label, kind: b.kind, target: { kind: 'block', id: b.id }, context: b.sublabel });
    for (const p of g.ports) if (p.members.some(n => n.toLowerCase().includes(q))) add({ text: p.label, kind: 'port', target: { kind: 'modulePort', id: p.id }, context: mod });
    for (const b of g.blocks) for (const p of b.ports)
      if (p.members.some(n => n.toLowerCase().includes(q))) add({ text: `${b.label}.${p.label}`, kind: 'instance port', target: { kind: 'blockPort', block: b.id, port: p.id }, context: b.sublabel });
    for (const n of idx.nodeList) for (const s of n.signals)
      if (s.name.toLowerCase().includes(q)) add({ text: s.name, kind: s.reg ? 'register' : 'signal', target: { kind: 'block', id: shownBlock(n.id) }, context: n.name });
    for (const e of g.edges) {
      const names = e.nets.map(id => idx.nets.get(id)!.name);
      const hit = names.find(n => n.toLowerCase().includes(q));
      if (hit) add({ text: hit, kind: 'net', target: { kind: 'edge', id: e.id }, context: e.label });
    }
    return hits;
  }

  /** Details for a target in the shown module. */
  describe(target: Target): Details | null {
    const g = this.graph, d = this.designValue, mod = this.module;
    if (!g || !d || !mod) return null;
    const idx = new ModuleIndex(d, mod);
    const netInfo = (n: Net): NetInfo => ({
      id: n.id, name: n.name, width: n.width, via: n.via, control: n.control, clock: n.clock,
      from: endpointText(idx, n.from), to: n.to.map(t => endpointText(idx, t)),
    });
    const edgesOf = (pred: (e: ViewGraph['edges'][number]) => boolean) =>
      [...new Set(g.edges.filter(pred).flatMap(e => e.nets))].map(id => netInfo(idx.nets.get(id)!));
    const base = { target, signals: [] as Signal[], ports: [] as Port[], module: null as string | null };

    switch (target.kind) {
      case 'block': {
        const b = g.blocks.find(x => x.id === target.id);
        if (!b) return null;
        const nets = edgesOf(e => e.source.block === b.id || e.target.block === b.id);
        if (b.kind === 'instance') {
          const inst = idx.instances.get(b.id)!;
          return { ...base, kind: 'instance', title: inst.name, subtitle: inst.module, loc: inst.loc, module: inst.module,
            ports: d.modules[inst.module]?.ports ?? [], nets };
        }
        const n = idx.nodes.get(b.id)!;
        // A collapsed area lists the signals of everything inside it.
        const inside = (id: string): Signal[] => [...(idx.nodes.get(id)?.signals ?? []), ...(idx.children.get(id) ?? []).flatMap(inside)];
        return { ...base, kind: b.collapsed ? 'area (collapsed)' : n.kind, title: n.name, subtitle: b.sublabel, loc: n.loc,
          signals: b.collapsed ? inside(n.id) : n.signals, nets };
      }
      case 'modulePort': {
        const p = g.ports.find(x => x.id === target.id);
        if (!p) return null;
        return { ...base, kind: p.bundle ? 'port bundle' : `${p.dir} port`, title: p.label, subtitle: `${p.dir} · ${p.width} bit`,
          loc: p.loc, ports: p.members.map(n => idx.ports.get(n)!).filter(Boolean),
          nets: edgesOf(e => (e.source.block === null && e.source.port === p.id) || (e.target.block === null && e.target.port === p.id)) };
      }
      case 'blockPort': {
        const b = g.blocks.find(x => x.id === target.block);
        const p = b?.ports.find(x => x.id === target.port);
        if (!b || !p) return null;
        const childPorts = new Map((d.modules[b.module ?? '']?.ports ?? []).map(x => [x.name, x]));
        return { ...base, kind: p.bundle ? 'port bundle' : `${p.dir} port`, title: `${b.label}.${p.label}`, subtitle: `${p.dir} · ${p.width} bit`,
          loc: p.loc, module: b.module, ports: p.members.map(n => childPorts.get(n)!).filter(Boolean),
          nets: edgesOf(e => (e.source.block === b.id && e.source.port === p.id) || (e.target.block === b.id && e.target.port === p.id)) };
      }
      case 'edge': {
        const e = g.edges.find(x => x.id === target.id);
        if (!e) return null;
        const nets = e.nets.map(id => netInfo(idx.nets.get(id)!));
        return { ...base, kind: nets.length > 1 ? 'bundle of nets' : 'net', title: e.label, subtitle: `${e.width} bit${nets.length > 1 ? ` · ${nets.length} nets` : ''}`,
          loc: null, nets };
      }
    }
  }

  // ---- viewport ----

  reveal(target: Target): void { this.renderer.reveal(target); }
  select(target: Target | null): void { this.onSelect(target); }
  fit(): void { this.renderer.fit(); }
  exportSvg(): string { return this.renderer.exportSvg(); }
  exportPng(scale = 2): Promise<Blob> { return this.renderer.exportPng(scale); }

  // ---- source locations ----

  /** Elements at a source line, across the design (see core/locate.ts). */
  locate(file: string, line: number): LocationHit[] {
    return this.designValue ? locate(this.designValue, file, line) : [];
  }

  /** "Show in Block Diagram": go to the module that declares what is at `file:line` (staying in the current
   *  instance path when it already shows that module), then select and centre it. Returns false when
   *  nothing in the design is declared there. */
  async showLocation(file: string, line: number): Promise<boolean> {
    const d = this.designValue;
    if (!d) return false;
    const hits = this.locate(file, line).filter(h => h.kind !== 'fsm' && h.kind !== 'state' && h.kind !== 'transition');
    if (!hits.length) return false;
    // Prefer the shown module, then the shallowest instance of another one.
    const here = hits.find(h => h.module === this.module);
    let hit = here ?? hits[0];
    if (!here) {
      let best: string[] | null = null;
      for (const h of hits) {
        const p = instancePaths(d, h.module, 1)[0];
        if (p && (!best || p.length < best.length)) { best = p; hit = h; }
      }
      if (!best) return false;
      await this.navigate(best);
    }
    if (hit.kind === 'module') { this.fit(); return true; }
    const target = this.targetForHit(hit);
    if (!target) return true;
    // A signal inside a collapsed area: open the area chain so the signal's block shows.
    this.reveal(target);
    this.select(target);
    return true;
  }

  /** Modules defined in a Scala file and the instance path of their first instance. */
  modulesIn(file: string): { module: string; path: string[] | null }[] {
    const d = this.designValue;
    if (!d) return [];
    return modulesDefinedIn(d, file).map(module => ({ module, path: instancePaths(d, module, 1)[0] ?? null }));
  }

  private targetForHit(hit: LocationHit): Target | null {
    const g = this.graph, d = this.designValue;
    if (!g || !d) return null;
    switch (hit.kind) {
      case 'port': {
        const p = g.ports.find(x => x.members.includes(hit.id));
        return p ? { kind: 'modulePort', id: p.id } : null;
      }
      case 'instance':
      case 'node':
      case 'signal': {
        const shown = this.visibleBlockOf(new ModuleIndex(d, hit.module))(hit.id);
        return g.blocks.some(b => b.id === shown) ? { kind: 'block', id: shown } : null;
      }
      default:
        return null;
    }
  }
  get viewport(): Viewport { return this.renderer.getViewport(); }
  dispose(): void { this.generation++; this.renderer.dispose(); }

  // ---- internals ----

  private isCollapsed(areaId: string): boolean {
    const mod = this.module!;
    const idx = new ModuleIndex(this.designValue!, mod);
    return collapsedAreas(idx, moduleView(this.stateValue, mod), this.stateValue.options.maxBlocks).has(areaId);
  }

  private isBundleOpen(owner: string, bundle: string): boolean {
    // Open when no visible port of that owner is the folded bundle itself.
    const g = this.graph;
    if (!g) return false;
    const ports: VPort[] = owner === '' ? g.ports : g.blocks.find(b => b.id === owner)?.ports ?? [];
    return !ports.some(p => p.bundle === bundle);
  }

  private async toggleBundleByPort(owner: string, portId: string): Promise<void> {
    const g = this.graph, d = this.designValue;
    if (!g || !d) return;
    const ports = owner === '' ? g.ports : g.blocks.find(b => b.id === owner)?.ports ?? [];
    const p = ports.find(x => x.id === portId);
    if (!p) return;
    if (p.bundle) return this.toggleBundle(owner, p.bundle, true);
    // A member of an opened bundle: close its innermost bundle.
    const real = owner === '' ? d.modules[this.module!].ports : d.modules[g.blocks.find(b => b.id === owner)?.module ?? '']?.ports ?? [];
    const group = real.find(x => x.name === p.members[0])?.groups.at(-1);
    if (group) await this.toggleBundle(owner, group, false);
  }

  private visibleBlockOf(idx: ModuleIndex): (id: string) => string {
    const shown = new Set(this.graph!.blocks.map(b => b.id));
    return id => shown.has(id) ? id : idx.ancestors(id).reverse().find(a => shown.has(a)) ?? id;
  }

  private onSelect(target: Target | null): void {
    this.selected = target;
    this.renderer.select(target ? [target] : []);
    this.renderer.highlight(target ? [target] : []);
    this.host.selectionChanged?.(target ? this.describe(target) : null);
  }

  private async activate(t: Target): Promise<void> {
    const details = this.describe(t);
    if (t.kind === 'block') {
      const b = this.graph?.blocks.find(x => x.id === t.id);
      if (b?.kind === 'instance' && this.options.doubleClick === 'descend') return this.descend(b.id);
      if (b?.collapsible && !b.loc) return this.toggleArea(b.id);
    }
    if (t.kind === 'blockPort' || t.kind === 'modulePort') {
      const owner = t.kind === 'blockPort' ? t.block : '';
      const id = t.kind === 'blockPort' ? t.port : t.id;
      const ports = owner === '' ? this.graph?.ports : this.graph?.blocks.find(b => b.id === owner)?.ports;
      if (ports?.find(p => p.id === id)?.bundle) return this.toggleBundleByPort(owner, id);
    }
    if (details?.loc) this.host.openSource(details.loc);
  }

  /** Rebuilds graph + layout for the current state. Later calls win over slower earlier ones. */
  private async refresh(keepViewport: boolean): Promise<void> {
    const d = this.designValue, mod = this.module;
    if (!d || !mod) return;
    const gen = ++this.generation;
    this.host.busy?.(true);
    try {
      const graph = buildViewGraph(d, mod, moduleView(this.stateValue, mod), this.stateValue.options);
      const scene = await layoutGraph(graph, this.options.layout, this.metrics, this.options.elkOptions);
      if (gen !== this.generation) return;
      this.graph = graph;
      this.scene = scene;
      this.renderer.render(scene, keepViewport);
      if (this.selected && this.describe(this.selected)) {
        this.renderer.select([this.selected]);
        this.renderer.highlight([this.selected]);
      } else this.selected = null;
      this.host.stateChanged?.(this.stateValue, this.renderer.getViewport());
    } catch (e) {
      this.host.error?.(e instanceof Error ? e : new Error(String(e)));
    } finally {
      if (gen === this.generation) this.host.busy?.(false);
    }
  }

  private notifyNavigated(): void {
    this.host.navigated?.(this.stateValue.path, this.modulePath);
  }
}

function endpointText(idx: ModuleIndex, e: Net['from']): string {
  switch (e.kind) {
    case 'port': return e.port;
    case 'inst': return `${idx.instances.get(e.id)?.name ?? e.id}.${e.port}`;
    case 'node': return idx.nodes.get(e.id)?.name ?? e.id;
  }
}
