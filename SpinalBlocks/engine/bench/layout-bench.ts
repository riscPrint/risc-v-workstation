// Layout quality numbers for a few modules: wire length, bends, time. Not a test; for tuning.
//   node bench/layout-bench.ts <design.json(.gz)> [Module ...]   (env: MAXPORTS, ELK='{"k":"v"}')
import { readFileSync } from 'node:fs';
import { buildViewGraph, initialView, layoutGraph, loadDesign, moduleView } from '../src/core.ts';
import { mainThreadLayout } from '../src/elk-main.ts';

const [file, ...mods] = process.argv.slice(2);
const d = await loadDesign(new Uint8Array(readFileSync(file)));
const st = initialView();
if (process.env.MAXPORTS) st.options.maxPortsPerSide = Number(process.env.MAXPORTS);
if (process.env.BUS) st.options.busThreshold = Number(process.env.BUS);
const elk = process.env.ELK ? JSON.parse(process.env.ELK) : {};
for (const mod of mods.length ? mods : ['BoomTile', 'BoomCore', 'LSU', 'Rob', 'BoomFrontend']) {
  const g = buildViewGraph(d, mod, moduleView(st, mod), st.options);
  const t0 = performance.now();
  const s = await layoutGraph(g, mainThreadLayout(), undefined, elk);
  let len = 0, bends = 0;
  for (const e of s.edges) for (const pts of e.sections) {
    bends += Math.max(0, pts.length - 2);
    for (let i = 1; i < pts.length; i++) len += Math.abs(pts[i].x - pts[i - 1].x) + Math.abs(pts[i].y - pts[i - 1].y);
  }
  const fill = s.blocks.filter(b => !b.block.compound).reduce((a, b) => a + b.width * b.height, 0) / (s.width * s.height);
  const ports = g.blocks.reduce((n, b) => n + b.ports.length, 0) + g.ports.length;
  console.log(`${mod.padEnd(14)} ports ${String(ports).padStart(4)} edges ${String(g.edges.length).padStart(4)} area ${Math.round(s.width)}x${Math.round(s.height)} len/edge ${Math.round(len / g.edges.length)} bends/edge ${(bends / g.edges.length).toFixed(1)} fill ${(100 * fill).toFixed(0)}% ${Math.round(performance.now() - t0)}ms`);
}
