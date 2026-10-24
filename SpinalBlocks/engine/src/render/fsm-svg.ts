// SVG renderer for state machine diagrams (FsmScene), in Sigasi's style: a frame titled with the
// machine's name, states as ellipses, transitions as curved arrows with their conditions beside them.
// The reset state is entered by a dashed arrow from a dot; unresolved transitions are dashed arrows
// to a "?"; dead states have a red outline and unused states are red.

import type { FsmScene, FsmSceneState, FsmSceneTransition } from '../core/fsm.ts';
import type { Point } from '../core/scene.ts';
import type { FsmRenderer, FsmRendererEvents, FsmTarget, RenderOptions } from './types.ts';
import { fsmRules, fsmViewRules } from './svg.css.ts';
import type { Box, Tip } from './canvas.ts';
import { SvgCanvas, r } from './canvas.ts';

/** Height of the frame's title bar. */
const HEADER = 30;
/** Arrowhead length and half width. */
const ARROW = 9, ARROW_W = 4;

type Ellipse = { cx: number; cy: number; rx: number; ry: number };

const ellipseOf = (s: FsmSceneState): Ellipse => ({ cx: s.x + s.width / 2, cy: s.y + s.height / 2, rx: s.width / 2, ry: s.height / 2 });

const sub = (a: Point, b: Point): Point => ({ x: a.x - b.x, y: a.y - b.y });
const len = (p: Point) => Math.hypot(p.x, p.y);

/** Where the line through `p` along `d` crosses the ellipse: the entry point (`first`) or the exit point. */
export function onEllipse(p: Point, d: Point, e: Ellipse, first: boolean): Point | null {
  const n = len(d);
  if (n < 1e-6) return null;
  const ux = d.x / n, uy = d.y / n;
  // Solve ((px + t ux - cx)/rx)^2 + ((py + t uy - cy)/ry)^2 = 1 for t.
  const ox = (p.x - e.cx) / e.rx, oy = (p.y - e.cy) / e.ry;
  const vx = ux / e.rx, vy = uy / e.ry;
  const a = vx * vx + vy * vy, b = 2 * (ox * vx + oy * vy), c = ox * ox + oy * oy - 1;
  const disc = b * b - 4 * a * c;
  if (disc < 0) return null;
  const t = first ? (-b - Math.sqrt(disc)) / (2 * a) : (-b + Math.sqrt(disc)) / (2 * a);
  return { x: p.x + t * ux, y: p.y + t * uy };
}

/** Section points as an SVG path: cubic Béziers when the points come in ELK's spline form
 *  [start, c1, c2, end, c1, c2, end...], else a polyline. */
export function curvePath(pts: Point[]): string {
  if (!pts.length) return '';
  let d = `M${r(pts[0].x)} ${r(pts[0].y)}`;
  if (pts.length > 1 && (pts.length - 1) % 3 === 0) {
    for (let i = 1; i + 2 < pts.length; i += 3)
      d += `C${r(pts[i].x)} ${r(pts[i].y)} ${r(pts[i + 1].x)} ${r(pts[i + 1].y)} ${r(pts[i + 2].x)} ${r(pts[i + 2].y)}`;
  } else {
    for (let i = 1; i < pts.length; i++) d += `L${r(pts[i].x)} ${r(pts[i].y)}`;
  }
  return d;
}

/** Last point before `end` that differs from it (the direction the curve arrives from). */
function before(pts: Point[], i: number, step: -1 | 1): Point | null {
  for (let j = i + step; j >= 0 && j < pts.length; j += step) if (len(sub(pts[i], pts[j])) > 0.5) return pts[j];
  return null;
}

/** Moves the first and/or last point of a curve onto the state ellipses (ELK ends edges on the
 *  bounding box), dragging the neighbouring control point along. */
function clip(pts: Point[], from: Ellipse | null, to: Ellipse | null): Point[] {
  const out = pts.map(p => ({ ...p }));
  if (out.length < 2) return out;
  const move = (i: number, j: number, e: Ellipse, entering: boolean) => {
    const q = before(out, i, j > i ? 1 : -1);
    if (!q) return;
    // Direction of travel at the end point.
    const d = entering ? sub(out[i], q) : sub(q, out[i]);
    const hit = onEllipse(out[i], d, e, entering);
    if (!hit) return;
    const dx = hit.x - out[i].x, dy = hit.y - out[i].y;
    out[i] = hit;
    if (j !== i && j >= 0 && j < out.length && out.length > 2) out[j] = { x: out[j].x + dx, y: out[j].y + dy };
  };
  if (from) move(0, 1, from, false);
  if (to) move(out.length - 1, out.length - 2, to, true);
  return out;
}

/** Shortens a curve's end by the arrowhead and returns the head polygon. */
function arrowhead(pts: Point[]): { pts: Point[]; head: string } | null {
  const n = pts.length;
  if (n < 2) return null;
  const end = pts[n - 1];
  const q = before(pts, n - 1, -1);
  if (!q) return null;
  const d = sub(end, q), l = len(d);
  const ux = d.x / l, uy = d.y / l;
  const base = { x: end.x - ux * ARROW, y: end.y - uy * ARROW };
  const out = pts.map(p => ({ ...p }));
  // Pull the end (and its control point) back to the arrow's base so the line does not poke through the tip.
  const k = ARROW - 1;
  out[n - 1] = { x: end.x - ux * k, y: end.y - uy * k };
  if (n > 2) out[n - 2] = { x: out[n - 2].x - ux * k, y: out[n - 2].y - uy * k };
  const head = [end, { x: base.x - uy * ARROW_W, y: base.y + ux * ARROW_W }, { x: base.x + uy * ARROW_W, y: base.y - ux * ARROW_W }]
    .map(p => `${r(p.x)},${r(p.y)}`).join(' ');
  return { pts: out, head };
}

/** Points along the curve(s), sampled finely enough to measure distances and lengths. */
export function sampleCurve(pts: Point[]): Point[] {
  if (pts.length < 2 || (pts.length - 1) % 3 !== 0) return pts;
  const out = [pts[0]];
  for (let i = 0; i + 3 < pts.length; i += 3) {
    const [a, b, c, d] = [pts[i], pts[i + 1], pts[i + 2], pts[i + 3]];
    for (let k = 1; k <= 12; k++) {
      const t = k / 12, u = 1 - t;
      const w0 = u * u * u, w1 = 3 * u * u * t, w2 = 3 * u * t * t, w3 = t * t * t;
      out.push({ x: w0 * a.x + w1 * b.x + w2 * c.x + w3 * d.x, y: w0 * a.y + w1 * b.y + w2 * c.y + w3 * d.y });
    }
  }
  return out;
}

/** Where a transition's label goes: the layout's box when it is next to the curve; otherwise (ELK's
 *  spline routing does not always pass its label slots) beside the middle of the curve.
 *  `end` = the box is left of the curve, so its text is right-aligned against the curve (text is
 *  usually narrower than the layout's width estimate). */
export function labelSpot(t: FsmSceneTransition, width: number, height: number): (Point & { end: boolean }) | null {
  const pts = t.sections.flatMap(sampleCurve);
  if (!pts.length) return t.labelAt ? { ...t.labelAt, end: false } : null;
  if (t.labelAt) {
    const { x, y } = t.labelAt;
    let best: Point | null = null, bestD = Infinity;
    for (const p of pts) {
      const d = Math.max(x - p.x, 0, p.x - x - width) ** 2 + Math.max(y - p.y, 0, p.y - y - height) ** 2;
      if (d < bestD) { bestD = d; best = p; }
    }
    if (best && bestD <= 14 * 14) return { x, y, end: best.x >= x + width - 2 };
  }
  // Midpoint by length, and the direction there.
  let total = 0;
  for (let i = 1; i < pts.length; i++) total += len(sub(pts[i], pts[i - 1]));
  let i = 1;
  for (let run = 0; i < pts.length - 1; i++) {
    run += len(sub(pts[i], pts[i - 1]));
    if (run >= total / 2) break;
  }
  const p = pts[i], q = pts[i - 1] ?? p;
  const d = sub(p, q);
  // Mostly vertical: to the right of the curve; mostly horizontal: above it.
  return Math.abs(d.y) >= Math.abs(d.x)
    ? { x: p.x + 5, y: p.y - height / 2, end: false }
    : { x: p.x - width / 2, y: p.y - height - 3, end: false };
}

export class SvgFsmRenderer extends SvgCanvas<FsmTarget> implements FsmRenderer {
  private scene: FsmScene | null = null;
  private stateEls = new Map<string, Element>();
  private transitionEls = new Map<string, Element[]>();
  private pseudoEls = { any: null as Element | null, unknown: null as Element | null };
  private marked = { hl: [] as Element[], sel: [] as Element[] };
  private readonly events: FsmRendererEvents;

  constructor(container: HTMLElement, events: FsmRendererEvents, options: Partial<RenderOptions> = {}) {
    super(container, options, fsmViewRules());
    this.events = events;
  }

  // -------------------------------------------------------------------------------------------
  // FsmRenderer API

  render(scene: FsmScene, keepViewport: boolean): void {
    this.scene = scene;
    this.marked = { hl: [], sel: [] };
    const vp = this.el('g', { class: 'sb-vp' }) as SVGGElement;
    this.draw(scene, vp);
    this.showDrawing(vp, scene.metrics.fontFamily, keepViewport);
  }

  highlight(targets: FsmTarget[]): void {
    for (const e of this.marked.hl) e.classList.remove('sb-hl');
    const s = this.scene;
    const lit: Element[] = [];
    const states = new Set<string>();
    const transitions = new Set<string>();
    for (const t of targets) {
      if (t.kind === 'state') {
        states.add(t.name);
        for (const tr of s?.transitions ?? [])
          if (tr.transition.from === t.name || tr.transition.to === t.name) transitions.add(tr.id);
      } else {
        transitions.add(t.id);
      }
    }
    for (const id of transitions) {
      lit.push(...(this.transitionEls.get(id) ?? []));
      const tr = s?.transitions.find(x => x.id === id)?.transition;
      if (!tr) continue;
      if (tr.from) states.add(tr.from); else if (this.pseudoEls.any) lit.push(this.pseudoEls.any);
      if (tr.to) states.add(tr.to); else if (this.pseudoEls.unknown) lit.push(this.pseudoEls.unknown);
    }
    for (const n of states) { const e = this.stateEls.get(n); if (e) lit.push(e); }
    for (const e of lit) e.classList.add('sb-hl');
    this.marked.hl = lit;
    this.vp.classList.toggle('sb-dimming', targets.length > 0);
  }

  select(targets: FsmTarget[]): void {
    for (const e of this.marked.sel) e.classList.remove('sb-sel');
    this.marked.sel = targets.flatMap(t => this.elementsOf(t));
    for (const e of this.marked.sel) e.classList.add('sb-sel');
  }

  reveal(target: FsmTarget): void {
    const s = this.scene;
    if (!s) return;
    if (target.kind === 'state') {
      this.revealBox(s.states.find(x => x.name === target.name) ?? null);
    } else {
      const t = s.transitions.find(x => x.id === target.id);
      this.revealBox(t ? SvgCanvas.pointsBox(t.sections.flat()) : null);
    }
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
    return { x: -8, y: -HEADER - 8, width: s.width + 16, height: s.height + HEADER + 16 };
  }

  protected onSelect(t: FsmTarget | null): void { this.events.select(t); }
  protected onActivate(t: FsmTarget): void { this.events.activate(t); }
  protected onHover(t: FsmTarget | null): void { this.events.hover(t); }
  protected onContextMenu(t: FsmTarget | null, x: number, y: number): void { this.events.contextMenu(t, x, y); }
  protected exportRules(): string[] { return fsmRules(); }

  protected tooltipOf(t: FsmTarget): Tip | null {
    const s = this.scene;
    if (!s) return null;
    if (t.kind === 'state') {
      const st = s.states.find(x => x.name === t.name);
      if (!st) return null;
      const out = s.fsm.transitions.filter(x => x.from === st.name).length;
      const into = s.fsm.transitions.filter(x => x.to === st.name).length;
      const kind = st.unused ? 'unused state' : st.dead ? 'dead state (no way out)' : st.reset ? 'reset state' : 'state';
      return { title: st.name, lines: [kind, `${into} in · ${out} out`] };
    }
    const tr = s.transitions.find(x => x.id === t.id)?.transition;
    if (!tr) return null;
    const lines = [tr.condition ? `when ${tr.condition}` : 'always'];
    if (tr.comment) lines.push(`// ${tr.comment}`);
    if (tr.to === null) lines.push('target not a constant state');
    return { title: `${tr.from ?? 'any state'} → ${tr.to ?? '?'}`, lines };
  }

  targetOf(node: EventTarget | null): FsmTarget | null {
    const el = node instanceof Object && 'closest' in node ? (node as Element).closest('[data-t]') : null;
    if (!el || !this.svg.contains(el)) return null;
    switch (el.getAttribute('data-t')) {
      case 's': return { kind: 'state', name: el.getAttribute('data-id')! };
      case 't': return { kind: 'transition', id: el.getAttribute('data-id')! };
    }
    return null;
  }

  // -------------------------------------------------------------------------------------------
  // Drawing

  private draw(s: FsmScene, vp: Element): void {
    this.stateEls = new Map();
    this.transitionEls = new Map();
    this.pseudoEls = { any: null, unknown: null };
    const m = s.metrics;
    const ellipses = new Map(s.states.map(st => [st.name, ellipseOf(st)]));

    const frame = this.el('g', { class: 'sb-l-frame' });
    const lines = this.el('g', { class: 'sb-l-transitions' });
    const nodes = this.el('g', { class: 'sb-l-states' });
    const labels = this.el('g', { class: 'sb-l-labels' });

    // Frame with the machine's name in a title bar.
    frame.appendChild(this.el('rect', { class: 'sb-frame', x: 0, y: -HEADER, width: r(s.width), height: r(s.height + HEADER) }));
    frame.appendChild(this.el('rect', { class: 'sb-fhead', x: 0, y: -HEADER, width: r(s.width), height: HEADER }));
    frame.appendChild(this.text(s.width / 2, -HEADER / 2 + (m.titleSize + 2) * 0.36, m.titleSize + 2, 'sb-ftitle', s.fsm.name, 'middle'));

    // Reset: a dot and a dashed arrow into the reset state.
    if (s.resetFrom && s.resetArrow) {
      const g = this.el('g', { class: 'sb-reset' });
      const resetState = s.states.find(x => x.reset);
      const pts = clip(s.resetArrow, null, resetState ? ellipses.get(resetState.name)! : null);
      const a = arrowhead(pts);
      g.appendChild(this.el('circle', { cx: r(s.resetFrom.x), cy: r(s.resetFrom.y), r: 4.5 }));
      g.appendChild(this.el('path', { class: 'sb-tl', d: curvePath(a ? a.pts : pts) }));
      if (a) g.appendChild(this.el('polygon', { class: 'sb-ah', points: a.head }));
      lines.appendChild(g);
    }

    for (const t of s.transitions) {
      const els = this.drawTransition(t, ellipses);
      lines.appendChild(els[0]);
      const label = this.drawLabel(t, s);
      if (label) { labels.appendChild(label); els.push(label); }
      this.transitionEls.set(t.id, els);
    }

    if (s.any) {
      const b = s.any;
      const g = this.el('g', { class: 'sb-pseudo sb-any' });
      g.appendChild(this.el('rect', { x: r(b.x), y: r(b.y), width: r(b.width), height: r(b.height), rx: r(Math.min(8, b.height / 2)) }));
      g.appendChild(this.text(b.x + b.width / 2, b.y + b.height / 2 + m.sublabelSize * 0.36, m.sublabelSize, '', 'any', 'middle'));
      nodes.appendChild(g);
      this.pseudoEls.any = g;
    }
    if (s.unknown) {
      const b = s.unknown;
      const g = this.el('g', { class: 'sb-unknown' });
      g.appendChild(this.text(b.x + b.width / 2, b.y + b.height / 2 + 7, 20, '', '?', 'middle'));
      nodes.appendChild(g);
      this.pseudoEls.unknown = g;
    }

    for (const st of s.states) nodes.appendChild(this.drawState(st, s));
    vp.append(frame, lines, nodes, labels);
  }

  private drawState(st: FsmSceneState, s: FsmScene): Element {
    const m = s.metrics;
    const cls = ['sb-st'];
    if (st.reset) cls.push('sb-reset-state');
    if (st.dead) cls.push('sb-dead');
    if (st.unused) cls.push('sb-unused');
    const g = this.el('g', { class: cls.join(' '), 'data-t': 's', 'data-id': st.name });
    this.stateEls.set(st.name, g);
    const e = ellipseOf(st);
    g.appendChild(this.el('ellipse', { class: 'sb-shape', cx: r(e.cx), cy: r(e.cy), rx: r(e.rx), ry: r(e.ry) }));
    g.appendChild(this.text(e.cx, e.cy + m.titleSize * 0.36, m.titleSize, '', st.name, 'middle'));
    return g;
  }

  private drawTransition(t: FsmSceneTransition, ellipses: Map<string, Ellipse>): Element[] {
    const cls = ['sb-tr'];
    if (t.unresolved) cls.push('sb-unres');
    if (t.fromAny) cls.push('sb-from-any');
    const g = this.el('g', { class: cls.join(' '), 'data-t': 't', 'data-id': t.id });
    const from = t.transition.from ? ellipses.get(t.transition.from) ?? null : null;
    const to = t.transition.to ? ellipses.get(t.transition.to) ?? null : null;
    const n = t.sections.length;
    t.sections.forEach((sec, i) => {
      let pts = clip(sec, i === 0 ? from : null, i === n - 1 ? to : null);
      let head: string | null = null;
      if (i === n - 1) {
        const a = arrowhead(pts);
        if (a) { pts = a.pts; head = a.head; }
      }
      const d = curvePath(pts);
      g.appendChild(this.el('path', { class: 'sb-eh', d }));
      g.appendChild(this.el('path', { class: 'sb-tl', d }));
      if (head) g.appendChild(this.el('polygon', { class: 'sb-ah', points: head }));
    });
    return [g];
  }

  /** Condition lines, then comment lines (muted), at the layout's label box. */
  private drawLabel(t: FsmSceneTransition, s: FsmScene): Element | null {
    if (!t.label.length) return null;
    const m = s.metrics;
    const lineH = m.edgeLabelSize + 3;
    const width = Math.max(...t.label.map(l => l.length)) * m.edgeLabelSize * m.charWidth + 6;
    const height = t.label.length * lineH + 2;
    const at = labelSpot(t, width, height);
    if (!at) return null;
    const g = this.el('g', { class: 'sb-tlabel', 'data-t': 't', 'data-id': t.id });
    g.appendChild(this.el('rect', { class: 'sb-hit', x: r(at.x), y: r(at.y), width: r(width), height: r(height) }));
    let comment = false;
    t.label.forEach((line, i) => {
      if (line.startsWith('//')) comment = true;
      // SVG drops leading spaces, so wrapped lines are indented by position.
      const text = line.trimStart();
      const indent = (line.length - text.length) * m.edgeLabelSize * m.charWidth;
      const tx = at.end ? at.x + width - 3 : at.x + 3 + indent;
      g.appendChild(this.text(tx, at.y + (i + 1) * lineH - 2, m.edgeLabelSize, comment ? 'sb-cmt' : '', text, at.end ? 'end' : undefined));
    });
    return g;
  }

  private elementsOf(t: FsmTarget): Element[] {
    if (t.kind === 'transition') return this.transitionEls.get(t.id) ?? [];
    const e = this.stateEls.get(t.name);
    return e ? [e] : [];
  }
}
