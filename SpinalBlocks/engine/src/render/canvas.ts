// Shared base of the SVG renderers (block diagrams and state machines): the root element and its
// stylesheet, pan and zoom, pointer gestures, the hover tooltip, and SVG/PNG export.
// Subclasses draw into a fresh viewport group and map DOM nodes back to their own targets.

import type { RenderOptions, Viewport } from './types.ts';
import { themeVars } from './svg.css.ts';

export const NS = 'http://www.w3.org/2000/svg';
export const MIN_ZOOM = 0.02;
export const MAX_ZOOM = 4;

/** Wait before the hover tooltip shows (ms). */
const TIP_DELAY = 350;
/** PNG export stays under the canvas limits of common browsers. */
const MAX_CANVAS_SIDE = 16384;
const MAX_CANVAS_AREA = 1.2e8;

export interface Box { x: number; y: number; width: number; height: number }

/** Rounds to 0.1 px to keep the SVG small. */
export const r = (n: number) => Math.round(n * 10) / 10;

export function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v));
}

/** Fills a style element through the CSSOM (allowed by strict CSPs such as VS Code webviews'),
 *  or as text where there is no CSSOM (DOM shims). */
export function installRules(style: HTMLStyleElement, rules: string[]): void {
  const sheet = style.sheet;
  if (sheet && typeof sheet.insertRule === 'function') {
    for (const rule of rules) {
      try { sheet.insertRule(rule, sheet.cssRules.length); } catch { /* rule unsupported by this engine */ }
    }
  } else {
    style.textContent = rules.join('\n');
  }
}

function cancelFrame(id: number): void {
  if (typeof cancelAnimationFrame !== 'undefined') cancelAnimationFrame(id);
}

/** Tooltip content: a bold title and plain lines below it. */
export interface Tip { title: string; lines: string[] }

export abstract class SvgCanvas<T> {
  protected readonly doc: Document;
  protected readonly root: HTMLElement;
  protected readonly svg: SVGSVGElement;
  protected vp: SVGGElement;
  protected options: RenderOptions;
  protected view: Viewport = { x: 0, y: 0, zoom: 1 };
  private readonly tip: HTMLElement;
  private frame = 0;
  private pendingFit = false;
  private drag: { id: number; x: number; y: number; vx: number; vy: number; moved: boolean } | null = null;
  private suppressClick = false;
  private hoverKey: string | null = null;
  private tipTimer: ReturnType<typeof setTimeout> | null = null;
  private pointer = { x: 0, y: 0 };
  private readonly cleanup: (() => void)[] = [];
  private resizeObserver: ResizeObserver | null = null;

  constructor(container: HTMLElement, options: Partial<RenderOptions>, rules: string[]) {
    this.options = { showEdgeLabels: true, theme: 'light', ...options };
    this.doc = container.ownerDocument;
    this.root = this.doc.createElement('div');
    this.root.className = 'sb-root';
    const style = this.doc.createElement('style');
    this.root.appendChild(style);
    this.svg = this.el('svg', { class: 'sb-svg', tabindex: '-1' }) as SVGSVGElement;
    this.vp = this.el('g', { class: 'sb-vp' }) as SVGGElement;
    this.svg.appendChild(this.vp);
    this.root.appendChild(this.svg);
    this.tip = this.doc.createElement('div');
    this.tip.className = 'sb-tip';
    this.root.appendChild(this.tip);
    container.appendChild(this.root);
    installRules(style, rules);
    this.applyOptions();
    this.listen();
  }

  // -------------------------------------------------------------------------------------------
  // What subclasses provide

  /** Area of the whole drawing (for fit and export), or null when nothing is drawn. */
  protected abstract drawingBounds(): Box | null;
  /** The target under a DOM node. */
  protected abstract targetOf(node: EventTarget | null): T | null;
  protected abstract onSelect(t: T | null): void;
  protected abstract onActivate(t: T): void;
  protected abstract onHover(t: T | null): void;
  protected abstract onContextMenu(t: T | null, clientX: number, clientY: number): void;
  protected abstract tooltipOf(t: T): Tip | null;
  /** Stylesheet embedded in exported SVGs (rules starting with `.sb-svg`). */
  protected abstract exportRules(): string[];
  /** A click on a `[data-act]` control. */
  protected onControl(_el: Element): void { /* no controls by default */ }
  /** Called whenever the zoom is applied. */
  protected zoomChanged(_zoom: number): void { /* nothing by default */ }

  // -------------------------------------------------------------------------------------------
  // Shared renderer API

  setOptions(options: Partial<RenderOptions>): void {
    this.options = { ...this.options, ...options };
    this.applyOptions();
  }

  fit(): void {
    const b = this.drawingBounds();
    const { width, height } = this.size();
    if (!b || width <= 0 || height <= 0) { this.pendingFit = !!b; return; }
    this.pendingFit = false;
    const zoom = clamp(Math.min(width / b.width, height / b.height) * 0.96, MIN_ZOOM, 1);
    this.view = { zoom, x: (width - b.width * zoom) / 2 - b.x * zoom, y: (height - b.height * zoom) / 2 - b.y * zoom };
    this.applyView(true);
  }

  getViewport(): Viewport {
    return { ...this.view };
  }

  setViewport(v: Viewport): void {
    this.pendingFit = false;
    this.view = { x: v.x, y: v.y, zoom: clamp(v.zoom, MIN_ZOOM, MAX_ZOOM) };
    this.applyView(true);
  }

  exportSvg(): string {
    const out = this.exportElement(1);
    const xml = typeof XMLSerializer !== 'undefined' ? new XMLSerializer().serializeToString(out) : out.outerHTML;
    return `<?xml version="1.0" encoding="UTF-8"?>\n${xml}\n`;
  }

  async exportPng(scale = 2): Promise<Blob> {
    const b = this.drawingBounds() ?? { x: 0, y: 0, width: 1, height: 1 };
    const k = Math.max(0.01, Math.min(scale, MAX_CANVAS_SIDE / b.width, MAX_CANVAS_SIDE / b.height,
      Math.sqrt(MAX_CANVAS_AREA / (b.width * b.height))));
    const out = this.exportElement(k);
    const xml = new XMLSerializer().serializeToString(out);
    const img = new Image();
    // A data URL rather than a blob URL: webview CSPs usually allow `img-src data:`.
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(xml);
    await img.decode();
    const canvas = this.doc.createElement('canvas');
    canvas.width = Math.ceil(b.width * k);
    canvas.height = Math.ceil(b.height * k);
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('PNG export: no 2D canvas');
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    return new Promise((resolve, reject) =>
      canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error('PNG export failed')), 'image/png'));
  }

  dispose(): void {
    if (this.frame) cancelFrame(this.frame);
    this.hideTip();
    for (const f of this.cleanup) f();
    this.cleanup.length = 0;
    this.resizeObserver?.disconnect();
    this.root.remove();
  }

  // -------------------------------------------------------------------------------------------
  // Helpers for subclasses

  protected el(tag: string, attrs: Record<string, string | number> = {}, text?: string): Element {
    const e = this.doc.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, String(attrs[k]));
    if (text !== undefined) e.textContent = text;
    return e;
  }

  protected text(x: number, y: number, size: number, cls: string, s: string, anchor?: 'middle' | 'end'): Element {
    const a: Record<string, string | number> = { x: r(x), y: r(y), 'font-size': size };
    if (cls) a['class'] = cls;
    if (anchor) a['text-anchor'] = anchor;
    return this.el('text', a, s);
  }

  /** Swaps in a freshly drawn viewport group, then keeps the view or fits. */
  protected showDrawing(vp: SVGGElement, fontFamily: string, keepViewport: boolean): void {
    this.hoverKey = null;
    this.hideTip();
    this.svg.replaceChild(vp, this.vp);
    this.vp = vp;
    this.svg.setAttribute('font-family', fontFamily);
    if (keepViewport) this.applyView(true);
    else this.fit();
  }

  /** Pans and zooms so the box is centred and visible. */
  protected revealBox(b: Box | null): void {
    const { width, height } = this.size();
    if (!b || width <= 0 || height <= 0) return;
    const fitZoom = Math.min(width / (b.width + 80), height / (b.height + 80));
    const zoom = clamp(Math.min(fitZoom, Math.max(this.view.zoom, 0.8)), MIN_ZOOM, MAX_ZOOM);
    const cx = b.x + b.width / 2, cy = b.y + b.height / 2;
    this.view = { zoom, x: width / 2 - cx * zoom, y: height / 2 - cy * zoom };
    this.applyView(true);
  }

  /** Box around a list of points. */
  protected static pointsBox(pts: { x: number; y: number }[]): Box | null {
    if (!pts.length) return null;
    const xs = pts.map(p => p.x), ys = pts.map(p => p.y);
    const x = Math.min(...xs), y = Math.min(...ys);
    return { x, y, width: Math.max(...xs) - x, height: Math.max(...ys) - y };
  }

  // -------------------------------------------------------------------------------------------
  // Internals

  private size(): { width: number; height: number } {
    return { width: this.svg.clientWidth || 0, height: this.svg.clientHeight || 0 };
  }

  private applyOptions(): void {
    this.root.classList.toggle('sb-dark', this.options.theme === 'dark');
    this.svg.classList.toggle('sb-nolabels', !this.options.showEdgeLabels);
  }

  /** Applies the viewport on the next frame (or now). */
  private applyView(now = false): void {
    const run = () => {
      this.frame = 0;
      const { x, y, zoom } = this.view;
      this.vp.setAttribute('transform', `translate(${r(x)},${r(y)}) scale(${Math.round(zoom * 10000) / 10000})`);
      this.zoomChanged(zoom);
    };
    if (now || typeof requestAnimationFrame === 'undefined') {
      if (this.frame) { cancelFrame(this.frame); this.frame = 0; }
      run();
    } else if (!this.frame) {
      this.frame = requestAnimationFrame(run);
    }
  }

  private zoomAt(sx: number, sy: number, factor: number): void {
    const v = this.view;
    const zoom = clamp(v.zoom * factor, MIN_ZOOM, MAX_ZOOM);
    const k = zoom / v.zoom;
    this.view = { zoom, x: sx - (sx - v.x) * k, y: sy - (sy - v.y) * k };
    this.applyView();
  }

  /** Theme colours as plain values (host overrides included), for exported files. */
  private resolvedColours(): Record<string, string> {
    const dark = this.options.theme === 'dark' ? 1 : 0;
    const cs = typeof getComputedStyle === 'function' ? getComputedStyle(this.root) : null;
    const out: Record<string, string> = {};
    for (const [k, d] of Object.entries(themeVars)) {
      const got = cs?.getPropertyValue(`--_sb-${k}`).trim() ?? '';
      out[k] = got && !got.includes('var(') ? got : d[dark];
    }
    return out;
  }

  /** A standalone copy of the drawing: no interaction parts, colours resolved, `scale` x scene size. */
  private exportElement(scale: number): SVGSVGElement {
    const b = this.drawingBounds() ?? { x: 0, y: 0, width: 0, height: 0 };
    const out = this.svg.cloneNode(true) as SVGSVGElement;
    out.removeAttribute('tabindex');
    out.removeAttribute('style');
    out.setAttribute('class', this.options.showEdgeLabels ? 'sb-svg' : 'sb-svg sb-nolabels');
    out.setAttribute('xmlns', NS);
    out.setAttribute('viewBox', `${r(b.x)} ${r(b.y)} ${r(b.width)} ${r(b.height)}`);
    out.setAttribute('width', String(Math.ceil(b.width * scale)));
    out.setAttribute('height', String(Math.ceil(b.height * scale)));
    const vp = out.querySelector('.sb-vp');
    if (vp) { vp.removeAttribute('transform'); vp.setAttribute('class', 'sb-vp'); }
    for (const e of Array.from(out.querySelectorAll('.sb-eh, .sb-hit, .sb-ctl'))) e.remove();
    for (const e of Array.from(out.querySelectorAll('.sb-hl, .sb-sel'))) e.classList.remove('sb-hl', 'sb-sel');
    for (const e of Array.from(out.querySelectorAll('[data-t]'))) {
      for (const a of ['data-t', 'data-id', 'data-b', 'data-p']) e.removeAttribute(a);
    }
    const colours = this.resolvedColours();
    const css = this.exportRules().join('\n').replace(/var\(--_sb-([a-z-]+)\)/g, (_, k: string) => colours[k] ?? '#000');
    const style = this.doc.createElementNS(NS, 'style');
    style.textContent = css;
    const bg = this.el('rect', { x: r(b.x), y: r(b.y), width: r(b.width), height: r(b.height), fill: colours['bg'] });
    out.insertBefore(bg, out.firstChild);
    out.insertBefore(style, out.firstChild);
    return out;
  }

  // Tooltip -------------------------------------------------------------------------------------

  private scheduleTip(t: T | null): void {
    this.hideTip();
    if (!t || typeof setTimeout === 'undefined') return;
    this.tipTimer = setTimeout(() => {
      this.tipTimer = null;
      const tip = this.tooltipOf(t);
      if (tip) this.showTip(tip);
    }, TIP_DELAY);
  }

  private showTip(tip: Tip): void {
    const el = this.tip;
    el.textContent = '';
    const title = this.doc.createElement('div');
    title.className = 'sb-tip-title';
    title.textContent = tip.title;
    el.appendChild(title);
    for (const line of tip.lines) {
      const d = this.doc.createElement('div');
      d.textContent = line;
      el.appendChild(d);
    }
    el.classList.add('sb-on');
    // Below-right of the pointer, flipped to stay inside the view.
    const box = this.root.getBoundingClientRect?.();
    const w = el.offsetWidth || 0, h = el.offsetHeight || 0;
    const vw = box?.width || 0, vh = box?.height || 0;
    let x = this.pointer.x + 14, y = this.pointer.y + 16;
    if (vw && x + w > vw - 4) x = Math.max(4, this.pointer.x - w - 10);
    if (vh && y + h > vh - 4) y = Math.max(4, this.pointer.y - h - 10);
    el.style.left = `${Math.round(x)}px`;
    el.style.top = `${Math.round(y)}px`;
  }

  private hideTip(): void {
    if (this.tipTimer !== null) { clearTimeout(this.tipTimer); this.tipTimer = null; }
    this.tip.classList.remove('sb-on');
  }

  // Events (delegated on the svg) -----------------------------------------------------------

  private listen(): void {
    const svg = this.svg;
    const on = <K extends keyof SVGElementEventMap>(type: K, f: (e: SVGElementEventMap[K]) => void, opts?: AddEventListenerOptions) => {
      svg.addEventListener(type, f as EventListener, opts);
      this.cleanup.push(() => svg.removeEventListener(type, f as EventListener, opts));
    };
    const local = (e: { clientX: number; clientY: number }) => {
      const b = svg.getBoundingClientRect();
      return { x: e.clientX - b.left, y: e.clientY - b.top };
    };
    const controlOf = (node: EventTarget | null): Element | null => {
      const el = node instanceof Object && 'closest' in node ? (node as Element).closest('[data-act]') : null;
      return el && svg.contains(el) ? el : null;
    };

    on('pointerdown', e => {
      this.hideTip();
      if (e.button !== 0 && e.button !== 1) return;
      this.suppressClick = false;
      this.drag = { id: e.pointerId, x: e.clientX, y: e.clientY, vx: this.view.x, vy: this.view.y, moved: false };
    });
    on('pointermove', e => {
      if (typeof e.clientX === 'number') this.pointer = local(e);
      const d = this.drag;
      if (!d || d.id !== e.pointerId) return;
      const dx = e.clientX - d.x, dy = e.clientY - d.y;
      if (!d.moved) {
        if (Math.abs(dx) + Math.abs(dy) < 4) return;
        d.moved = true;
        // Capture only once dragging, so plain clicks keep their real target.
        svg.setPointerCapture?.(e.pointerId);
        svg.classList.add('sb-panning');
      }
      this.view = { ...this.view, x: d.vx + dx, y: d.vy + dy };
      this.applyView();
    });
    const end = (e: PointerEvent) => {
      const d = this.drag;
      if (!d || d.id !== e.pointerId) return;
      if (d.moved) {
        this.suppressClick = true;
        svg.classList.remove('sb-panning');
        if (svg.hasPointerCapture?.(e.pointerId)) svg.releasePointerCapture(e.pointerId);
      }
      this.drag = null;
    };
    on('pointerup', end);
    on('pointercancel', end);

    on('wheel', e => {
      e.preventDefault();
      this.hideTip();
      const p = local(e);
      const unit = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? 400 : 1;
      const dx = e.deltaX * unit, dy = e.deltaY * unit;
      // Pinch (ctrlKey on macOS trackpads) and mouse wheels zoom; trackpad scrolling pans.
      const mouseWheel = e.deltaMode !== 0 || (dx === 0 && Math.abs(dy) >= 50 && Number.isInteger(dy));
      if (e.ctrlKey || e.metaKey || (mouseWheel && !e.shiftKey)) {
        const k = e.ctrlKey && !mouseWheel ? 0.01 : 0.002;
        this.zoomAt(p.x, p.y, Math.exp(-dy * k));
      } else {
        const sx = e.shiftKey && dx === 0 ? dy : dx, sy = e.shiftKey && dx === 0 ? 0 : dy;
        this.view = { ...this.view, x: this.view.x - sx, y: this.view.y - sy };
        this.applyView();
      }
    }, { passive: false });

    on('click', e => {
      if (this.suppressClick) { this.suppressClick = false; return; }
      const ctl = controlOf(e.target);
      if (ctl) { e.stopPropagation(); this.onControl(ctl); return; }
      this.onSelect(this.targetOf(e.target));
    });
    on('dblclick', e => {
      if (controlOf(e.target)) return;
      const t = this.targetOf(e.target);
      if (t) { e.preventDefault(); this.onActivate(t); }
    });
    on('contextmenu', e => {
      e.preventDefault();
      this.hideTip();
      this.onContextMenu(this.targetOf(e.target), e.clientX, e.clientY);
    });
    on('pointerover', e => {
      if (this.drag?.moved) return;
      if (typeof e.clientX === 'number') this.pointer = local(e);
      const t = this.targetOf(e.target);
      const key = t ? JSON.stringify(t) : null;
      if (key === this.hoverKey) return;
      this.hoverKey = key;
      this.scheduleTip(t);
      this.onHover(t);
    });
    on('pointerleave', () => {
      this.hideTip();
      if (this.hoverKey === null) return;
      this.hoverKey = null;
      this.onHover(null);
    });

    if (typeof ResizeObserver !== 'undefined') {
      this.resizeObserver = new ResizeObserver(() => { if (this.pendingFit) this.fit(); });
      this.resizeObserver.observe(this.svg);
    }
  }
}
