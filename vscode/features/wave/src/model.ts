/** Saved wave queries and their results. Pure code: no VS Code API, so unit tests run in Node. */
export type RecordValue = Record<string, unknown>;
export function object(value: unknown): RecordValue {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as RecordValue : {};
}

export const KINDS = ['find', 'edges', 'why', 'seq', 'txn', 'diff', 'changes', 'sample'] as const;
export type QueryKind = typeof KINDS[number];

/** A saved query file (`*.rvwq.json`): one `rvw wave` command with its options. */
export interface WaveQuery {
  schema: 'rvw.wave-query/1';
  kind: QueryKind;
  wave: string;
  /** Positional arguments after the wave: expression, regex, signal, sequence or second wave. */
  args: string[];
  /** Options without the leading dashes, e.g. {"from": "100", "db": "design.db", "indexed": true}. */
  options: Record<string, string | number | boolean>;
  title?: string;
}

const OPTION = /^[a-z][a-z0-9-]*$/;

export function parseQuery(text: string): WaveQuery {
  const q = object(JSON.parse(text));
  if (q.schema !== 'rvw.wave-query/1') throw new Error(`Unsupported wave query schema: ${String(q.schema)}`);
  if (!KINDS.includes(q.kind as QueryKind)) throw new Error(`Unknown wave query kind: ${String(q.kind)}`);
  if (typeof q.wave !== 'string' || !q.wave) throw new Error('A wave query needs a wave path');
  const args = Array.isArray(q.args) ? q.args : [];
  if (!args.every(a => typeof a === 'string')) throw new Error('Wave query args must be strings');
  const options = object(q.options);
  for (const [k, v] of Object.entries(options)) {
    if (!OPTION.test(k)) throw new Error(`Invalid option name: ${k}`);
    if (!['string', 'number', 'boolean'].includes(typeof v)) throw new Error(`Invalid option value for ${k}`);
  }
  return {schema: 'rvw.wave-query/1', kind: q.kind as QueryKind, wave: q.wave, args: args as string[],
    options: options as WaveQuery['options'], title: typeof q.title === 'string' ? q.title : undefined};
}

/** Argument array for execFile. Values never pass through a shell. */
export function queryArgv(q: WaveQuery, base?: string): string[] {
  const path = (p: string) => base && !p.startsWith('/') ? `${base}/${p}` : p;
  const argv = ['wave', q.kind, path(q.wave)];
  if (q.kind === 'diff' && q.args[0]) argv.push(path(q.args[0]));
  else argv.push(...q.args);
  for (const [k, v] of Object.entries(q.options)) {
    if (v === false) continue;
    const value = k === 'db' && typeof v === 'string' ? path(v) : String(v);
    argv.push(`--${k}`);
    if (v !== true) argv.push(value);
  }
  argv.push('--json');
  return argv;
}

/** One-line summary. It reports what the tool measured; it never turns a result into a pass. */
export function headline(kind: QueryKind, r: RecordValue): string {
  if (r.error) return `error: ${String(r.error)}`;
  switch (kind) {
    case 'find': return `${String(r.count)} intervals; first ${String(r.first)}; ${String(r.unknown_steps)} unknown steps`;
    case 'edges': return `${(Array.isArray(r.signals) ? r.signals.length : 0)} signals`;
    case 'why': return `${String(r.signal)} @ ${String(r.time)}: ${String(object(r.trace).status)} (binding unverified)`;
    case 'seq': return `${String(r.matched)} matched, ${String(r.failed)} failed, ${String(r.pending)} pending`;
    case 'txn': return `${String(r.kind)}: ${String(r.transfers)} transfers, ${String(r.issue_count)} issues, ${String(r.unknown_edges)} unknown edges`;
    case 'diff': return r.status === 'match' ? `no divergence in ${String(r.points_compared)} points (time alignment only)`
      : r.status === 'diverged' ? `first divergence at ${String(r.first_divergence)}` : 'inconclusive: no points compared';
    default: return 'wave query result';
  }
}

export interface Row { key: string; value: unknown; heading?: boolean }

/** Tree children. A `why` node shows its children trace nodes under `drivers`. */
export function children(value: unknown): Row[] {
  if (Array.isArray(value)) return value.map((v, i) => ({key: String(i), value: v}));
  return Object.entries(object(value)).map(([key, value]) => ({key, value}));
}

export function label(row: Row): string {
  if (row.heading) return row.key;
  if (row.value === null || typeof row.value !== 'object') return `${row.key}: ${String(row.value)}`;
  const v = object(row.value);
  if (typeof v.signal === 'string' && 'value' in v) {
    const at = v.set_at !== undefined && v.set_at !== null ? ` (set at ${String(v.set_at)})` : '';
    return `${v.signal} = ${String(v.value)}${at}${v.status === undefined ? '' : ` [${String(v.status)}]`}`;
  }
  if (typeof v.source === 'string' && 'holds' in v) return `:= ${v.source} [holds: ${String(v.holds)}]`;
  if (typeof v.start === 'number') return `${v.start} .. ${v.end === null ? 'end' : String(v.end)}`;
  if (typeof v.issue === 'string') return `${String(v.time)}: ${v.issue}`;
  if (typeof v.time === 'number') return `${String(v.time)}${v.wait_cycles === undefined ? '' : ` wait ${String(v.wait_cycles)}`}`;
  const name = v.signal ?? v.name ?? v.path;
  return `${row.key}${name === undefined ? '' : `: ${String(name)}`}`;
}

/** A time to open in the wave viewer: a match start, transfer, issue or divergence. */
export function rowTime(row: Row | undefined): number | undefined {
  const v = object(row?.value);
  for (const key of ['start', 'time', 'first_divergence', 'set_at', 'at']) {
    if (typeof v[key] === 'number' && Number.isSafeInteger(v[key])) return v[key] as number;
  }
  return typeof row?.value === 'number' && /time|start|first|at$/.test(row.key) ? row.value : undefined;
}

/** Signal path of a row, for cross-navigation through `rvw query where`. */
export function rowSignal(row: Row | undefined): string | undefined {
  const v = object(row?.value);
  const s = v.signal ?? (row?.key === 'signal' ? row.value : undefined);
  return typeof s === 'string' && s.trim() ? s : undefined;
}

/** Database location of an assignment row (`file:line`). The source hash is not checked here. */
export function rowLocation(row: Row | undefined): {file: string; line: number} | undefined {
  const loc = object(row?.value).loc;
  if (typeof loc !== 'string') return undefined;
  const m = /^(.*):(\d+)$/.exec(loc);
  return m && Number(m[2]) >= 1 ? {file: m[1], line: Number(m[2])} : undefined;
}

/** Window around a time for `rvw wave cut`, clamped at 0. */
export function cutArgv(wave: string, time: number, span: number, out: string): string[] {
  const from = Math.max(0, time - span);
  return ['wave', 'cut', wave, '--from', String(from), '--to', String(time + span), '-o', out, '--json'];
}

/** Summary of `rvw wave session open` output. Incomplete sessions say what is missing. */
export function sessionHeadline(r: RecordValue): string {
  if (r.error) return `error: ${String(r.error)}`;
  const artifacts = Object.entries(object(r.artifacts));
  const bad = artifacts.filter(([, v]) => object(v).status !== 'ok').map(([k, v]) => `${k} ${String(object(v).status)}`);
  const missing = Array.isArray(r.missing_signals) ? r.missing_signals.length : 0;
  return r.status === 'complete' ? `session complete: ${artifacts.length} artifacts verified`
    : `session incomplete: ${[...bad, ...(missing ? [`${missing} signals missing`] : [])].join(', ')}`;
}

/** An embedded saved query of a session row, or undefined. */
export function rowQuery(row: Row | undefined): WaveQuery | undefined {
  const v = object(row?.value);
  if (v.schema !== 'rvw.wave-query/1') return undefined;
  try { return parseQuery(JSON.stringify(v)); } catch { return undefined; }
}
