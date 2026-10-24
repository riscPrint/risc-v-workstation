// ViewGraph -> ELK graph -> Scene. The ELK instance is supplied by the host (main thread, web worker,
// Node), so this module has no ELK runtime dependency.

import type { EndRef, VBlock, ViewGraph } from './graph.ts';
import type { Metrics, Point, Scene, SceneBlock, SceneBlockPort, SceneEdge, SceneModulePort } from './scene.ts';
import { defaultMetrics, textWidth } from './scene.ts';

/** Minimal ELK JSON types (elkjs `ElkNode`), kept local so the core does not import elkjs. */
export interface ElkPort { id: string; x?: number; y?: number; width?: number; height?: number; layoutOptions?: Record<string, string> }
export interface ElkSection { startPoint: Point; endPoint: Point; bendPoints?: Point[] }
export interface ElkEdge { id: string; sources: string[]; targets: string[]; sections?: ElkSection[]; junctionPoints?: Point[]; container?: string }
export interface ElkNode {
  id: string;
  x?: number; y?: number; width?: number; height?: number;
  children?: ElkNode[];
  ports?: ElkPort[];
  edges?: ElkEdge[];
  layoutOptions?: Record<string, string>;
}

/** Anything that lays out an ELK graph: `new ELK()` from elkjs satisfies this. */
export interface LayoutEngine { layout(graph: ElkNode): Promise<ElkNode> }

const ROOT = '__root';

const rootOptions: Record<string, string> = {
  'elk.algorithm': 'layered',
  'elk.direction': 'RIGHT',
  'elk.edgeRouting': 'ORTHOGONAL',
  'elk.hierarchyHandling': 'INCLUDE_CHILDREN',
  'elk.layered.spacing.nodeNodeBetweenLayers': '60',
  'elk.layered.spacing.edgeNodeBetweenLayers': '10',
  'elk.layered.spacing.edgeEdgeBetweenLayers': '5',
  'elk.spacing.nodeNode': '32',
  'elk.spacing.edgeNode': '10',
  'elk.spacing.edgeEdge': '5',
  'elk.layered.compaction.postCompaction.strategy': 'EDGE_LENGTH',
  // NETWORK_SIMPLEX and model-order layering look slightly tidier but are 10-100x slower on big modules.
  'elk.layered.nodePlacement.strategy': 'BRANDES_KOEPF',
  'elk.layered.mergeEdges': 'false',
  'elk.padding': '[top=24,left=24,bottom=24,right=24]',
};

/** Area of a block relative to the smallest one: grows with the log of its logic, capped, so big
 *  blocks stand out without a cache taking over the diagram (1 bit -> 1x, 1 kbit -> ~4.6x, 300 kbit -> ~9.5x area,
 *  i.e. at most ~3x wider and taller). */
export function areaScale(weight: number): number {
  return Math.min(10, 1 + 2 * Math.log10(1 + weight / 16));
}

function blockSize(b: VBlock, m: Metrics): { width: number; height: number } {
  const title = Math.max(textWidth(b.label, m.titleSize, m), textWidth(b.sublabel, m.sublabelSize, m)) + 32;
  const scale = areaScale(b.weight);
  if (b.kind === 'comb' && b.signalCount === 1) {
    // A single assignment: a small ":=" block, like Sigasi's "<=" blocks.
    return { width: Math.max(64, textWidth(b.label, m.titleSize, m) + 44), height: 34 };
  }
  if (b.kind !== 'instance') {
    // Logic blocks: base 160x70.
    const area = 160 * 70 * scale;
    const width = Math.max(title, Math.round(Math.sqrt(area * 2.2)));
    return { width, height: Math.max(64, Math.round(area / width)) };
  }
  const left = b.ports.filter(p => p.dir !== 'out');
  const right = b.ports.filter(p => p.dir === 'out');
  const lw = Math.max(0, ...left.map(p => textWidth(portText(p), m.portLabelSize, m)));
  const rw = Math.max(0, ...right.map(p => textWidth(portText(p), m.portLabelSize, m)));
  // Instances: base 260x170, but always room for the title and both port columns.
  const area = 260 * 170 * scale;
  const portHeight = m.headerHeight + Math.max(1, left.length, right.length) * m.portPitch + 10;
  const width = Math.max(title, lw + rw + 56, Math.round(Math.sqrt(area * 1.5)));
  return { width, height: Math.max(portHeight, Math.round(area / width)) };
}

/** Vertical distance between ports of a block: the normal pitch, spread out (up to 1.6x) on tall blocks. */
function portPitchFor(height: number, count: number, m: Metrics): number {
  if (count <= 1) return m.portPitch;
  return Math.max(m.portPitch, Math.min(m.portPitch * 1.6, (height - m.headerHeight - 10) / count));
}

/** Port label as drawn: name plus bus width. */
export function portText(p: { label: string; width: number; bundle: string | null }): string {
  return p.width > 1 || p.bundle ? `${p.label} [${p.width}]` : p.label;
}

function endId(r: EndRef): string {
  if (r.block === null) return `mp:${r.port}`;
  return r.port ? `${r.block}::${r.port}` : r.block;
}

/** Lays out a view graph. */
export async function layoutGraph(graph: ViewGraph, engine: LayoutEngine, metrics: Metrics = defaultMetrics,
                                  elkOptions: Record<string, string> = {}): Promise<Scene> {
  const m = metrics;
  const elkNodes = new Map<string, ElkNode>();
  const root: ElkNode = { id: ROOT, layoutOptions: { ...rootOptions, ...elkOptions }, children: [], edges: [] };
  elkNodes.set(ROOT, root);

  // Module ports as first/last layer nodes.
  for (const p of graph.ports) {
    const width = textWidth(portText(p), m.portLabelSize, m) + 26;
    root.children!.push({
      id: `mp:${p.id}`, width, height: m.modulePortHeight,
      layoutOptions: { 'elk.layered.layering.layerConstraint': p.dir === 'out' ? 'LAST_SEPARATE' : 'FIRST_SEPARATE' },
    });
  }

  // Blocks; parents are listed before children.
  for (const b of graph.blocks) {
    const parent = elkNodes.get(b.parent ?? ROOT)!;
    const node: ElkNode = { id: b.id };
    if (b.compound) {
      node.children = [];
      node.edges = [];
      node.layoutOptions = { 'elk.padding': `[top=${m.areaHeader},left=14,bottom=14,right=14]` };
    } else {
      Object.assign(node, blockSize(b, m));
      if (b.kind === 'instance') {
        node.layoutOptions = { 'elk.portConstraints': 'FIXED_POS' };
        const left = b.ports.filter(p => p.dir !== 'out');
        const right = b.ports.filter(p => p.dir === 'out');
        const s = m.portSize;
        const lp = portPitchFor(node.height!, left.length, m), rp = portPitchFor(node.height!, right.length, m);
        node.ports = [
          ...left.map((p, i) => ({ id: `${b.id}::${p.id}`, x: -s / 2, y: m.headerHeight + i * lp + lp / 2 - s / 2, width: s, height: s,
            layoutOptions: { 'elk.port.side': 'WEST' } })),
          ...right.map((p, i) => ({ id: `${b.id}::${p.id}`, x: node.width! - s / 2, y: m.headerHeight + i * rp + rp / 2 - s / 2, width: s, height: s,
            layoutOptions: { 'elk.port.side': 'EAST' } })),
        ];
      }
    }
    elkNodes.set(b.id, node);
    parent.children!.push(node);
  }

  // Edges go into the lowest common ancestor of their ends (ELK requirement for hierarchical graphs).
  const parentOf = new Map<string, string>();
  for (const b of graph.blocks) parentOf.set(b.id, b.parent ?? ROOT);
  const chain = (block: string | null): string[] => {
    const out: string[] = [];
    for (let c = block === null ? ROOT : parentOf.get(block)!; c; c = c === ROOT ? '' : parentOf.get(c)!) out.push(c);
    return out; // innermost container first
  };
  for (const e of graph.edges) {
    const a = chain(e.source.block);
    const bset = new Set(chain(e.target.block));
    const container = a.find(c => bset.has(c)) ?? ROOT;
    elkNodes.get(container)!.edges!.push({ id: e.id, sources: [endId(e.source)], targets: [endId(e.target)] });
  }

  const laid = await engine.layout(root);
  return toScene(graph, laid, m);
}

function toScene(graph: ViewGraph, laid: ElkNode, m: Metrics): Scene {
  const abs = new Map<string, Point>();
  const byId = new Map<string, ElkNode>();
  const visit = (n: ElkNode, ox: number, oy: number) => {
    const x = ox + (n.x ?? 0), y = oy + (n.y ?? 0);
    abs.set(n.id, { x, y });
    byId.set(n.id, n);
    for (const c of n.children ?? []) visit(c, x, y);
  };
  visit(laid, -(laid.x ?? 0), -(laid.y ?? 0));

  const vports = new Map(graph.ports.map(p => [p.id, p]));
  const ports: SceneModulePort[] = [];
  for (const p of graph.ports) {
    const id = `mp:${p.id}`;
    const n = byId.get(id)!, pos = abs.get(id)!;
    ports.push({ id: p.id, x: pos.x, y: pos.y, width: n.width!, height: n.height!, side: p.dir === 'out' ? 'right' : 'left', port: vports.get(p.id)! });
  }

  const depth = new Map<string, number>();
  const blocks: SceneBlock[] = graph.blocks.map(b => {
    const d = b.parent ? (depth.get(b.parent) ?? 0) + 1 : 0;
    depth.set(b.id, d);
    const n = byId.get(b.id)!, pos = abs.get(b.id)!;
    const bports: SceneBlockPort[] = (n.ports ?? []).map(ep => {
      const vp = b.ports.find(p => `${b.id}::${p.id}` === ep.id)!;
      const side = vp.dir === 'out' ? 'right' : 'left';
      return { id: vp.id, x: pos.x + (side === 'left' ? 0 : n.width!), y: pos.y + ep.y! + ep.height! / 2, side, port: vp };
    });
    return { id: b.id, x: pos.x, y: pos.y, width: n.width!, height: n.height!, depth: d, block: b, ports: bports };
  });

  // Edge coordinates are relative to the edge's container node.
  const vedges = new Map(graph.edges.map(e => [e.id, e]));
  const edges: SceneEdge[] = [];
  const collectEdges = (n: ElkNode) => {
    const o = abs.get(n.id)!;
    for (const e of n.edges ?? []) {
      const off = e.container ? abs.get(e.container) ?? o : o;
      const sh = (p: Point) => ({ x: p.x + off.x, y: p.y + off.y });
      const sections = (e.sections ?? []).map(s => [s.startPoint, ...(s.bendPoints ?? []), s.endPoint].map(sh));
      edges.push({ id: e.id, sections, junctions: (e.junctionPoints ?? []).map(sh), labelAt: labelSpot(sections, m), edge: vedges.get(e.id)! });
    }
    for (const c of n.children ?? []) collectEdges(c);
  };
  collectEdges(laid);
  edges.sort((a, b) => Number(a.id.slice(1)) - Number(b.id.slice(1)));

  // ELK ends wires on the outer side of the port marker; end them on the block border instead.
  const portPoint = new Map<string, Point>();
  for (const b of blocks) for (const p of b.ports) portPoint.set(`${b.id}::${p.id}`, { x: p.x, y: p.y });
  const snap = (pts: Point[] | undefined, i: number, ref: EndRef) => {
    const target = ref.block !== null && ref.port ? portPoint.get(`${ref.block}::${ref.port}`) : undefined;
    if (!pts || pts.length < 2 || !target) return;
    const end = pts[i], next = pts[i === 0 ? 1 : pts.length - 2];
    if (Math.abs(end.y - next.y) < 0.5 && Math.abs(end.y - target.y) < 0.5) end.x = target.x;
  };
  for (const e of edges) {
    snap(e.sections[0], 0, e.edge.source);
    const last = e.sections.at(-1);
    snap(last, (last?.length ?? 1) - 1, e.edge.target);
  }

  return { module: graph.module, width: laid.width ?? 0, height: laid.height ?? 0, ports, blocks, edges, graph, metrics: m };
}

/** Left end of the longest horizontal run, if it is long enough for a short label. */
function labelSpot(sections: Point[][], m: Metrics): Point | null {
  let best: Point | null = null, len = 0;
  for (const pts of sections) {
    for (let i = 0; i + 1 < pts.length; i++) {
      const a = pts[i], b = pts[i + 1];
      if (Math.abs(a.y - b.y) < 0.5 && Math.abs(b.x - a.x) > len) {
        len = Math.abs(b.x - a.x);
        best = { x: Math.min(a.x, b.x) + 6, y: a.y - 3 };
      }
    }
  }
  return len >= 4 * m.edgeLabelSize ? best : null;
}
