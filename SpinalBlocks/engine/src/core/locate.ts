// From source locations to diagram elements: "Show in Block Diagram" and "Open Block Diagram" for a file.

import type { Design, Loc } from './model.ts';
import { ModuleIndex } from './model.ts';

/** What a source line points at in one module. */
export interface LocationHit {
  module: string;
  kind: 'module' | 'port' | 'instance' | 'node' | 'signal' | 'fsm' | 'state' | 'transition';
  /** Element id inside the module: port name, instance id, node id (signals: their node), fsm id. */
  id: string;
  /** Display name (the signal for kind "signal"). */
  name: string;
  loc: Loc;
}

const sameFile = (a: string, b: string) => a === b || a.endsWith('/' + b) || b.endsWith('/' + a);

/** Elements declared at `file:line`. When nothing is on that exact line, the closest declaration above it
 *  within `slack` lines (a cursor inside a multi-line statement). Exact hits come first. */
export function locate(design: Design, file: string, line: number, slack = 3): LocationHit[] {
  const exact: LocationHit[] = [];
  const near: { hit: LocationHit; d: number }[] = [];
  const consider = (hit: Omit<LocationHit, 'loc'>, loc: Loc | null) => {
    if (!loc || !sameFile(loc.file, file)) return;
    const d = line - loc.line;
    if (d === 0) exact.push({ ...hit, loc });
    else if (d > 0 && d <= slack) near.push({ hit: { ...hit, loc }, d });
  };
  for (const m of Object.values(design.modules)) {
    consider({ module: m.name, kind: 'module', id: m.name, name: m.name }, m.loc);
    for (const p of m.ports) consider({ module: m.name, kind: 'port', id: p.name, name: p.name }, p.loc);
    for (const i of m.instances) consider({ module: m.name, kind: 'instance', id: i.id, name: i.name }, i.loc);
    for (const n of m.nodes) {
      consider({ module: m.name, kind: 'node', id: n.id, name: n.name }, n.loc);
      for (const s of n.signals) consider({ module: m.name, kind: 'signal', id: n.id, name: s.name }, s.loc);
    }
    for (const f of m.fsms ?? []) {
      consider({ module: m.name, kind: 'fsm', id: f.id, name: f.name }, f.loc);
      for (const s of f.states) consider({ module: m.name, kind: 'state', id: f.id, name: s.name }, s.loc);
      for (const t of f.transitions) consider({ module: m.name, kind: 'transition', id: f.id, name: `${t.from ?? '*'} → ${t.to ?? '?'}` }, t.loc);
    }
  }
  if (exact.length) return exact;
  const best = Math.min(...near.map(n => n.d));
  return near.filter(n => n.d === best).map(n => n.hit);
}

/** Modules whose component class is defined in `file` (for "Open Block Diagram" on a Scala file). */
export function modulesDefinedIn(design: Design, file: string): string[] {
  return Object.values(design.modules).filter(m => m.loc && sameFile(m.loc.file, file)).map(m => m.name);
}

/** Instance paths (names from the top) at which `module` is instantiated, shortest first. */
export function instancePaths(design: Design, module: string, limit = 50): string[][] {
  const out: string[][] = [];
  const queue: { name: string; path: string[] }[] = [{ name: design.top, path: [] }];
  while (queue.length && out.length < limit) {
    const { name, path } = queue.shift()!;
    if (name === module) out.push(path);
    for (const i of design.modules[name]?.instances ?? []) queue.push({ name: i.module, path: [...path, i.name] });
  }
  return out;
}

/** The visible-or-not block a node lives in, for lookups that start from data ids. */
export function nodeOrInstanceExists(design: Design, module: string, id: string): boolean {
  const idx = new ModuleIndex(design, module);
  return idx.nodes.has(id) || idx.instances.has(id);
}
