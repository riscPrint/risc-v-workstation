import type { HierarchyNode, Loc, SearchHit, Target, ViewState, Viewport } from '../../../../SpinalBlocks/engine/src/index.ts';

export interface SavedView { state: ViewState; viewport: Viewport; labels: boolean }
export type ToWebview =
  | { type: 'load'; bytes: ArrayBuffer; saved?: SavedView }
  | { type: 'navigate'; path: string[] }
  | { type: 'search'; query: string; request: number }
  | { type: 'pick'; target: Target }
  | { type: 'openModuleSource' }
  | { type: 'showLocation'; file: string; line: number }
  | { type: 'showFsm'; module: string; fsm: string }
  | { type: 'exportImage'; format: 'svg' | 'png' };
export type FromWebview =
  | { type: 'ready' }
  | { type: 'save'; saved: SavedView }
  | { type: 'openSource'; loc: Loc }
  | { type: 'navigated'; path: string[]; modules: string[] }
  | { type: 'hierarchy'; root: HierarchyNode | null }
  | { type: 'busy'; value: boolean }
  | { type: 'error'; message: string }
  | { type: 'searchResults'; hits: SearchHit[]; request: number }
  | { type: 'export'; svg: string; name: string }
  | { type: 'exportPng'; bytes: ArrayBuffer; name: string }
  | { type: 'revealTree'; path: string[] }
  | { type: 'selected'; file: string; line: number; found: boolean; kind: 'block' | 'fsm' }
  | { type: 'find' }
  | { type: 'rendered'; path: string[]; blocks: number; theme: string; loads: number; fsm?: string };

const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object';
const strings = (v: unknown): v is string[] => Array.isArray(v) && v.every(x => typeof x === 'string');
export function isTarget(v: unknown): v is Target {
  if (!record(v)) return false;
  return v.kind === 'blockPort' ? typeof v.block === 'string' && typeof v.port === 'string'
    : ['block', 'modulePort', 'edge'].includes(String(v.kind)) && typeof v.id === 'string';
}
function hierarchy(v: unknown, depth = 0): boolean {
  return record(v) && depth <= 66 && typeof v.name === 'string' && typeof v.module === 'string'
    && strings(v.path) && Array.isArray(v.children) && v.children.every(c => hierarchy(c, depth + 1));
}
function savedView(v: unknown): v is SavedView {
  if (!record(v) || !record(v.state) || !strings(v.state.path) || !record(v.state.options) || !record(v.state.modules) || !record(v.viewport) || typeof v.labels !== 'boolean') return false;
  const { options, modules } = v.state;
  return typeof options.showClocks === 'boolean' && typeof options.showControl === 'boolean'
    && typeof options.maxBlocks === 'number' && Number.isFinite(options.maxBlocks) && options.maxBlocks > 0
    && typeof options.maxPortsPerSide === 'number' && Number.isFinite(options.maxPortsPerSide) && options.maxPortsPerSide > 0
    && Object.values(modules).every(m => record(m) && record(m.areas) && record(m.bundles) && [...Object.values(m.areas), ...Object.values(m.bundles)].every(x => typeof x === 'boolean'))
    && ['x','y','zoom'].every(k => typeof v.viewport === 'object' && Number.isFinite((v.viewport as Record<string, unknown>)[k])) && Number(v.viewport.zoom) > 0;
}
export function isFromWebview(v: unknown): v is FromWebview {
  if (!record(v)) return false;
  switch (v.type) {
    case 'ready': case 'find': return true;
    case 'save': return savedView(v.saved);
    case 'openSource': return record(v.loc) && typeof v.loc.file === 'string' && Number.isSafeInteger(v.loc.line) && Number(v.loc.line) > 0;
    case 'navigated': return strings(v.path) && strings(v.modules) && v.modules.length === v.path.length + 1;
    case 'hierarchy': return v.root === null || hierarchy(v.root);
    case 'busy': return typeof v.value === 'boolean';
    case 'error': return typeof v.message === 'string';
    case 'searchResults': return Number.isSafeInteger(v.request) && Array.isArray(v.hits) && v.hits.every(h => record(h) && typeof h.text === 'string' && typeof h.kind === 'string' && typeof h.context === 'string' && isTarget(h.target));
    case 'exportPng': return v.bytes instanceof ArrayBuffer && typeof v.name === 'string';
    case 'revealTree': return strings(v.path);
    case 'selected': return typeof v.file === 'string' && Number.isSafeInteger(v.line) && Number(v.line) > 0 && typeof v.found === 'boolean' && (v.kind === 'block' || v.kind === 'fsm');
    case 'export': return typeof v.svg === 'string' && typeof v.name === 'string';
    case 'rendered': return strings(v.path) && Number.isSafeInteger(v.blocks) && Number.isSafeInteger(v.loads) && typeof v.theme === 'string' && (v.fsm === undefined || typeof v.fsm === 'string');
    default: return false;
  }
}
export function isToWebview(v: unknown): v is ToWebview {
  if (!record(v)) return false;
  switch (v.type) {
    case 'load': return v.bytes instanceof ArrayBuffer && (v.saved === undefined || savedView(v.saved));
    case 'navigate': return strings(v.path);
    case 'search': return typeof v.query === 'string' && Number.isSafeInteger(v.request);
    case 'pick': return isTarget(v.target);
    case 'showLocation': return typeof v.file === 'string' && Number.isSafeInteger(v.line) && Number(v.line) > 0;
    case 'showFsm': return typeof v.module === 'string' && typeof v.fsm === 'string';
    case 'exportImage': return v.format === 'svg' || v.format === 'png';
    case 'openModuleSource': return true;
    default: return false;
  }
}
