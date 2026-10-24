import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseHTML, DOMParser } from 'linkedom';
import { layoutFsm } from '../src/core/fsm.ts';
import type { FsmScene } from '../src/core/fsm.ts';
import type { Fsm } from '../src/core/model.ts';
import { mainThreadLayout } from '../src/elk-main.ts';
import { SvgFsmRenderer, curvePath, onEllipse } from '../src/render/fsm-svg.ts';
import type { FsmRendererEvents } from '../src/render/types.ts';

const loc = (line: number) => ({ file: 'Gcd.scala', line });

/** A small machine with every feature: reset, conditions and comments, a from-any transition,
 *  an unresolved one, a dead state and an unused one. */
export const demoFsm: Fsm = {
  id: 'fsm:ctrl_fsm', name: 'ctrl_fsm', node: 'area:ctrl_fsm', register: 'ctrl_fsm_stateReg', kind: 'statemachine', loc: loc(10),
  states: ['idle', 'load', 'run', 'done', 'halted', 'spare'].map((name, i) => ({ name, loc: loc(20 + i) })),
  reset: 'idle',
  transitions: [
    { from: 'idle', to: 'load', condition: 'fifo.io_pop_valid', comment: null, loc: loc(30) },
    { from: 'load', to: 'run', condition: null, comment: 'operands latched', loc: loc(31) },
    { from: 'run', to: 'done', condition: 'units(0).io_valid && units(1).io_valid && !io_flush', comment: null, loc: loc(32) },
    { from: 'run', to: 'run', condition: '!units(0).io_valid', comment: null, loc: loc(33) },
    { from: 'done', to: 'idle', condition: null, comment: null, loc: loc(34) },
    { from: 'done', to: null, condition: 'io_jump', comment: null, loc: loc(35) },
    { from: null, to: 'halted', condition: 'io_halt', comment: null, loc: loc(36) },
  ],
};

export function demoFsmScene(): Promise<FsmScene> {
  return layoutFsm(demoFsm, mainThreadLayout(), { showConditions: true, showComments: true, wrap: 36, maxLines: 4 });
}

function setup() {
  const { document, window } = parseHTML('<!doctype html><html><head></head><body><div id="c"></div></body></html>');
  const container = document.getElementById('c') as unknown as HTMLElement;
  const log: [string, unknown][] = [];
  const events: FsmRendererEvents = {
    select: t => log.push(['select', t]),
    hover: t => log.push(['hover', t]),
    activate: t => log.push(['activate', t]),
    contextMenu: t => log.push(['contextMenu', t]),
  };
  const renderer = new SvgFsmRenderer(container, events);
  const fire = (el: Element, type: string) => el.dispatchEvent(new window.Event(type, { bubbles: true }));
  return { container, renderer, log, fire };
}

test('fsm helpers: Bézier paths and ellipse clipping', () => {
  const p = (x: number, y: number) => ({ x, y });
  assert.equal(curvePath([p(0, 0), p(0, 10), p(10, 10), p(10, 20)]), 'M0 0C0 10 10 10 10 20');
  assert.equal(curvePath([p(0, 0), p(5, 5), p(10, 0)]), 'M0 0L5 5L10 0');
  const e = { cx: 0, cy: 0, rx: 20, ry: 10 };
  // Coming down onto the top of the ellipse from its bounding box corner line.
  const hit = onEllipse(p(0, -10), p(0, 1), e, true)!;
  assert.ok(Math.abs(hit.y + 10) < 1e-9);
  const side = onEllipse(p(-20, -10), p(1, 1), e, true)!;
  assert.ok(Math.abs((side.x / 20) ** 2 + (side.y / 10) ** 2 - 1) < 1e-9);
});

test('draws states, transitions, reset, pseudo-nodes and labels', async () => {
  const scene = await demoFsmScene();
  const { container, renderer } = setup();
  renderer.render(scene, false);
  const q = (s: string) => container.querySelectorAll(s).length;
  assert.equal(q('.sb-st'), demoFsm.states.length);
  assert.equal(q('.sb-st ellipse'), demoFsm.states.length);
  assert.equal(q('.sb-tr'), demoFsm.transitions.length);
  assert.equal(q('.sb-tr .sb-ah'), demoFsm.transitions.length, 'every transition has an arrowhead');
  assert.equal(q('.sb-tr.sb-unres'), 1);
  assert.equal(q('.sb-reset circle'), 1);
  assert.equal(q('.sb-any'), 1);
  assert.equal(q('.sb-unknown'), 1);
  assert.ok(container.querySelector('[data-t="s"][data-id="spare"]')!.classList.contains('sb-unused'));
  assert.ok(container.querySelector('[data-t="s"][data-id="idle"]')!.classList.contains('sb-reset-state'));
  // Condition text and the comment (muted) are drawn.
  const texts = Array.from(container.querySelectorAll('.sb-tlabel text')).map(t => t.textContent);
  assert.ok(texts.includes('fifo.io_pop_valid'));
  assert.equal(q('.sb-tlabel text.sb-cmt'), 1);
  assert.ok(container.querySelector('.sb-ftitle')!.textContent === 'ctrl_fsm');
  assert.ok(Array.from(container.querySelectorAll('.sb-tl')).every(p => /^M[-\d.]+ [-\d.]+(C|L)/.test(p.getAttribute('d')!)));
});

test('fsm clicks, highlight, selection, export', async () => {
  const scene = await demoFsmScene();
  const { container, renderer, log, fire } = setup();
  renderer.render(scene, false);

  fire(container.querySelector('[data-t="s"][data-id="run"] ellipse')!, 'click');
  assert.deepEqual(log.pop(), ['select', { kind: 'state', name: 'run' }]);
  fire(container.querySelector('[data-t="t"][data-id="t0"] .sb-eh')!, 'dblclick');
  assert.deepEqual(log.pop(), ['activate', { kind: 'transition', id: 't0' }]);
  fire(container.querySelector('.sb-tlabel[data-id="t0"] text')!, 'click');
  assert.deepEqual(log.pop(), ['select', { kind: 'transition', id: 't0' }]);
  fire(container.querySelector('[data-t="s"][data-id="idle"] text')!, 'contextmenu');
  assert.equal(log.at(-1)![0], 'contextMenu');
  assert.deepEqual(log.pop()![1], { kind: 'state', name: 'idle' });
  fire(container.querySelector('.sb-frame')!, 'click');
  assert.deepEqual(log.pop(), ['select', null]);

  // A state lights up its transitions and the states at their other ends.
  renderer.highlight([{ kind: 'state', name: 'run' }]);
  const lit = new Set(Array.from(container.querySelectorAll('.sb-tr.sb-hl')).map(e => e.getAttribute('data-id')));
  assert.deepEqual([...lit].sort(), ['t1', 't2', 't3']);
  for (const n of ['load', 'run', 'done']) assert.ok(container.querySelector(`[data-t="s"][data-id="${n}"]`)!.classList.contains('sb-hl'), n);
  assert.ok(!container.querySelector('[data-t="s"][data-id="idle"]')!.classList.contains('sb-hl'));
  assert.ok(container.querySelector('.sb-vp')!.classList.contains('sb-dimming'));
  // An unresolved transition lights its "?".
  renderer.highlight([{ kind: 'transition', id: 't5' }]);
  assert.ok(container.querySelector('.sb-unknown')!.classList.contains('sb-hl'));
  renderer.highlight([]);
  assert.equal(container.querySelectorAll('.sb-hl').length, 0);

  renderer.select([{ kind: 'transition', id: 't2' }]);
  assert.ok(container.querySelector('.sb-tr[data-id="t2"]')!.classList.contains('sb-sel'));
  renderer.setViewport({ x: 5, y: 6, zoom: 2 });
  assert.deepEqual(renderer.getViewport(), { x: 5, y: 6, zoom: 2 });
  renderer.setOptions({ theme: 'dark' });

  const out = renderer.exportSvg();
  assert.ok(!out.includes('var(--'));
  assert.ok(!out.includes('data-t='));
  const doc = new DOMParser().parseFromString(out.replace(/^<\?xml[^>]*>\s*/, ''), 'image/svg+xml');
  assert.equal(doc.documentElement.querySelectorAll('ellipse').length, demoFsm.states.length);
  assert.ok(doc.documentElement.querySelector('style')!.textContent!.includes('#1e1e1e'), 'dark theme colours');

  renderer.dispose();
  assert.equal(container.querySelectorAll('.sb-root').length, 0);
});
