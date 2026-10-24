// Builds the visible graph of one module for a view state: folds ports into bundles, hides the contents of
// collapsed areas, and merges the nets that end up between the same two visible endpoints.

import type { Design, Endpoint, Loc, LogicNode, Net, NodeKind, Port, Signal } from './model.ts';
import { ModuleIndex } from './model.ts';
import type { ModuleView, ViewOptions } from './view.ts';

/** A port as drawn: one real port, or a folded bundle of ports with the same direction. */
export interface VPort {
  id: string;
  label: string;
  dir: 'in' | 'out' | 'inout';
  /** Sum of member widths. */
  width: number;
  /** Real port names in this visible port. */
  members: string[];
  /** Bundle name when folded (key for ModuleView.bundles), else null. */
  bundle: string | null;
  /** Can be opened (folded bundle) or closed (member of a bundle the user opened). */
  expandable: boolean;
  loc: Loc | null;
}

export type BlockKind = 'instance' | NodeKind;

export interface VBlock {
  id: string;
  kind: BlockKind;
  label: string;
  /** Second line: module name for instances, class/kind for logic. */
  sublabel: string;
  /** Enclosing visible area block, or null. */
  parent: string | null;
  /** Has visible children (an expanded area). */
  compound: boolean;
  /** A collapsed area (children hidden). */
  collapsed: boolean;
  /** Area that can be collapsed/expanded. */
  collapsible: boolean;
  /** Ports, only for instances. */
  ports: VPort[];
  /** Module name for instances (to descend into). */
  module: string | null;
  /** How much logic the block holds: bits of registers, signals and memories inside it, recursively.
   *  The layout sizes blocks by it. */
  weight: number;
  /** Signals drawn in the block (logic blocks; 0 for instances). A `comb` block with one is an assignment. */
  signalCount: number;
  loc: Loc | null;
}

/** One end of a visible edge: a module port (block null) or a block, with a port for instances. */
export interface EndRef { block: string | null; port: string | null }

export interface VEdge {
  id: string;
  source: EndRef;
  target: EndRef;
  /** Net ids merged into this edge. */
  nets: string[];
  /** Their names, same order. */
  netNames: string[];
  label: string;
  /** Sum of the widths of the merged nets. */
  width: number;
  control: boolean;
  clock: boolean;
}

export interface ViewGraph {
  module: string;
  /** The module's own ports. */
  ports: VPort[];
  /** Parents before children. */
  blocks: VBlock[];
  edges: VEdge[];
  /** Nets dropped by the options (clock/control filters), for status display. */
  hiddenNets: number;
}

// ---------------------------------------------------------------------------------------------
// Port folding

interface Tree { name: string; children: Map<string, Tree>; ports: Port[] }

/** A side always shows at least this many entries when it can (no single "io" lump). */
const MIN_ENTRIES = 4;

/** Folds ports of one direction. Opens bundles largest first while the side stays under `max` (or has
 *  fewer than MIN_ENTRIES entries), honouring the user's explicit choices in `bundles` (keyed by `${owner}|${group}`). */
function foldSide(ports: Port[], max: number, owner: string, bundles: Record<string, boolean>): VPort[] {
  const root: Tree = { name: '', children: new Map(), ports: [] };
  for (const p of ports) {
    let t = root;
    for (const g of p.groups ?? []) {
      if (!t.children.has(g)) t.children.set(g, { name: g, children: new Map(), ports: [] });
      t = t.children.get(g)!;
    }
    t.ports.push(p);
  }
  const all = (t: Tree): Port[] => [...t.ports, ...[...t.children.values()].flatMap(all)];
  const size = (t: Tree) => t.ports.length + t.children.size;

  // Entries are either a real port or a folded subtree.
  type Entry = { port: Port } | { tree: Tree };
  const open = (t: Tree): Entry[] => [...t.ports.map(port => ({ port })), ...[...t.children.values()].map(tree => ({ tree }))];
  let entries: Entry[] = open(root);
  const userOpened = new Set<string>();

  for (let guard = 0; guard < 10000; guard++) {
    let best = -1;
    for (let i = 0; i < entries.length; i++) {
      const e = entries[i];
      if (!('tree' in e)) continue;
      const choice = bundles[`${owner}|${e.tree.name}`];
      // Always open single-entry bundles and the ones the user opened; never the ones they closed.
      if (choice === true || size(e.tree) <= 1) { best = i; if (choice === true) userOpened.add(e.tree.name); break; }
      if (choice === false) continue;
      const grow = size(e.tree) - 1;
      const fits = entries.length + grow <= max || (entries.length < MIN_ENTRIES && entries.length + grow <= 2 * max);
      if (!fits) continue;
      if (best < 0 || size(e.tree) > size((entries[best] as { tree: Tree }).tree)) best = i;
    }
    if (best < 0) break;
    const t = (entries[best] as { tree: Tree }).tree;
    entries = [...entries.slice(0, best), ...open(t), ...entries.slice(best + 1)];
  }

  // Keep declaration order of the first member.
  const order = new Map(ports.map((p, i) => [p.name, i]));
  const first = (e: Entry) => order.get('port' in e ? e.port.name : all(e.tree)[0].name) ?? 0;
  entries.sort((a, b) => first(a) - first(b));

  return entries.map(e => {
    if ('port' in e) {
      const p = e.port;
      const parent = p.groups?.length ? p.groups[p.groups.length - 1] : null;
      return {
        id: `p:${p.name}`, label: p.name, dir: p.dir, width: p.width, members: [p.name], bundle: null,
        expandable: !!parent && userOpened.has(parent), loc: p.loc,
      };
    }
    const members = all(e.tree);
    return {
      id: `b:${e.tree.name}:${members[0].dir}`, label: e.tree.name, dir: members[0].dir,
      width: members.reduce((s, p) => s + p.width, 0), members: members.map(p => p.name),
      bundle: e.tree.name, expandable: true, loc: members[0].loc,
    };
  });
}

/** Folds a port list: inputs and outputs separately (a Stream bundle shows on both sides). */
export function foldPorts(ports: Port[], max: number, owner: string, bundles: Record<string, boolean>): VPort[] {
  const ins = ports.filter(p => p.dir !== 'out');
  const outs = ports.filter(p => p.dir === 'out');
  return [...foldSide(ins, max, owner, bundles), ...foldSide(outs, max, owner, bundles)];
}

// ---------------------------------------------------------------------------------------------
// Area collapsing

/** Collapsed state of every area: the user's choices, then automatic collapsing so the module shows
 *  at most `maxBlocks` blocks. Shallow areas open first, smaller ones before larger ones. */
export function collapsedAreas(idx: ModuleIndex, view: ModuleView, maxBlocks: number): Set<string> {
  const areas = idx.nodeList.filter(n => n.compound);
  const collapsed = new Set(areas.map(a => a.id));
  for (const a of areas) if (view.areas[a.id] === false) collapsed.delete(a.id);

  const visibleCount = () => {
    let n = 0;
    const walk = (parent: string | null) => {
      for (const id of idx.children.get(parent) ?? []) {
        n++;
        if (!collapsed.has(id) && idx.nodes.get(id)?.compound) walk(id);
      }
    };
    walk(null);
    return n;
  };
  const isShown = (id: string) => idx.ancestors(id).every(a => !collapsed.has(a));

  const auto = areas
    .filter(a => view.areas[a.id] === undefined)
    .sort((a, b) => idx.depth(a.id) - idx.depth(b.id) || (idx.children.get(a.id)?.length ?? 0) - (idx.children.get(b.id)?.length ?? 0));
  let count = visibleCount();
  let changed = true;
  while (changed) {
    changed = false;
    for (const a of auto) {
      if (!collapsed.has(a.id) || !isShown(a.id)) continue;
      const grow = (idx.children.get(a.id)?.length ?? 1) - 1;
      if (count + grow <= maxBlocks) {
        collapsed.delete(a.id);
        count += grow;
        changed = true;
      }
    }
  }
  return collapsed;
}

// ---------------------------------------------------------------------------------------------
// Weights

/** Bits a signal stands for; a memory counts all its words. */
function signalBits(s: Signal): number {
  const words = /^Mem\[(\d+)\]/.exec(s.type);
  return words ? s.width * Number(words[1]) : s.width;
}

const moduleWeights = new WeakMap<Design, Map<string, number>>();

/** Bits of logic in a module, including its children. */
export function moduleWeight(design: Design, name: string): number {
  let cache = moduleWeights.get(design);
  if (!cache) moduleWeights.set(design, cache = new Map());
  const hit = cache.get(name);
  if (hit !== undefined) return hit;
  cache.set(name, 0); // guards against (impossible) recursive modules
  const m = design.modules[name];
  const w = !m ? 0 : m.nodes.reduce((sum, n) => sum + n.signals.reduce((a, sig) => a + signalBits(sig), 0), 0) +
    m.instances.reduce((sum, i) => sum + moduleWeight(design, i.module), 0);
  cache.set(name, w);
  return w;
}

/** "119 kbit" style. */
export function formatBits(bits: number): string {
  if (bits >= 1e6) return `${(bits / 1e6).toFixed(bits >= 1e7 ? 0 : 1)} Mbit`;
  if (bits >= 1e3) return `${(bits / 1e3).toFixed(bits >= 1e4 ? 0 : 1)} kbit`;
  return `${bits} bit`;
}

// ---------------------------------------------------------------------------------------------
// The graph

const kindLabel: Record<NodeKind, string> = {
  area: 'area', logic: 'logic', reg: 'register', comb: 'combinational', mixed: 'logic', mem: 'memory',
};

function nodeSublabel(n: LogicNode): string {
  if (n.className) return n.className.split('.').pop()!;
  if (n.kind === 'area' || n.kind === 'logic') {
    const parts = [];
    if (n.regCount) parts.push(`${n.regCount} reg`);
    if (n.combCount) parts.push(`${n.combCount} comb`);
    const mems = n.signals.filter(s => s.type.startsWith('Mem[')).length;
    if (mems) parts.push(`${mems} mem`);
    return parts.join(' · ') || kindLabel[n.kind];
  }
  if (n.signals.length === 1) {
    const s = n.signals[0];
    return `${kindLabel[n.kind]} · ${s.type}${s.width > 1 ? `[${s.width}]` : ''}`;
  }
  return `${kindLabel[n.kind]} · ${n.signals.length} signals`;
}

/** Common `_`-separated prefix of names, or "". */
function commonPrefix(names: string[]): string {
  const split = names.map(n => n.split('_'));
  const out: string[] = [];
  for (let i = 0; i < split[0].length; i++) {
    const part = split[0][i];
    if (split.every(s => s[i] === part)) out.push(part); else break;
  }
  return out.join('_');
}

export function buildViewGraph(design: Design, moduleName: string, view: ModuleView, options: ViewOptions): ViewGraph {
  const idx = new ModuleIndex(design, moduleName);
  const m = idx.module;
  const collapsed = collapsedAreas(idx, view, options.maxBlocks);

  // Module ports.
  const ports = foldPorts(m.ports, options.maxPortsPerSide, '', view.bundles);
  const modulePortOf = new Map<string, string>();
  for (const vp of ports) for (const name of vp.members) modulePortOf.set(name, vp.id);

  // Visible block for every node/instance id: itself, or its outermost collapsed ancestor.
  const visibleOf = new Map<string, string>();
  const shown = (id: string): string => {
    const hit = visibleOf.get(id);
    if (hit) return hit;
    const anc = idx.ancestors(id); // innermost first
    let v = id;
    for (const a of anc) if (collapsed.has(a)) v = a;
    visibleOf.set(id, v);
    return v;
  };

  /** Logic in a node, plus everything inside it when it is an area. */
  const areaWeight = (id: string): number => {
    const own = idx.nodes.get(id)?.signals.reduce((a, sig) => a + signalBits(sig), 0) ?? 0;
    const inst = idx.instances.get(id);
    if (inst) return moduleWeight(design, inst.module);
    return own + (idx.children.get(id) ?? []).reduce((a, c) => a + areaWeight(c), 0);
  };

  const blocks: VBlock[] = [];
  const instPortOf = new Map<string, Map<string, string>>();
  const walk = (parent: string | null) => {
    for (const id of idx.children.get(parent) ?? []) {
      if (shown(id) !== id) continue;
      const inst = idx.instances.get(id);
      if (inst) {
        const child = design.modules[inst.module];
        const vports = child ? foldPorts(child.ports, options.maxPortsPerSide, inst.id, view.bundles) : [];
        const map = new Map<string, string>();
        for (const vp of vports) for (const name of vp.members) map.set(name, vp.id);
        instPortOf.set(inst.id, map);
        const weight = moduleWeight(design, inst.module);
        blocks.push({
          id, kind: 'instance', label: inst.name,
          sublabel: `${inst.module}${child?.blackbox ? ' (blackbox)' : ''}${weight ? ` · ${formatBits(weight)}` : ''}`,
          parent, compound: false, collapsed: false, collapsible: false, ports: vports, module: inst.module, weight, signalCount: 0, loc: inst.loc,
        });
        continue;
      }
      const n = idx.nodes.get(id)!;
      const isCollapsed = collapsed.has(id);
      blocks.push({
        id, kind: n.kind, label: n.name, sublabel: nodeSublabel(n), parent,
        compound: n.compound && !isCollapsed, collapsed: isCollapsed, collapsible: n.compound,
        ports: [], module: null, weight: areaWeight(n.id), signalCount: n.signals.length, loc: n.loc,
      });
      if (n.compound && !isCollapsed) walk(id);
    }
  };
  walk(null);

  const endOf = (e: Endpoint): EndRef | null => {
    switch (e.kind) {
      case 'port': {
        const p = modulePortOf.get(e.port);
        return p ? { block: null, port: p } : null;
      }
      case 'inst': {
        if (!idx.instances.has(e.id)) return null;
        const v = shown(e.id);
        if (v !== e.id) return { block: v, port: null };
        const p = instPortOf.get(e.id)?.get(e.port);
        return p ? { block: e.id, port: p } : null;
      }
      case 'node':
        return idx.nodes.has(e.id) ? { block: shown(e.id), port: null } : null;
    }
  };
  const key = (r: EndRef) => `${r.block ?? ''}#${r.port ?? ''}`;

  // Merge nets per (source, target).
  const merged = new Map<string, { source: EndRef; target: EndRef; nets: Net[] }>();
  let hiddenNets = 0;
  for (const net of m.nets) {
    if ((net.clock && !options.showClocks) || (net.control && !options.showControl)) { hiddenNets++; continue; }
    const src = endOf(net.from);
    if (!src) continue;
    for (const to of net.to) {
      const dst = endOf(to);
      if (!dst) continue;
      if (src.block !== null && src.block === dst.block && src.port === dst.port) continue; // inside a collapsed area
      const k = `${key(src)}>${key(dst)}`;
      const entry = merged.get(k) ?? { source: src, target: dst, nets: [] };
      if (!entry.nets.includes(net)) entry.nets.push(net);
      merged.set(k, entry);
    }
  }

  // Buses: the wires between the same two blocks become one, attached to a port only when all of them
  // use that port. Module ports keep their own wires (they are the module's interface).
  let groups = [...merged.values()];
  if (options.busThreshold > 0) {
    const byPair = new Map<string, typeof groups>();
    for (const g of groups) {
      if (g.source.block === null || g.target.block === null) continue;
      const k = `${g.source.block}>${g.target.block}`;
      byPair.set(k, [...(byPair.get(k) ?? []), g]);
    }
    const replaced = new Set<object>();
    const buses: typeof groups = [];
    for (const list of byPair.values()) {
      if (list.length < options.busThreshold) continue;
      list.forEach(g => replaced.add(g));
      const same = (f: (g: (typeof groups)[number]) => string | null) => list.every(g => f(g) === f(list[0])) ? f(list[0]) : null;
      buses.push({
        source: { block: list[0].source.block, port: same(g => g.source.port) },
        target: { block: list[0].target.block, port: same(g => g.target.port) },
        nets: [...new Set(list.flatMap(g => g.nets))],
      });
    }
    groups = [...groups.filter(g => !replaced.has(g)), ...buses];
  }

  const edges: VEdge[] = [];
  let i = 0;
  for (const { source, target, nets } of groups) {
    const names = nets.map(n => n.name);
    let label: string;
    if (nets.length === 1) label = names[0];
    else {
      const prefix = commonPrefix(names);
      label = prefix ? `${prefix} (${nets.length})` : `${nets.length} nets`;
    }
    edges.push({
      id: `e${i++}`, source, target, nets: nets.map(n => n.id), netNames: names, label,
      width: nets.reduce((s, n) => s + n.width, 0),
      control: nets.every(n => n.control), clock: nets.every(n => n.clock),
    });
  }

  return { module: moduleName, ports, blocks, edges, hiddenNets };
}
