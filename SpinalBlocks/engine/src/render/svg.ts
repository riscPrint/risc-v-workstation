// SVG renderer: draws a Scene as a Sigasi-style block diagram and turns pointer gestures into
// RendererEvents. The DOM is built once per render(); pan and zoom only change one transform.
//
// Conventions (Sigasi's): the module is a framed sheet with its name in a header bar; module ports
// are solid triangles on the frame (squares for inout); instances are solid rectangles with the
// instance name over the module name and small port triangles on their border; logic is rounded;
// expanded areas are dashed containers; wires are thin for single bits and thick for buses.

import type { Scene, SceneBlock, SceneBlockPort, SceneEdge, SceneModulePort, Point, Metrics } from '../core/scene.ts';
import { textWidth } from '../core/scene.ts';
import type { EndRef, VBlock, VEdge, VPort } from '../core/graph.ts';
import { portText } from '../core/layout.ts';
import type { Renderer, RendererEvents, RenderOptions, Target } from './types.ts';
import { diagramRules, viewRules } from './svg.css.ts';
import type { Box, Tip } from './canvas.ts';
import { SvgCanvas, r } from './canvas.ts';

/** Below these zoom levels edge labels, then port labels and sublabels, are hidden. */
const FAR_ZOOM = 0.55;
const FARTHER_ZOOM = 0.4;

/** Height of the module frame's title bar. */
const FRAME_HEADER = 24;

/** Stroke width of a wire: thin for one bit, thick for buses and merged nets (Sigasi draws two widths). */
export function edgeStroke(bits: number, nets = 1): number {
  return bits <= 1 && nets <= 1 ? 1 : 2.5;
}

/** Cuts `text` to at most `room` px with an ellipsis, using the metrics' width estimate. */
export function fitText(text: string, size: number, room: number, m: Metrics): string {
  const max = Math.floor(room / (size * m.charWidth));
  if (text.length <= max) return text;
  return max <= 1 ? '' : text.slice(0, max - 1) + '…';
}

/** Port marker centred at (x, y): a solid triangle pointing right (the direction of flow, since inputs
 *  sit on the left and outputs on the right), or a square for inout. `s` is the marker size. */
export function portShape(x: number, y: number, s: number, dir: VPort['dir']): string {
  const h = s / 2;
  const pts = dir === 'inout'
    ? [[x - h, y - h], [x + h, y - h], [x + h, y + h], [x - h, y + h]]
    : [[x - h, y - h], [x + h, y], [x - h, y + h]];
  return pts.map(([a, b]) => `${r(a)},${r(b)}`).join(' ');
}

/** Key of one end of an edge (module port: block = null). */
function endKey(block: string | null, port: string | null): string {
  return `${block ?? ''}\u0000${port ?? ''}`;
}

function pathOf(sections: Point[][]): string {
  return sections.map(s => s.map((p, i) => `${i ? 'L' : 'M'}${r(p.x)} ${r(p.y)}`).join('')).join('');
}

/** A comb block holding a single signal is a plain assignment (Sigasi draws these as "<=" blocks). */
function isAssignment(b: VBlock): boolean {
  return b.kind === 'comb' && !b.compound && !/\d+ signals$/.test(b.sublabel);
}

const bits = (n: number) => n === 1 ? '1 bit' : `${n} bits`;

/** Length of the horizontal run that starts at an edge's label anchor (labelSpot puts it 6 px in, 3 px up). */
function labelRoom(e: SceneEdge): number {
  const at = e.labelAt!;
  for (const s of e.sections) {
    for (let i = 0; i + 1 < s.length; i++) {
      const a = s[i], b = s[i + 1];
      if (Math.abs(a.y - b.y) < 0.5 && Math.abs(a.y - (at.y + 3)) < 0.5 && Math.abs(Math.min(a.x, b.x) + 6 - at.x) < 0.5)
        return Math.abs(b.x - a.x) - 12;
    }
  }
  return 200;
}

export class SvgRenderer extends SvgCanvas<Target> implements Renderer {
  private scene: Scene | null = null;
  private zoomClass = '';

  // Lookup tables, rebuilt by render().
  private blockEls = new Map<string, Element>();
  private modulePortEls = new Map<string, Element>();
  private blockPortEls = new Map<string, Element>();
  private edgeEls = new Map<string, Element[]>();
  private edgesAt = new Map<string, string[]>();
  private edgesOfBlock = new Map<string, string[]>();
  private childrenOf = new Map<string, string[]>();
  private sceneEdges = new Map<string, SceneEdge>();
  private sceneBlocks = new Map<string, SceneBlock>();
  private marked = { hl: [] as Element[], sel: [] as Element[] };

  private readonly events: RendererEvents;

  constructor(container: HTMLElement, events: RendererEvents, options: Partial<RenderOptions> = {}) {
    super(container, options, viewRules());
    this.events = events;
  }

  // -------------------------------------------------------------------------------------------
  // Renderer API

  render(scene: Scene, keepViewport: boolean): void {
    this.scene = scene;
    this.marked = { hl: [], sel: [] };
    this.index(scene);
    const vp = this.el('g', { class: 'sb-vp' }) as SVGGElement;
    this.draw(scene, vp);
    this.showDrawing(vp, scene.metrics.fontFamily, keepViewport);
  }

  highlight(targets: Target[]): void {
    for (const e of this.marked.hl) e.classList.remove('sb-hl');
    this.marked.hl = [];
    const edges = new Set<string>();
    const ends: Element[] = [];
    for (const t of targets) {
      ends.push(...this.elementsOf(t));
      switch (t.kind) {
        case 'block': for (const id of this.blockAndDescendants(t.id)) for (const e of this.edgesOfBlock.get(id) ?? []) edges.add(e); break;
        case 'modulePort': for (const e of this.edgesAt.get(endKey(null, t.id)) ?? []) edges.add(e); break;
        case 'blockPort': for (const e of this.edgesAt.get(endKey(t.block, t.port)) ?? []) edges.add(e); break;
        case 'edge': edges.add(t.id); break;
      }
    }
    for (const id of edges) {
      const se = this.sceneEdges.get(id);
      if (!se) continue;
      ends.push(...(this.edgeEls.get(id) ?? []), ...this.endElements(se.edge.source), ...this.endElements(se.edge.target));
    }
    for (const e of ends) e.classList.add('sb-hl');
    this.marked.hl = ends;
    this.vp.classList.toggle('sb-dimming', targets.length > 0);
  }

  select(targets: Target[]): void {
    for (const e of this.marked.sel) e.classList.remove('sb-sel');
    this.marked.sel = targets.flatMap(t => this.elementsOf(t));
    for (const e of this.marked.sel) e.classList.add('sb-sel');
  }

  reveal(target: Target): void {
    this.revealBox(this.boundsOf(target));
  }

  override dispose(): void {
    super.dispose();
    this.scene = null;
  }

  // -------------------------------------------------------------------------------------------
  // SvgCanvas hooks

  protected drawingBounds(): Box | null {
    const s = this.scene;
    if (!s) return null;
    const f = this.frameBox(s);
    const x0 = Math.min(0, f.x) - 8, x1 = Math.max(s.width, f.x + f.width) + 8;
    const y0 = f.y - FRAME_HEADER - 8, y1 = Math.max(s.height, f.y + f.height) + 8;
    return { x: x0, y: y0, width: x1 - x0, height: y1 - y0 };
  }

  protected onSelect(t: Target | null): void { this.events.select(t); }
  protected onActivate(t: Target): void { this.events.activate(t); }
  protected onHover(t: Target | null): void { this.events.hover(t); }
  protected onContextMenu(t: Target | null, x: number, y: number): void { this.events.contextMenu(t, x, y); }
  protected exportRules(): string[] { return diagramRules().filter(rule => !rule.includes('.sb-far')); }

  protected override onControl(el: Element): void {
    switch (el.getAttribute('data-act')) {
      case 'area': this.events.toggleArea(el.getAttribute('data-id')!); break;
      case 'open': this.events.open(el.getAttribute('data-id')!); break;
      default: this.events.toggleBundle(el.getAttribute('data-owner')!, el.getAttribute('data-p')!);
    }
  }

  protected override zoomChanged(zoom: number): void {
    if (zoom < FARTHER_ZOOM) {
      this.svg.style.setProperty('--sb-far-size', `${r(12 / zoom)}px`);
      this.svg.style.setProperty('--sb-far-halo', `${r(3 / zoom)}px`);
    }
    const cls = zoom < FARTHER_ZOOM ? 'far farther' : zoom < FAR_ZOOM ? 'far' : '';
    if (cls !== this.zoomClass) {
      this.zoomClass = cls;
      this.svg.classList.toggle('sb-far', zoom < FAR_ZOOM);
      this.svg.classList.toggle('sb-farther', zoom < FARTHER_ZOOM);
    }
  }

  protected tooltipOf(t: Target): Tip | null {
    const s = this.scene;
    if (!s) return null;
    const portLines = (p: VPort) => {
      const lines = [`${p.dir} · ${bits(p.width)}`];
      if (p.bundle) lines.push(`bundle of ${p.members.length} ports`, ...listed(p.members));
      return lines;
    };
    switch (t.kind) {
      case 'block': {
        const b = this.sceneBlocks.get(t.id)?.block;
        if (!b) return null;
        if (b.kind === 'instance') return { title: b.label, lines: [`instance of ${b.module ?? b.sublabel}`, `${b.ports.length} ports`] };
        if (b.kind === 'area') return { title: b.label, lines: [b.sublabel || 'area', b.collapsed ? 'collapsed area' : 'area'] };
        return { title: b.label, lines: [isAssignment(b) ? `assignment · ${b.sublabel.replace(/^[^·]*· /, '')}` : b.sublabel] };
      }
      case 'modulePort': {
        const p = s.ports.find(q => q.id === t.id)?.port;
        return p ? { title: p.label, lines: ['module port', ...portLines(p)] } : null;
      }
      case 'blockPort': {
        const sb = this.sceneBlocks.get(t.block);
        const p = sb?.ports.find(q => q.id === t.port)?.port;
        return sb && p ? { title: `${sb.block.label}.${p.label}`, lines: portLines(p) } : null;
      }
      case 'edge': {
        const e = this.sceneEdges.get(t.id)?.edge;
        if (!e) return null;
        const lines = [`${bits(e.width)}${e.nets.length > 1 ? ` · ${e.nets.length} nets` : ''}${e.clock ? ' · clock' : e.control ? ' · control' : ''}`];
        const names = netNames(e);
        if (names.length > 1 || (names.length === 1 && names[0] !== e.label)) lines.push(...listed(names));
        return { title: e.label, lines };
      }
    }
  }

  // -------------------------------------------------------------------------------------------
  // Drawing

  private index(s: Scene): void {
    this.sceneEdges = new Map(s.edges.map(e => [e.id, e]));
    this.sceneBlocks = new Map(s.blocks.map(b => [b.id, b]));
    this.edgesAt = new Map();
    this.edgesOfBlock = new Map();
    this.childrenOf = new Map();
    const push = (m: Map<string, string[]>, k: string, v: string) => { const l = m.get(k); if (l) l.push(v); else m.set(k, [v]); };
    for (const e of s.edges) {
      for (const end of [e.edge.source, e.edge.target]) {
        push(this.edgesAt, endKey(end.block, end.port), e.id);
        if (end.block !== null) push(this.edgesOfBlock, end.block, e.id);
      }
    }
    for (const b of s.blocks) if (b.block.parent) push(this.childrenOf, b.block.parent, b.id);
  }

  private draw(s: Scene, vp: Element): void {
    this.blockEls = new Map();
    this.modulePortEls = new Map();
    this.blockPortEls = new Map();
    this.edgeEls = new Map();
    const m = s.metrics;

    // Layers, back to front: frame, area containers, edges, edge labels, blocks, module ports.
    const frame = this.el('g', { class: 'sb-l-frame' });
    const areas = this.el('g', { class: 'sb-l-areas' });
    const edges = this.el('g', { class: 'sb-l-edges' });
    const labels = this.el('g', { class: 'sb-l-labels' });
    const blocks = this.el('g', { class: 'sb-l-blocks' });
    const ports = this.el('g', { class: 'sb-l-ports' });

    // The module: a framed sheet with a title bar, like Sigasi's.
    const f = this.frameBox(s);
    frame.appendChild(this.el('rect', { class: 'sb-frame', x: r(f.x), y: r(f.y - FRAME_HEADER), width: r(f.width), height: r(f.height + FRAME_HEADER) }));
    frame.appendChild(this.el('rect', { class: 'sb-fhead', x: r(f.x), y: r(f.y - FRAME_HEADER), width: r(f.width), height: FRAME_HEADER }));
    frame.appendChild(this.text(f.x + f.width / 2, f.y - FRAME_HEADER / 2 + m.titleSize * 0.36, m.titleSize, 'sb-ftitle',
      fitText(s.module, m.titleSize, f.width - 16, m), 'middle'));

    for (const b of s.blocks) (b.block.compound ? areas : blocks).appendChild(this.drawBlock(b, m));
    const placed = new LabelGrid();
    for (const e of s.edges) {
      const g = this.drawEdge(e);
      edges.appendChild(g);
      const els = [g];
      if (e.labelAt && e.edge.label) {
        const text = fitText(e.edge.label, m.edgeLabelSize, labelRoom(e), m);
        // Skip stubs cut down to a few letters and labels that would overlap one already drawn.
        const box = { x: e.labelAt.x, y: e.labelAt.y - m.edgeLabelSize, width: textWidth(text, m.edgeLabelSize, m), height: m.edgeLabelSize + 2 };
        if ((text === e.edge.label || text.length >= 8) && placed.add(box)) {
          const t = this.text(e.labelAt.x, e.labelAt.y - 1, m.edgeLabelSize, 'sb-elabel', text);
          labels.appendChild(t);
          els.push(t);
        }
      }
      this.edgeEls.set(e.id, els);
    }
    for (const p of s.ports) ports.appendChild(this.drawModulePort(p, f, m));
    vp.append(frame, areas, edges, labels, blocks, ports);
  }

  private drawBlock(sb: SceneBlock, m: Metrics): Element {
    const b = sb.block;
    const cls = ['sb-blk', b.kind === 'instance' ? 'sb-inst' : `sb-${b.kind}`];
    if (b.compound) cls.push('sb-compound'); else cls.push('sb-leaf');
    if (isAssignment(b)) cls.push('sb-assignment');
    const g = this.el('g', { class: cls.join(' '), 'data-t': 'b', 'data-id': b.id });
    this.blockEls.set(b.id, g);
    const { x, y, width: w, height: h } = sb;

    if (b.kind === 'instance') {
      // Solid rectangle, header with the instance name (bold) over the module name.
      const hh = m.headerHeight - 4;
      g.appendChild(this.el('rect', { class: 'sb-box', x, y, width: w, height: h }));
      g.appendChild(this.el('rect', { class: 'sb-head', x: r(x + 0.5), y: r(y + 0.5), width: r(w - 1), height: r(hh - 0.5) }));
      g.appendChild(this.el('path', { class: 'sb-sep', d: `M${r(x)} ${r(y + hh)}h${r(w)}` }));
      const room = w - 2 * 22;
      g.appendChild(this.text(x + w / 2, y + 15, m.titleSize, 'sb-title', fitText(b.label, m.titleSize, room, m), 'middle'));
      g.appendChild(this.text(x + w / 2, y + 29, m.sublabelSize, 'sb-sub', fitText(b.sublabel, m.sublabelSize, room, m), 'middle'));
      if (b.module) g.appendChild(this.openGlyph(b.id, x + w - 16, y + 5));
      for (const p of sb.ports) g.appendChild(this.drawBlockPort(sb, p, m));
      return g;
    }

    if (b.compound) {
      // Expanded area: dashed container with a collapse chevron.
      g.appendChild(this.el('rect', { class: 'sb-box', x, y, width: w, height: h, rx: 3 }));
      g.appendChild(this.chevron(b.id, x + 7, y + 8, true));
      g.appendChild(this.text(x + 22, y + 17, m.titleSize, 'sb-title', fitText(b.label, m.titleSize, w - 30, m)));
      const used = textWidth(b.label, m.titleSize, m) + 30;
      if (b.sublabel && w - used > 40) g.appendChild(this.text(x + used, y + 17, m.sublabelSize, 'sb-sub', fitText(b.sublabel, m.sublabelSize, w - used - 8, m)));
      return g;
    }

    // Collapsed areas are solid blocks (like modules); logic is rounded (like Sigasi's processes).
    const rounded = b.kind !== 'area';
    g.appendChild(this.el('rect', { class: 'sb-box', x, y, width: w, height: h, rx: rounded ? 8 : 1 }));
    let tx = x + 10;
    if (b.collapsible) { g.appendChild(this.chevron(b.id, x + 6, y + 8, false)); tx = x + 20; }
    let room = x + w - tx - 6;
    if (isAssignment(b)) {
      // Spinal's assignment operator in place of Sigasi's "<=".
      g.appendChild(this.text(tx, y + 21, m.titleSize + 3, 'sb-assign', ':='));
      tx += 24;
      room -= 24;
    }
    if (b.kind === 'mem') {
      // Memory: a small stack of words.
      const gx = x + w - 19, gy = y + 7;
      g.appendChild(this.el('path', { class: 'sb-glyph', d: `M${r(gx)} ${r(gy)}h12v13h-12zM${r(gx)} ${r(gy + 3.25)}h12M${r(gx)} ${r(gy + 6.5)}h12M${r(gx)} ${r(gy + 9.75)}h12` }));
      room -= 16;
    }
    if (b.kind === 'reg' || b.kind === 'mixed') {
      // Register: the clock-edge wedge of a flip-flop symbol, on the bottom-left edge.
      g.appendChild(this.el('path', { class: 'sb-glyph', d: `M${r(x)} ${r(y + h - 18)}l8 5l-8 5` }));
    }
    g.appendChild(this.text(tx, y + 19, m.titleSize, 'sb-title', fitText(b.label, m.titleSize, room, m)));
    const sub = isAssignment(b) ? b.sublabel.replace(/^[^·]*· /, '') : b.sublabel;
    g.appendChild(this.text(tx, y + 34, m.sublabelSize, 'sb-sub', fitText(sub, m.sublabelSize, x + w - tx - 6, m)));
    return g;
  }

  private drawBlockPort(sb: SceneBlock, p: SceneBlockPort, m: Metrics): Element {
    const vp = p.port;
    const left = p.side === 'left';
    const g = this.el('g', { class: `sb-bp sb-${vp.dir}`, 'data-t': 'bp', 'data-b': sb.id, 'data-p': p.id });
    this.blockPortEls.set(endKey(sb.id, p.id), g);
    const s = Math.max(6, m.portSize - 1), pitch = m.portPitch;
    // Hit area: the port's row on its half of the block plus the marker.
    g.appendChild(this.el('rect', { class: 'sb-hit', x: r(left ? p.x - s : sb.x + sb.width / 2), y: r(p.y - pitch / 2), width: r(sb.width / 2 + s), height: pitch }));
    // Solid triangle straddling the border, pointing along the flow (into the block on the left, out on the right).
    const cx = left ? p.x + s / 2 - 1 : p.x - s / 2 + 1;
    g.appendChild(this.el('polygon', { class: 'sb-mark', points: portShape(vp.dir === 'inout' ? p.x : cx, p.y, s, vp.dir) }));
    let inner = s + 3;
    const ctl = this.bundleControl(sb.id, vp);
    if (ctl) {
      const bx = left ? p.x + inner + 5 : p.x - inner - 5;
      ctl.setAttribute('transform', `translate(${r(bx)},${r(p.y)})`);
      g.appendChild(ctl);
      inner += 13;
    }
    const tx = left ? p.x + inner : p.x - inner;
    const room = sb.width / 2 - inner - 3;
    const label = fitText(portText(vp), m.portLabelSize, Math.max(room, sb.width - inner * 2 - 40), m);
    g.appendChild(this.text(tx, p.y + m.portLabelSize * 0.35, m.portLabelSize, '', label, left ? undefined : 'end'));
    return g;
  }

  /** Module port: a solid triangle on the frame edge, a stub wire to where the layout ends the net,
   *  and the name above the stub, next to the triangle (as Sigasi draws them). */
  private drawModulePort(p: SceneModulePort, f: Box, m: Metrics): Element {
    const vp = p.port;
    const g = this.el('g', { class: `sb-mp sb-${vp.dir}`, 'data-t': 'mp', 'data-id': p.id });
    this.modulePortEls.set(p.id, g);
    const left = p.side === 'left';
    const cy = p.y + p.height / 2;
    const s = 9;
    const edgeX = left ? f.x : f.x + f.width;
    // Inputs point into the sheet, outputs out of it; both sit across the frame line.
    const mx = vp.dir === 'inout' ? edgeX : edgeX + (left ? 1 : -1);
    const wireX = left ? p.x + p.width : p.x;
    const inner = left ? mx + s / 2 : mx - s / 2;
    g.appendChild(this.el('rect', { class: 'sb-hit', x: r(Math.min(edgeX, wireX) - s), y: r(p.y), width: r(Math.abs(wireX - edgeX) + 2 * s), height: r(p.height) }));
    g.appendChild(this.el('path', { class: 'sb-stub', d: `M${r(inner)} ${r(cy)}H${r(wireX)}`, 'stroke-width': edgeStroke(vp.width, vp.bundle ? 2 : 1) }));
    g.appendChild(this.el('polygon', { class: 'sb-pm', points: portShape(mx, cy, s, vp.dir) }));
    let tx = left ? inner + 4 : inner - 4;
    const ctl = this.bundleControl('', vp);
    if (ctl) {
      ctl.setAttribute('transform', `translate(${r(left ? tx + 6 : tx - 6)},${r(cy - 8)})`);
      g.appendChild(ctl);
      tx += left ? 15 : -15;
    }
    const room = Math.abs(wireX - tx) - 2;
    const label = fitText(portText(vp), m.portLabelSize, Math.max(room, 40), m);
    g.appendChild(this.text(tx, cy - 4, m.portLabelSize, '', label, left ? undefined : 'end'));
    return g;
  }

  /** +/- control for a folded bundle (+) or a member of an opened bundle (-), centred at (0,0). */
  private bundleControl(owner: string, vp: VPort): Element | null {
    if (!vp.bundle && !vp.expandable) return null;
    const g = this.el('g', { class: 'sb-ctl', 'data-act': 'bundle', 'data-owner': owner, 'data-p': vp.id });
    g.appendChild(this.el('rect', { class: 'sb-hit', x: -7, y: -7, width: 14, height: 14 }));
    g.appendChild(this.el('rect', { x: -4.5, y: -4.5, width: 9, height: 9, rx: 1 }));
    g.appendChild(this.el('path', { d: vp.bundle ? 'M-2.5 0h5M0 -2.5v5' : 'M-2.5 0h5' }));
    return g;
  }

  /** Area chevron: down when expanded, right when collapsed; (x, y) is the top-left of a 10x10 box. */
  private chevron(id: string, x: number, y: number, expanded: boolean): Element {
    const g = this.el('g', { class: 'sb-ctl', 'data-act': 'area', 'data-id': id, transform: `translate(${r(x)},${r(y)})` });
    g.appendChild(this.el('rect', { class: 'sb-hit', x: -3, y: -3, width: 16, height: 16 }));
    g.appendChild(this.el('path', { class: 'sb-chev', d: expanded ? 'M1 3h8l-4 5z' : 'M3 1v8l5-4z' }));
    return g;
  }

  /** "Open module" button in an instance header: a box with an arrow going into it; (x, y) is its top-left. */
  private openGlyph(id: string, x: number, y: number): Element {
    const g = this.el('g', { class: 'sb-ctl sb-open', 'data-act': 'open', 'data-id': id, transform: `translate(${r(x)},${r(y)})` });
    g.appendChild(this.el('rect', { class: 'sb-hit', x: -3, y: -3, width: 17, height: 17 }));
    g.appendChild(this.el('rect', { x: 0.5, y: 0.5, width: 10, height: 10, rx: 1.5 }));
    g.appendChild(this.el('path', { d: 'M3 3l4.5 4.5M7.5 4v3.5H4' }));
    const t = this.el('title', {}, 'Open module');
    g.appendChild(t);
    return g;
  }

  private drawEdge(e: SceneEdge): Element {
    const v = e.edge;
    const cls = ['sb-e'];
    if (v.control) cls.push('sb-ctrl');
    if (v.clock) cls.push('sb-clk');
    const sw = edgeStroke(v.width, v.nets.length);
    if (sw > 1) cls.push('sb-bus');
    const g = this.el('g', { class: cls.join(' '), 'data-t': 'e', 'data-id': e.id });
    const d = pathOf(this.snapEnds(e));
    g.appendChild(this.el('path', { class: 'sb-eh', d }));
    g.appendChild(this.el('path', { class: 'sb-el', d, 'stroke-width': sw }));
    for (const j of e.junctions) g.appendChild(this.el('circle', { class: 'sb-jn', cx: r(j.x), cy: r(j.y), r: r(sw + 1.5) }));
    return g;
  }

  /** ELK ends edges on the outer side of the port box; extend them to the port point on the block border. */
  private snapEnds(e: SceneEdge): Point[][] {
    if (!e.sections.length) return e.sections;
    const at = (end: EndRef): Point | null => {
      if (end.block === null || end.port === null) return null;
      const p = this.sceneBlocks.get(end.block)?.ports.find(q => q.id === end.port);
      return p ? { x: p.x, y: p.y } : null;
    };
    const sections = e.sections.map(s => s.slice());
    const first = sections[0], last = sections[sections.length - 1];
    const src = at(e.edge.source), dst = at(e.edge.target);
    if (src && first.length && Math.abs(first[0].y - src.y) < 0.5 && first[0].x !== src.x) first.unshift(src);
    if (dst && last.length && Math.abs(last[last.length - 1].y - dst.y) < 0.5 && last[last.length - 1].x !== dst.x) last.push(dst);
    return sections;
  }

  // -------------------------------------------------------------------------------------------
  // Geometry

  /** Body of the module frame (title bar above it). The frame's left and right lines run through the
   *  outer ends of the module ports, where their triangles sit. */
  private frameBox(s: Scene): Box {
    const lefts = s.ports.filter(p => p.side === 'left').map(p => p.x);
    const rights = s.ports.filter(p => p.side === 'right').map(p => p.x + p.width);
    const x0 = Math.min(16, ...lefts) - 2;
    const x1 = Math.max(s.width - 16, ...rights) + 2;
    return { x: x0, y: 8, width: x1 - x0, height: s.height - 16 };
  }

  private boundsOf(t: Target): Box | null {
    const s = this.scene;
    if (!s) return null;
    switch (t.kind) {
      case 'block': return this.sceneBlocks.get(t.id) ?? null;
      case 'modulePort': return s.ports.find(p => p.id === t.id) ?? null;
      case 'blockPort': {
        const p = this.sceneBlocks.get(t.block)?.ports.find(q => q.id === t.port);
        return p ? { x: p.x - 10, y: p.y - 10, width: 20, height: 20 } : this.sceneBlocks.get(t.block) ?? null;
      }
      case 'edge': return SvgCanvas.pointsBox(this.sceneEdges.get(t.id)?.sections.flat() ?? []);
    }
  }

  // -------------------------------------------------------------------------------------------
  // Targets

  private elementsOf(t: Target): Element[] {
    let e: Element | undefined;
    switch (t.kind) {
      case 'block': e = this.blockEls.get(t.id); break;
      case 'modulePort': e = this.modulePortEls.get(t.id); break;
      case 'blockPort': e = this.blockPortEls.get(endKey(t.block, t.port)); break;
      case 'edge': return this.edgeEls.get(t.id) ?? [];
    }
    return e ? [e] : [];
  }

  private endElements(end: EndRef): Element[] {
    const out: Element[] = [];
    if (end.block === null) {
      if (end.port) { const e = this.modulePortEls.get(end.port); if (e) out.push(e); }
      return out;
    }
    const b = this.blockEls.get(end.block);
    if (b) out.push(b);
    if (end.port) { const p = this.blockPortEls.get(endKey(end.block, end.port)); if (p) out.push(p); }
    return out;
  }

  private blockAndDescendants(id: string): string[] {
    const out = [id];
    for (let i = 0; i < out.length; i++) out.push(...(this.childrenOf.get(out[i]) ?? []));
    return out;
  }

  /** The target under a DOM node, from the data attributes set while drawing. */
  targetOf(node: EventTarget | null): Target | null {
    const el = node instanceof Object && 'closest' in node ? (node as Element).closest('[data-t]') : null;
    if (!el || !this.svg.contains(el)) return null;
    switch (el.getAttribute('data-t')) {
      case 'b': return { kind: 'block', id: el.getAttribute('data-id')! };
      case 'mp': return { kind: 'modulePort', id: el.getAttribute('data-id')! };
      case 'bp': return { kind: 'blockPort', block: el.getAttribute('data-b')!, port: el.getAttribute('data-p')! };
      case 'e': return { kind: 'edge', id: el.getAttribute('data-id')! };
    }
    return null;
  }
}

/** Net names of an edge when the view graph provides them, else its net ids. */
function netNames(e: VEdge): string[] {
  const names = (e as VEdge & { netNames?: string[] }).netNames;
  return names ?? (e.nets.length > 1 ? [] : [e.label]);
}

/** At most a dozen names, then a count of the rest. */
function listed(names: string[]): string[] {
  const max = 12;
  return names.length <= max ? names.map(n => `  ${n}`) : [...names.slice(0, max).map(n => `  ${n}`), `  … ${names.length - max} more`];
}

/** Boxes already placed, bucketed on a coarse grid for quick overlap tests. */
class LabelGrid {
  private cells = new Map<string, Box[]>();
  private static readonly SIZE = 128;

  /** Adds the box unless it overlaps one already added. */
  add(b: Box): boolean {
    const keys: string[] = [];
    const n = LabelGrid.SIZE;
    for (let i = Math.floor(b.x / n); i <= Math.floor((b.x + b.width) / n); i++)
      for (let j = Math.floor(b.y / n); j <= Math.floor((b.y + b.height) / n); j++) keys.push(`${i},${j}`);
    for (const k of keys) for (const o of this.cells.get(k) ?? [])
      if (b.x < o.x + o.width && o.x < b.x + b.width && b.y < o.y + o.height && o.y < b.y + b.height) return false;
    for (const k of keys) { const l = this.cells.get(k); if (l) l.push(b); else this.cells.set(k, [b]); }
    return true;
  }
}
