// The diagram data written by the Scala extractor (docs/FORMAT.md).

export interface Loc { file: string; line: number }

export interface Port {
  name: string;
  dir: 'in' | 'out' | 'inout';
  width: number;
  type: string;
  group: string;
  groups: string[];
  loc: Loc | null;
}

export interface Instance {
  id: string;
  name: string;
  module: string;
  parent: string | null;
  loc: Loc | null;
}

export interface Signal { name: string; width: number; type: string; reg: boolean; loc: Loc | null }

export type NodeKind = 'area' | 'logic' | 'reg' | 'comb' | 'mixed' | 'mem';

export interface LogicNode {
  id: string;
  name: string;
  kind: NodeKind;
  parent: string | null;
  compound: boolean;
  className: string | null;
  loc: Loc | null;
  signals: Signal[];
  regCount: number;
  combCount: number;
}

export type Endpoint =
  | { kind: 'port'; port: string }
  | { kind: 'inst'; id: string; port: string }
  | { kind: 'node'; id: string };

export interface Net {
  id: string;
  name: string;
  width: number;
  via: string[];
  control: boolean;
  clock: boolean;
  from: Endpoint;
  to: Endpoint[];
}

/** A state of a state machine (docs/FORMAT.md, "State machines"). */
export interface FsmState { name: string; loc: Loc | null }

export interface FsmTransition {
  /** Source state; null = from any state (assignment outside a per-state branch). */
  from: string | null;
  /** Target state; null = unresolved (not a constant). */
  to: string | null;
  /** The condition as Spinal-ish source text, without the "in state X" part; null = always. */
  condition: string | null;
  /** Comment on the `goto`/assignment line, if any. */
  comment: string | null;
  loc: Loc | null;
}

export interface Fsm {
  id: string;
  name: string;
  /** Logic node (area) that holds the state register. */
  node: string | null;
  /** The state register. */
  register: string;
  /** spinal.lib StateMachine, or a plain enum register. */
  kind: 'statemachine' | 'enum';
  loc: Loc | null;
  states: FsmState[];
  /** State after reset (register init / StateMachine entry), or null. */
  reset: string | null;
  transitions: FsmTransition[];
}

export interface Module {
  name: string;
  className: string;
  loc: Loc | null;
  instanceCount: number;
  blackbox: boolean;
  ports: Port[];
  instances: Instance[];
  nodes: LogicNode[];
  nets: Net[];
  /** State machines in this module (absent in older files). */
  fsms?: Fsm[];
}

export interface Design {
  format: 'spinalblocks';
  version: number;
  top: string;
  generated?: string;
  modules: Record<string, Module>;
}

/** Parses a design from JSON text, file bytes (plain or gzipped, i.e. a `.json` or `.json.gz` file), or an
 *  already parsed value. */
export async function loadDesign(input: string | Uint8Array | ArrayBuffer | unknown): Promise<Design> {
  let value: unknown = input;
  if (input instanceof ArrayBuffer) value = new Uint8Array(input);
  if (value instanceof Uint8Array) {
    const gzipped = value.length > 2 && value[0] === 0x1f && value[1] === 0x8b;
    value = gzipped ? await gunzip(value) : new TextDecoder().decode(value);
  }
  if (typeof value === 'string') value = JSON.parse(value);
  const d = value as Design;
  if (!d || d.format !== 'spinalblocks' || typeof d.modules !== 'object' || !d.modules[d.top]) {
    throw new Error('not a SpinalBlocks design (expected format "spinalblocks" with a top module)');
  }
  if (d.version !== 1) throw new Error(`unsupported SpinalBlocks format version ${d.version}`);
  return d;
}

async function gunzip(bytes: Uint8Array): Promise<string> {
  const stream = new Blob([bytes as BlobPart]).stream().pipeThrough(new DecompressionStream('gzip'));
  return await new Response(stream).text();
}

/** Id of the virtual area that groups a module's loose logic (see ModuleIndex). */
export const GLUE_ID = 'area:(glue)';

/** Loose logic blocks needed before they are grouped into one glue area. */
const GLUE_MIN = 6;

/** Lookup tables for one module.
 *
 *  When a module has instances and also many logic blocks outside any area (BOOM's core: 23 instances,
 *  80 small register groups), those blocks are put in a virtual area `GLUE_ID` ("glue logic"), so the
 *  instances stay readable; it collapses and expands like any area. Everything that reads the module's
 *  structure goes through this index, so it sees the same grouping. */
export class ModuleIndex {
  readonly design: Design;
  readonly module: Module;
  /** All logic nodes including the glue area, in data order. */
  readonly nodeList: LogicNode[];
  readonly nodes = new Map<string, LogicNode>();
  readonly instances = new Map<string, Instance>();
  readonly ports = new Map<string, Port>();
  readonly nets = new Map<string, Net>();
  /** Area id -> child node ids and instance ids. */
  readonly children = new Map<string | null, string[]>();

  constructor(design: Design, name: string) {
    this.design = design;
    const m = design.modules[name];
    if (!m) throw new Error(`unknown module ${name}`);
    this.module = m;
    const loose = m.nodes.filter(n => n.parent === null && !n.compound && n.kind !== 'area');
    if (m.instances.length >= 2 && loose.length >= GLUE_MIN) {
      const looseIds = new Set(loose.map(n => n.id));
      const glue: LogicNode = {
        id: GLUE_ID, name: 'glue logic', kind: 'area', parent: null, compound: true, className: null, loc: null,
        signals: [], regCount: loose.reduce((a, n) => a + n.regCount, 0), combCount: loose.reduce((a, n) => a + n.combCount, 0),
      };
      this.nodeList = [glue, ...m.nodes.map(n => looseIds.has(n.id) ? { ...n, parent: GLUE_ID } : n)];
    } else this.nodeList = m.nodes;
    for (const n of this.nodeList) this.nodes.set(n.id, n);
    for (const i of m.instances) this.instances.set(i.id, i);
    for (const p of m.ports) this.ports.set(p.name, p);
    for (const n of m.nets) this.nets.set(n.id, n);
    const add = (parent: string | null, id: string) => {
      const list = this.children.get(parent) ?? [];
      list.push(id);
      this.children.set(parent, list);
    };
    for (const n of this.nodeList) add(n.parent, n.id);
    for (const i of m.instances) add(i.parent, i.id);
  }

  /** Parent area of a node or instance. */
  parentOf(id: string): string | null {
    return this.nodes.get(id)?.parent ?? this.instances.get(id)?.parent ?? null;
  }

  /** Areas enclosing `id`, innermost first. */
  ancestors(id: string): string[] {
    const out: string[] = [];
    for (let p = this.parentOf(id); p; p = this.parentOf(p)) out.push(p);
    return out;
  }

  /** Nesting depth of an area (0 = in the module body). */
  depth(id: string): number {
    return this.ancestors(id).length;
  }
}

/** Instance path from the top: ["core", "rob"] -> module names along the way. Returns null when invalid. */
export function resolvePath(design: Design, path: string[]): string[] | null {
  const modules = [design.top];
  for (const instName of path) {
    const m = design.modules[modules[modules.length - 1]];
    const inst = m.instances.find(i => i.name === instName);
    if (!inst || !design.modules[inst.module]) return null;
    modules.push(inst.module);
  }
  return modules;
}
