// State machine diagrams for hosts: one Fsm at a time, drawn by an FsmRenderer.

import type { Design, Fsm, FsmTransition, Loc } from './core/model.ts';
import { loadDesign } from './core/model.ts';
import type { LayoutEngine } from './core/layout.ts';
import type { FsmOptions, FsmScene } from './core/fsm.ts';
import { defaultFsmOptions, layoutFsm } from './core/fsm.ts';
import { instancePaths } from './core/locate.ts';
import type { FsmRenderer, FsmRendererEvents, FsmTarget, RenderOptions, Viewport } from './render/types.ts';

export interface FsmHost {
  openSource(loc: Loc): void;
  selectionChanged?(details: FsmDetails | null): void;
  contextMenu?(details: FsmDetails | null, clientX: number, clientY: number): void;
  busy?(busy: boolean): void;
  error?(error: Error): void;
}

export interface FsmDetails {
  target: FsmTarget;
  title: string;
  /** "state", "reset state", "dead state", "unused state", "transition". */
  kind: string;
  loc: Loc | null;
  /** For states: transitions in and out. For transitions: itself. */
  transitions: FsmTransition[];
}

/** A state machine somewhere in the design, for pickers. */
export interface FsmEntry {
  module: string;
  fsm: Fsm;
  /** Instance path of the first instance of the module, or null if unused. */
  path: string[] | null;
}

export interface FsmViewOptions {
  layout: LayoutEngine;
  renderer: (container: HTMLElement, events: FsmRendererEvents) => FsmRenderer;
}

export class FsmView {
  private readonly host: FsmHost;
  private readonly options: FsmViewOptions;
  private readonly renderer: FsmRenderer;
  private designValue: Design | null = null;
  private current: { module: string; fsm: Fsm } | null = null;
  private fsmOptions: FsmOptions = { ...defaultFsmOptions };
  private scene: FsmScene | null = null;
  private generation = 0;

  constructor(container: HTMLElement, host: FsmHost, options: FsmViewOptions) {
    this.host = host;
    this.options = options;
    this.renderer = options.renderer(container, {
      select: t => {
        this.renderer.select(t ? [t] : []);
        this.renderer.highlight(t ? [t] : []);
        this.host.selectionChanged?.(t ? this.describe(t) : null);
      },
      hover: t => this.renderer.highlight(t ? [t] : []),
      activate: t => { const loc = this.describe(t)?.loc; if (loc) this.host.openSource(loc); },
      contextMenu: (t, x, y) => this.host.contextMenu?.(t ? this.describe(t) : null, x, y),
    });
  }

  async setDesign(input: Design | string | Uint8Array | ArrayBuffer | unknown): Promise<void> {
    this.designValue = await loadDesign(input);
    // Keep showing the same machine after a reload when it still exists.
    if (this.current) {
      const again = this.designValue.modules[this.current.module]?.fsms?.find(f => f.id === this.current!.fsm.id);
      this.current = again ? { module: this.current.module, fsm: again } : null;
      if (this.current) await this.refresh(true);
    }
  }

  /** Every state machine in the design. */
  list(): FsmEntry[] {
    const d = this.designValue;
    if (!d) return [];
    return Object.values(d.modules).flatMap(m => (m.fsms ?? []).map(fsm => ({
      module: m.name, fsm, path: instancePaths(d, m.name, 1)[0] ?? null,
    })));
  }

  /** State machines declared in a Scala file (for "Open State Machines Diagram" on the current editor). */
  inFile(file: string): FsmEntry[] {
    return this.list().filter(e => e.fsm.loc && (e.fsm.loc.file === file || e.fsm.loc.file.endsWith('/' + file) || file.endsWith('/' + e.fsm.loc.file)));
  }

  async show(module: string, fsmId: string): Promise<void> {
    const fsm = this.designValue?.modules[module]?.fsms?.find(f => f.id === fsmId);
    if (!fsm) throw new Error(`no state machine ${fsmId} in ${module}`);
    this.current = { module, fsm };
    await this.refresh(false);
  }

  get shown(): { module: string; fsm: Fsm } | null { return this.current; }
  get currentScene(): FsmScene | null { return this.scene; }

  async setOptions(options: Partial<FsmOptions>): Promise<void> {
    this.fsmOptions = { ...this.fsmOptions, ...options };
    await this.refresh(true);
  }
  get fsmOptionsValue(): FsmOptions { return this.fsmOptions; }

  setRenderOptions(options: Partial<RenderOptions>): void { this.renderer.setOptions(options); }

  /** Select the state or transition declared at a source line, if it belongs to the shown machine. */
  showLocation(file: string, line: number): boolean {
    const f = this.current?.fsm;
    if (!f) return false;
    const at = (l: Loc | null) => !!l && l.line === line && (l.file === file || l.file.endsWith('/' + file) || file.endsWith('/' + l.file));
    const s = f.states.find(x => at(x.loc));
    const i = f.transitions.findIndex(t => at(t.loc));
    const target: FsmTarget | null = i >= 0 ? { kind: 'transition', id: `t${i}` } : s ? { kind: 'state', name: s.name } : null;
    if (!target) return false;
    this.renderer.reveal(target);
    this.renderer.select([target]);
    this.renderer.highlight([target]);
    return true;
  }

  describe(t: FsmTarget): FsmDetails | null {
    const sc = this.scene;
    if (!sc) return null;
    if (t.kind === 'transition') {
      const tr = sc.transitions.find(x => x.id === t.id);
      if (!tr) return null;
      const x = tr.transition;
      return { target: t, title: `${x.from ?? 'any state'} → ${x.to ?? '?'}`, kind: 'transition', loc: x.loc, transitions: [x] };
    }
    const st = sc.states.find(x => x.name === t.name);
    if (!st) return null;
    const kind = st.unused ? 'unused state' : st.dead ? 'dead state' : st.reset ? 'reset state' : 'state';
    return { target: t, title: st.name, kind, loc: st.loc,
      transitions: sc.fsm.transitions.filter(x => x.from === st.name || x.to === st.name) };
  }

  fit(): void { this.renderer.fit(); }
  exportSvg(): string { return this.renderer.exportSvg(); }
  exportPng(scale = 2): Promise<Blob> { return this.renderer.exportPng(scale); }
  get viewport(): Viewport { return this.renderer.getViewport(); }
  dispose(): void { this.generation++; this.renderer.dispose(); }

  private async refresh(keepViewport: boolean): Promise<void> {
    if (!this.current) return;
    const gen = ++this.generation;
    this.host.busy?.(true);
    try {
      const scene = await layoutFsm(this.current.fsm, this.options.layout, this.fsmOptions);
      if (gen !== this.generation) return;
      this.scene = scene;
      this.renderer.render(scene, keepViewport);
    } catch (e) {
      this.host.error?.(e instanceof Error ? e : new Error(String(e)));
    } finally {
      if (gen === this.generation) this.host.busy?.(false);
    }
  }
}
