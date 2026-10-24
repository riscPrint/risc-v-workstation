import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { parseHTML, DOMParser } from 'linkedom';
import { buildViewGraph, defaultMetrics, initialView, layoutGraph, loadDesign, moduleView } from '../src/core.ts';
import type { Scene } from '../src/core.ts';
import { mainThreadLayout } from '../src/elk-main.ts';
import { SvgRenderer, edgeStroke, fitText, portShape } from '../src/render/svg.ts';
import type { RendererEvents, Target } from '../src/render/types.ts';

const bytes = readFileSync(new URL('./fixtures/demo.json', import.meta.url));

async function demoScene(maxPortsPerSide?: number): Promise<Scene> {
  const d = await loadDesign(new Uint8Array(bytes));
  const st = initialView();
  if (maxPortsPerSide) st.options.maxPortsPerSide = maxPortsPerSide;
  return layoutGraph(buildViewGraph(d, d.top, moduleView(st, d.top), st.options), mainThreadLayout());
}

/** A renderer in a fresh DOM, recording the events it fires. */
function setup() {
  const { document, window } = parseHTML('<!doctype html><html><head></head><body><div id="c"></div></body></html>');
  const container = document.getElementById('c') as unknown as HTMLElement;
  const log: [string, unknown][] = [];
  const events: RendererEvents = {
    select: t => log.push(['select', t]),
    hover: t => log.push(['hover', t]),
    activate: t => log.push(['activate', t]),
    toggleArea: id => log.push(['toggleArea', id]),
    toggleBundle: (owner, port) => log.push(['toggleBundle', [owner, port]]),
    contextMenu: t => log.push(['contextMenu', t]),
    open: id => log.push(['open', id]),
  };
  const renderer = new SvgRenderer(container, events);
  const fire = (el: Element, type: string) => el.dispatchEvent(new window.Event(type, { bubbles: true }));
  return { document, container, renderer, log, fire };
}

test('helpers: stroke widths, text fitting, port shapes', () => {
  // Sigasi's two wire widths: thin for one bit, thick for buses and merged nets.
  assert.equal(edgeStroke(1), 1);
  assert.ok(edgeStroke(16) > edgeStroke(1));
  assert.equal(edgeStroke(16), edgeStroke(4096));
  assert.equal(edgeStroke(1, 3), edgeStroke(16));
  assert.equal(fitText('short', 10, 1000, defaultMetrics), 'short');
  const cut = fitText('a_rather_long_signal_name', 10, 60, defaultMetrics);
  assert.ok(cut.endsWith('…') && cut.length * 10 * defaultMetrics.charWidth <= 60);
  // Triangles for in/out, squares for inout.
  assert.equal(portShape(0, 0, 8, 'in').split(' ').length, 3);
  assert.equal(portShape(0, 0, 8, 'out').split(' ').length, 3);
  assert.equal(portShape(0, 0, 8, 'inout').split(' ').length, 4);
});

test('draws every block, port and edge of the demo scene', async () => {
  const scene = await demoScene(3);
  const { container, renderer } = setup();
  renderer.render(scene, false);
  const q = (s: string) => container.querySelectorAll(s).length;
  assert.equal(q('.sb-root'), 1);
  assert.equal(q('.sb-blk'), scene.blocks.length);
  assert.equal(q('.sb-inst'), scene.blocks.filter(b => b.block.kind === 'instance').length);
  assert.equal(q('.sb-compound'), scene.blocks.filter(b => b.block.compound).length);
  assert.equal(q('.sb-mp'), scene.ports.length);
  assert.equal(q('.sb-bp'), scene.blocks.reduce((n, b) => n + b.ports.length, 0));
  assert.equal(q('.sb-e'), scene.edges.length);
  const controls = scene.ports.filter(p => p.port.bundle || p.port.expandable).length
    + scene.blocks.reduce((n, b) => n + b.ports.filter(p => p.port.bundle || p.port.expandable).length, 0);
  assert.ok(controls > 0);
  assert.equal(q('[data-act="bundle"]'), controls);
  assert.equal(q('[data-act="area"]'), scene.blocks.filter(b => b.block.collapsible).length);
  assert.ok(container.querySelector('.sb-frame'));
  assert.equal(q('[data-act="open"]'), scene.blocks.filter(b => b.block.kind === 'instance' && b.block.module).length);
  assert.ok(q('.sb-mp polygon.sb-pm') === scene.ports.length, 'module ports are solid markers');
  // Rendering again replaces the drawing instead of adding to it.
  renderer.render(scene, true);
  assert.equal(q('.sb-blk'), scene.blocks.length);
});

test('clicks map back to targets; controls only toggle', async () => {
  // Few ports per side, so the demo has folded bundles with +/- controls.
  const scene = await demoScene(3);
  const { container, renderer, log, fire } = setup();
  renderer.render(scene, false);

  const inst = scene.blocks.find(b => b.block.kind === 'instance')!;
  fire(container.querySelector(`[data-t="b"][data-id="${inst.id}"] .sb-title`)!, 'click');
  assert.deepEqual(log.pop(), ['select', { kind: 'block', id: inst.id }]);
  fire(container.querySelector(`[data-t="b"][data-id="${inst.id}"] .sb-box`)!, 'dblclick');
  assert.deepEqual(log.pop(), ['activate', { kind: 'block', id: inst.id }]);

  const bp = inst.ports[0];
  fire(container.querySelector(`[data-t="bp"][data-b="${inst.id}"][data-p="${bp.id}"] text`)!, 'click');
  assert.deepEqual(log.pop(), ['select', { kind: 'blockPort', block: inst.id, port: bp.id }]);

  const mp = scene.ports[0];
  fire(container.querySelector(`[data-t="mp"][data-id="${mp.id}"] .sb-pm`)!, 'contextmenu');
  assert.equal(log.at(-1)![0], 'contextMenu');
  assert.deepEqual(log.pop()![1], { kind: 'modulePort', id: mp.id });

  const edge = scene.edges[0];
  fire(container.querySelector(`[data-t="e"][data-id="${edge.id}"] .sb-eh`)!, 'click');
  assert.deepEqual(log.pop(), ['select', { kind: 'edge', id: edge.id }]);

  // The open glyph in an instance header goes inside the instance.
  fire(container.querySelector(`[data-act="open"][data-id="${inst.id}"] path`)!, 'click');
  assert.deepEqual(log.pop(), ['open', inst.id]);

  fire(container.querySelector('.sb-frame')!, 'click');
  assert.deepEqual(log.pop(), ['select', null]);

  const area = scene.blocks.find(b => b.block.collapsible)!;
  fire(container.querySelector(`[data-act="area"][data-id="${area.id}"] path`)!, 'click');
  assert.deepEqual(log.pop(), ['toggleArea', area.id]);
  const n = log.length;
  fire(container.querySelector(`[data-act="area"][data-id="${area.id}"] path`)!, 'dblclick');
  assert.equal(log.length, n, 'dblclick on a control fires nothing');

  const ctl = container.querySelector('[data-act="bundle"]');
  assert.ok(ctl, 'the scene has a folded bundle');
  fire(ctl.querySelector('path')!, 'click');
  const [kind, [owner, port]] = log.pop() as [string, [string, string]];
  assert.equal(kind, 'toggleBundle');
  assert.equal(owner, ctl.getAttribute('data-owner'));
  assert.equal(port, ctl.getAttribute('data-p'));

  fire(container.querySelector(`[data-t="b"][data-id="${inst.id}"] .sb-box`)!, 'pointerover');
  assert.deepEqual(log.pop(), ['hover', { kind: 'block', id: inst.id }]);
});

test('highlight marks a block, its edges and their other ends', async () => {
  const scene = await demoScene();
  const { container, renderer } = setup();
  renderer.render(scene, false);
  const inst = scene.blocks.find(b => b.block.kind === 'instance')!;
  const mine = scene.edges.filter(e => e.edge.source.block === inst.id || e.edge.target.block === inst.id);
  assert.ok(mine.length > 0);
  renderer.highlight([{ kind: 'block', id: inst.id }]);
  assert.ok(container.querySelector('.sb-vp')!.classList.contains('sb-dimming'));
  const lit = new Set(Array.from(container.querySelectorAll('.sb-e.sb-hl')).map(e => e.getAttribute('data-id')));
  assert.deepEqual([...lit].sort(), mine.map(e => e.id).sort());
  for (const e of mine) {
    const other = e.edge.source.block === inst.id ? e.edge.target : e.edge.source;
    const sel = other.block === null ? `[data-t="mp"][data-id="${other.port}"]` : `[data-t="b"][data-id="${other.block}"]`;
    assert.ok(container.querySelector(sel)!.classList.contains('sb-hl'), sel);
  }
  renderer.highlight([]);
  assert.equal(container.querySelectorAll('.sb-hl').length, 0);
  assert.ok(!container.querySelector('.sb-vp')!.classList.contains('sb-dimming'));

  const targets: Target[] = [{ kind: 'edge', id: scene.edges[0].id }, { kind: 'modulePort', id: scene.ports[0].id }];
  renderer.select(targets);
  assert.ok(container.querySelector(`[data-t="e"][data-id="${scene.edges[0].id}"]`)!.classList.contains('sb-sel'));
  assert.ok(container.querySelector(`[data-t="mp"][data-id="${scene.ports[0].id}"]`)!.classList.contains('sb-sel'));
  renderer.select([]);
  assert.equal(container.querySelectorAll('.sb-sel').length, 0);
});

test('viewport, options, export and dispose', async () => {
  const scene = await demoScene();
  const { container, renderer } = setup();
  renderer.render(scene, false);
  renderer.setViewport({ x: 10, y: 20, zoom: 0.3 });
  assert.deepEqual(renderer.getViewport(), { x: 10, y: 20, zoom: 0.3 });
  const svg = container.querySelector('.sb-svg')!;
  assert.match(container.querySelector('.sb-vp')!.getAttribute('transform')!, /translate\(10,20\) scale\(0.3\)/);
  assert.ok(svg.classList.contains('sb-far') && svg.classList.contains('sb-farther'));
  renderer.setViewport({ x: 0, y: 0, zoom: 1 });
  assert.ok(!svg.classList.contains('sb-far'));
  renderer.setOptions({ theme: 'dark', showEdgeLabels: false });
  assert.ok(container.querySelector('.sb-root')!.classList.contains('sb-dark'));
  assert.ok(svg.classList.contains('sb-nolabels'));

  renderer.setOptions({ showEdgeLabels: true });
  renderer.highlight([{ kind: 'block', id: scene.blocks[0].id }]);
  const out = renderer.exportSvg();
  assert.ok(out.startsWith('<?xml'));
  assert.ok(!out.includes('var(--'), 'colours are resolved');
  assert.ok(!out.includes('data-t='), 'no interaction attributes');
  assert.ok(!out.includes('data-act='), 'no controls');
  const doc = new DOMParser().parseFromString(out.replace(/^<\?xml[^>]*>\s*/, ''), 'image/svg+xml');
  const root = doc.documentElement;
  assert.equal(root.tagName.toLowerCase(), 'svg');
  assert.equal(root.getAttribute('xmlns'), 'http://www.w3.org/2000/svg');
  assert.ok(root.getAttribute('viewBox'));
  assert.equal(root.querySelectorAll('.sb-blk').length, scene.blocks.length);
  assert.ok(root.querySelector('style')!.textContent!.includes('#1e1e1e'), 'dark theme colours');

  renderer.dispose();
  assert.equal(container.querySelectorAll('.sb-root').length, 0);
});
