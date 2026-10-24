// State machine diagrams: Fsm (from the design) -> ELK -> FsmScene. Headless, like layout.ts.

import type { Fsm, FsmTransition, Loc } from './model.ts';
import type { ElkNode, LayoutEngine } from './layout.ts';
import type { Metrics, Point } from './scene.ts';
import { defaultMetrics, textWidth } from './scene.ts';

export interface FsmOptions {
  /** Draw transition conditions on the edges. */
  showConditions: boolean;
  /** Draw source comments on the edges. */
  showComments: boolean;
  /** Wrap condition text at about this many characters per line. */
  wrap: number;
  /** At most this many lines per condition; longer ones end in "…" (the full text is in the details). */
  maxLines: number;
}

export const defaultFsmOptions: FsmOptions = { showConditions: true, showComments: false, wrap: 36, maxLines: 4 };

export interface FsmSceneState {
  name: string;
  x: number; y: number; width: number; height: number;
  /** State after reset. */
  reset: boolean;
  /** No outgoing transitions (Sigasi: red outline). */
  dead: boolean;
  /** No transitions at all (Sigasi: red). */
  unused: boolean;
  loc: Loc | null;
}

export interface FsmSceneTransition {
  id: string;
  /** Absolute cubic Bézier paths (ELK splines): [start, c1, c2, end, c1, c2, end, ...] per section. */
  sections: Point[][];
  /** Label lines (condition, then comment), already wrapped; empty when hidden. */
  label: string[];
  /** Top-left of the label box, absolute (null when there is no label). */
  labelAt: Point | null;
  /** Target could not be determined (Sigasi: dashed arrow to "?"). */
  unresolved: boolean;
  /** From any state (assignment outside per-state branches). */
  fromAny: boolean;
  transition: FsmTransition;
}

export interface FsmScene {
  fsm: Fsm;
  width: number;
  height: number;
  states: FsmSceneState[];
  transitions: FsmSceneTransition[];
  /** Start of the dashed reset arrow (a dot), or null without a reset state. */
  resetFrom: Point | null;
  /** Reset arrow, absolute, same Bézier form as transitions. */
  resetArrow: Point[] | null;
  /** The "?" target of unresolved transitions and the "any state" source, when used. */
  unknown: { x: number; y: number; width: number; height: number } | null;
  any: { x: number; y: number; width: number; height: number } | null;
  metrics: Metrics;
}

/** Splits text into lines of about `width` characters, breaking after operators/spaces; continuation
 *  lines are indented (Sigasi wraps long conditions the same way). */
export function wrapText(text: string, width: number): string[] {
  if (text.length <= width) return [text];
  const out: string[] = [];
  let rest = text;
  while (rest.length > width) {
    let cut = -1;
    for (const sep of [' && ', ' || ', ', ', ' ']) {
      const i = rest.lastIndexOf(sep, width);
      if (i > width / 3) { cut = i + sep.length; break; }
    }
    if (cut < 0) cut = width;
    out.push(rest.slice(0, cut).trimEnd());
    rest = '  ' + rest.slice(cut).trimStart();
  }
  out.push(rest);
  return out;
}

const ANY = '__any', UNKNOWN = '__unknown', RESET = '__reset';

export async function layoutFsm(fsm: Fsm, engine: LayoutEngine, options: FsmOptions = defaultFsmOptions,
                                metrics: Metrics = defaultMetrics): Promise<FsmScene> {
  const m = metrics;
  const lineH = m.edgeLabelSize + 3;
  const outgoing = new Map<string, number>(), incoming = new Map<string, number>();
  for (const t of fsm.transitions) {
    if (t.from) outgoing.set(t.from, (outgoing.get(t.from) ?? 0) + 1);
    if (t.to) incoming.set(t.to, (incoming.get(t.to) ?? 0) + 1);
  }
  const usesAny = fsm.transitions.some(t => t.from === null);
  const usesUnknown = fsm.transitions.some(t => t.to === null);

  const cap = (lines: string[]) => lines.length <= options.maxLines ? lines : [...lines.slice(0, options.maxLines - 1), lines[options.maxLines - 1] + ' …'];
  const labelOf = (t: FsmTransition): string[] => [
    ...(options.showConditions && t.condition ? cap(wrapText(t.condition, options.wrap)) : []),
    ...(options.showComments && t.comment ? wrapText(`// ${t.comment}`, options.wrap) : []),
  ];

  const stateId = (name: string) => `s:${name}`;
  const children: ElkNode[] = fsm.states.map(s => ({
    id: stateId(s.name), width: Math.max(70, textWidth(s.name, m.titleSize, m) + 36), height: 40,
  }));
  // No layer constraint: the dot lands in the layer just before the reset state, so its arrow stays short.
  if (fsm.reset) children.push({ id: RESET, width: 10, height: 10 });
  if (usesAny) children.push({ id: ANY, width: 64, height: 26 });
  if (usesUnknown) children.push({ id: UNKNOWN, width: 30, height: 30 });

  const labels = new Map<string, string[]>();
  const edges = fsm.transitions.map((t, i) => {
    const id = `t${i}`;
    const label = labelOf(t);
    labels.set(id, label);
    return {
      id,
      sources: [t.from === null ? ANY : stateId(t.from)],
      targets: [t.to === null ? UNKNOWN : stateId(t.to)],
      labels: label.length ? [{
        id: `${id}:l`, text: label.join('\n'),
        width: Math.max(...label.map(l => textWidth(l, m.edgeLabelSize, m))) + 6, height: label.length * lineH + 2,
      }] : [],
    };
  });
  if (fsm.reset) edges.push({ id: 'reset', sources: [RESET], targets: [stateId(fsm.reset)], labels: [] });

  const graph: ElkNode = {
    id: 'fsm',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': 'DOWN',
      'elk.edgeRouting': 'SPLINES',
      'elk.layered.edgeRouting.splines.mode': 'CONSERVATIVE',
      'elk.edgeLabels.placement': 'CENTER',
      'elk.layered.edgeLabels.sideSelection': 'SMART_DOWN',
      'elk.spacing.nodeNode': '40',
      'elk.layered.spacing.nodeNodeBetweenLayers': '50',
      'elk.spacing.edgeLabel': '4',
      'elk.layered.nodePlacement.strategy': 'BRANDES_KOEPF',
      'elk.padding': '[top=20,left=20,bottom=20,right=20]',
    },
    children,
    edges: edges as unknown as ElkNode['edges'],
  };
  const laid = await engine.layout(graph);

  const pos = new Map((laid.children ?? []).map(c => [c.id, c]));
  const box = (id: string) => {
    const c = pos.get(id);
    return c ? { x: c.x ?? 0, y: c.y ?? 0, width: c.width ?? 0, height: c.height ?? 0 } : null;
  };
  const states: FsmSceneState[] = fsm.states.map(s => ({
    name: s.name, ...box(stateId(s.name))!,
    reset: fsm.reset === s.name,
    dead: !outgoing.get(s.name) && !usesAny && !!incoming.get(s.name),
    unused: !outgoing.get(s.name) && !incoming.get(s.name) && fsm.reset !== s.name,
    loc: s.loc,
  }));

  type LaidEdge = { id: string; sections?: { startPoint: Point; endPoint: Point; bendPoints?: Point[] }[]; labels?: { x?: number; y?: number }[] };
  const laidEdges = new Map(((laid.edges ?? []) as unknown as LaidEdge[]).map(e => [e.id, e]));
  const pts = (e: LaidEdge | undefined) => (e?.sections ?? []).map(s => [s.startPoint, ...(s.bendPoints ?? []), s.endPoint]);
  const transitions: FsmSceneTransition[] = fsm.transitions.map((t, i) => {
    const e = laidEdges.get(`t${i}`);
    const l = e?.labels?.[0];
    const label = labels.get(`t${i}`) ?? [];
    return {
      id: `t${i}`, sections: pts(e), label, labelAt: label.length && l ? { x: l.x ?? 0, y: l.y ?? 0 } : null,
      unresolved: t.to === null, fromAny: t.from === null, transition: t,
    };
  });
  const resetEdge = laidEdges.get('reset');
  const resetBox = box(RESET);
  return {
    fsm, width: laid.width ?? 0, height: laid.height ?? 0, states, transitions,
    resetFrom: resetBox ? { x: resetBox.x + resetBox.width / 2, y: resetBox.y + resetBox.height / 2 } : null,
    resetArrow: resetEdge ? pts(resetEdge)[0] ?? null : null,
    unknown: box(UNKNOWN), any: box(ANY), metrics: m,
  };
}
