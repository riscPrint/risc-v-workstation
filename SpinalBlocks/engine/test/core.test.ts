import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { gzipSync } from 'node:zlib';
import { buildViewGraph, foldPorts, initialView, layoutGraph, loadDesign, moduleView, updateModuleView } from '../src/core.ts';
import type { Port } from '../src/core.ts';
import { mainThreadLayout } from '../src/elk-main.ts';

const bytes = readFileSync(new URL('./fixtures/demo.json', import.meta.url));

test('loads plain and gzipped files', async () => {
  const a = await loadDesign(new Uint8Array(bytes));
  const b = await loadDesign(new Uint8Array(gzipSync(bytes)));
  assert.equal(a.top, 'GcdCluster');
  assert.deepEqual(Object.keys(b.modules), Object.keys(a.modules));
  await assert.rejects(loadDesign('{"format":"other"}'));
});

const port = (name: string, dir: Port['dir'], groups: string[]): Port =>
  ({ name, dir, width: 1, type: 'Bool', group: groups.at(-1) ?? '', groups, loc: null });

test('ports fold by bundle until a side fits', () => {
  const ports = [
    ...Array.from({ length: 10 }, (_, i) => port(`io_a_${i}`, 'in', ['io', 'io_a'])),
    ...Array.from({ length: 10 }, (_, i) => port(`io_b_${i}`, 'in', ['io', 'io_b'])),
    port('clk', 'in', []),
  ];
  const tight = foldPorts(ports, 4, '', {});
  assert.deepEqual(tight.map(p => p.label), ['io_a', 'io_b', 'clk']);
  assert.equal(tight[0].members.length, 10);
  assert.equal(foldPorts(ports, 30, '', {}).length, 21);
  // The user's choice wins over the size limit.
  const opened = foldPorts(ports, 4, '', { '|io_b': true });
  assert.equal(opened.filter(p => p.label.startsWith('io_b_')).length, 10);
  assert.ok(opened.filter(p => p.label.startsWith('io_b_')).every(p => p.expandable));
});

test('a stream bundle folds per direction', () => {
  const payload = Array.from({ length: 20 }, (_, i) => port(`s_payload_${i}`, 'in', ['s', 's_payload']));
  const ports = [port('s_valid', 'in', ['s']), ...payload, port('s_ready', 'out', ['s'])];
  const vp = foldPorts(ports, 4, '', {});
  assert.deepEqual(vp.map(p => [p.label, p.dir, p.members.length]), [['s_valid', 'in', 1], ['s_payload', 'in', 20], ['s_ready', 'out', 1]]);
});

test('collapsed areas absorb their contents and edges', async () => {
  const d = await loadDesign(new Uint8Array(bytes));
  let st = initialView();
  const open = buildViewGraph(d, 'GcdCluster', moduleView(st, 'GcdCluster'), st.options);
  assert.ok(open.blocks.some(b => b.id === 'area:ctrl_fsm'));
  st = updateModuleView(st, 'GcdCluster', v => ({ ...v, areas: { 'area:ctrl': true } }));
  const closed = buildViewGraph(d, 'GcdCluster', moduleView(st, 'GcdCluster'), st.options);
  assert.ok(!closed.blocks.some(b => b.id === 'area:ctrl_fsm'));
  const ctrl = closed.blocks.find(b => b.id === 'area:ctrl')!;
  assert.ok(ctrl.collapsed && !ctrl.compound);
  // fsm -> logic was internal to ctrl and disappears; ctrl drives the GCD loads.
  assert.ok(closed.edges.every(e => !(e.source.block === 'area:ctrl' && e.target.block === 'area:ctrl')));
  assert.ok(closed.edges.some(e => e.source.block === 'area:ctrl' && e.target.block === 'inst:units_0'));
});

test('options hide clocks and control nets; parallel nets merge', async () => {
  const d = await loadDesign(new Uint8Array(bytes));
  const st = initialView();
  const g = buildViewGraph(d, 'GcdCluster', moduleView(st, 'GcdCluster'), st.options);
  assert.ok(g.edges.every(e => !e.clock));
  const withClocks = buildViewGraph(d, 'GcdCluster', moduleView(st, 'GcdCluster'), { ...st.options, showClocks: true });
  assert.ok(withClocks.edges.some(e => e.clock));
  const noCtl = buildViewGraph(d, 'GcdCluster', moduleView(st, 'GcdCluster'), { ...st.options, showControl: false });
  assert.ok(noCtl.edges.every(e => !e.control));
  const keys = g.edges.map(e => JSON.stringify([e.source, e.target]));
  assert.equal(new Set(keys).size, keys.length);
});

test('layout gives every block, port and edge a position', async () => {
  const d = await loadDesign(new Uint8Array(bytes));
  const st = initialView();
  for (const mod of Object.keys(d.modules)) {
    const g = buildViewGraph(d, mod, moduleView(st, mod), st.options);
    const s = await layoutGraph(g, mainThreadLayout());
    assert.equal(s.blocks.length, g.blocks.length);
    for (const b of s.blocks) {
      assert.ok(Number.isFinite(b.x) && b.width > 0, b.id);
      if (b.block.parent) {
        const p = s.blocks.find(x => x.id === b.block.parent)!;
        assert.ok(b.x >= p.x && b.x + b.width <= p.x + p.width + 0.5, `${b.id} inside ${p.id}`);
      }
    }
    for (const e of s.edges) {
      assert.ok(e.sections.length > 0, e.id);
      for (const pts of e.sections) for (let i = 1; i < pts.length; i++)
        assert.ok(Math.abs(pts[i].x - pts[i - 1].x) < 0.5 || Math.abs(pts[i].y - pts[i - 1].y) < 0.5, 'orthogonal');
    }
  }
});

test('source lines find their elements; files find their modules', async () => {
  const { locate, modulesDefinedIn, instancePaths } = await import('../src/core.ts');
  const d = await loadDesign(new Uint8Array(readFileSync(new URL('./fixtures/demo.json', import.meta.url))));
  const unit = d.modules.GcdCluster.instances.find(i => i.name === 'units_0')!;
  const hits = locate(d, unit.loc!.file, unit.loc!.line);
  assert.ok(hits.some(h => h.kind === 'instance' && h.module === 'GcdCluster'));
  // Only the file name works too, and a line inside a statement finds the declaration just above.
  assert.ok(locate(d, 'Demo.scala', unit.loc!.line + 1).some(h => h.kind === 'instance'));
  assert.deepEqual(modulesDefinedIn(d, unit.loc!.file).sort(), ['Gcd', 'GcdCluster']);
  assert.deepEqual(instancePaths(d, 'Gcd'), [['units_0'], ['units_1']]);
});

test('state machines lay out with reset, dead and unused states', async () => {
  const { layoutFsm } = await import('../src/core.ts');
  const d = await loadDesign(new Uint8Array(readFileSync(new URL('./fixtures/demo.json', import.meta.url))));
  const fsms = d.modules.GcdCluster.fsms ?? [];
  assert.deepEqual(fsms.map(f => f.name).sort(), ['ctrl_fsm', 'results_phase']);
  const phase = await layoutFsm(fsms.find(f => f.name === 'results_phase')!, mainThreadLayout());
  const st = new Map(phase.states.map(s => [s.name, s]));
  assert.ok(st.get('Empty')!.reset);
  assert.ok(st.get('Spare')!.unused);
  assert.ok(phase.resetArrow && phase.resetArrow.length >= 2);
  assert.ok(phase.transitions.every(t => t.sections.length > 0));
  assert.ok(phase.transitions.some(t => t.label.join(' ').includes('results_write')));
});
