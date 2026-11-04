import { resolve } from 'node:path';
import { createHash } from 'node:crypto';
export type Kind = 'regress' | 'coverage' | 'perf';
export type RecordValue = Record<string, unknown>;
export function object(value: unknown): RecordValue {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as RecordValue : {};
}
const schemas: Record<Kind, string[]> = {
  regress: ['rvw.results/1', 'rvw.verdict/2'],
  coverage: ['rvw.coverage/1', 'rvw.coverage-report/1', 'rvw.functional-coverage/1', 'rvw.coverage-error/1'],
  perf: ['rvw.perf/1', 'rvw.perf.compare/1'],
};
export function parseReport(kind: Kind, text: string): RecordValue {
  const data = object(JSON.parse(text));
  if (!schemas[kind].includes(String(data.schema))) throw new Error(`Unsupported ${kind} schema: ${String(data.schema)}`);
  return data;
}
/** These are displayed producer claims. The viewer does not issue gate verdicts. */
export function headline(kind: Kind, data: RecordValue): string {
  if (data.error) return `inconclusive: ${String(data.error)}`;
  if (kind !== 'regress') return kind === 'perf' ? 'Measurements; no correctness verdict' : 'Coverage observations; no correctness verdict';
  if (data.schema === 'rvw.verdict/2') {
    const verdict = ['accept', 'reject', 'inconclusive'].includes(String(data.verdict)) ? String(data.verdict) : 'inconclusive';
    return `Reported verdict: ${verdict}; tests: ${String(data.tests ?? 'incomplete')}`;
  }
  const tests = Array.isArray(data.tests) ? data.tests : [];
  const counts = new Map<string, number>();
  for (const test of tests) {
    const status = String(object(test).status ?? 'inconclusive');
    counts.set(status, (counts.get(status) ?? 0) + 1);
  }
  return tests.length ? `Reported tests: ${[...counts].map(([s, n]) => `${n} ${s}`).join(', ')}; no gate verdict` : 'inconclusive: no test evidence';
}
export interface Row { key: string; value: unknown; heading?: boolean }
export function children(value: unknown): Row[] {
  if (Array.isArray(value)) return value.map((v, i) => ({key: String(i), value: v}));
  return Object.entries(object(value)).map(([key, value]) => ({key, value}));
}
export function label(row: Row): string {
  if (row.value === null || typeof row.value !== 'object') return `${row.key}: ${String(row.value)}`;
  const v = object(row.value);
  const name = v.id ?? v.name ?? v.signal ?? v.path;
  return `${row.key}${name === undefined ? '' : `: ${String(name)}`}${v.status === undefined ? '' : ` [${String(v.status)}]`}`;
}
export function queryArgs(db: string, signal: string): string[] {
  return ['query', 'where', '--db', db, '--json', '--', signal];
}
export interface SourceTarget { file: string; line: number; sha256: string }
export function sourceTargets(result: unknown): SourceTarget[] {
  const r = object(result);
  if (r.error || r.status === 'inconclusive' || (Array.isArray(r.db_warnings) && r.db_warnings.length)) return [];
  const signals = Array.isArray(r.signals) ? r.signals : [r.signal];
  return signals.flatMap(signal => {
    const s = object(signal), source = object(s.source);
    if (s.pruned === true) return [];
    if (typeof s.loc !== 'string' || typeof source.sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(source.sha256)) return [];
    const match = /^(.*):(\d+)$/.exec(s.loc);
    if (!match || match[1] !== source.source || !Number.isSafeInteger(Number(match[2])) || Number(match[2]) < 1) return [];
    return [{file: match[1], line: Number(match[2]), sha256: source.sha256}];
  });
}
export function sourceMatches(target: SourceTarget, bytes: Uint8Array): boolean {
  return createHash('sha256').update(bytes).digest('hex') === target.sha256;
}

/** Use explicit producer fields only. A generic `path` can be an artifact, not a signal. */
export function rowSignal(row: Row | undefined): string | undefined {
  const value = object(row?.value);
  const signal = value.signal ?? (row?.key === 'signal' ? row.value : undefined);
  return typeof signal === 'string' && signal.trim() ? signal : undefined;
}
export function runResultPath(reportFile: string, row: Row | undefined): string | undefined {
  const run = object(row?.value).run;
  return typeof run === 'string' && run.trim() ? resolve(reportFile, '..', run, 'result.json') : undefined;
}
