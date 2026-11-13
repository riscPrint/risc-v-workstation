/** Pure model of `rvw lint` output (rvw.lint/1 or SARIF 2.1.0) as editor diagnostics. */
export type Severity = 'error' | 'warning' | 'info' | 'hint';

export interface LintDiagnostic {
  file?: string;
  line: number;       // 1-based; 1 when unknown
  column: number;     // 1-based
  severity: Severity;
  rule: string;
  message: string;
  endpoint?: string;
  backend?: string;
  waived?: string;    // waiver reason
  id?: string;        // finding id for an exact waiver
}

export interface LintSummary {
  status: string;
  config?: string;
  top?: string;
  backends: Record<string, string>;
  diagnostics: LintDiagnostic[];
}

const ENDPOINT = /^(.*):(\d+):(\d+)$/;

function severity(s: unknown): Severity {
  return s === 'error' ? 'error' : s === 'info' || s === 'note' ? 'info' : 'warning';
}

function fromUri(uri: string): string {
  return uri.startsWith('file://') ? decodeURIComponent(uri.slice('file://'.length)) : uri;
}

function locate(f: Record<string, unknown>): Pick<LintDiagnostic, 'file' | 'line' | 'column'> {
  if (typeof f.file === 'string' && f.file) {
    return {file: f.file, line: Number(f.line) || 1, column: 1};
  }
  const m = typeof f.endpoint === 'string' ? ENDPOINT.exec(f.endpoint) : null;
  return m ? {file: m[1], line: Number(m[2]), column: Number(m[3])} : {line: 1, column: 1};
}

export function parseLint(text: string): LintSummary {
  const data = JSON.parse(text) as Record<string, unknown>;
  if (data.version === '2.1.0' && Array.isArray(data.runs)) return fromSarif(data);
  if (data.schema !== 'rvw.lint/1') {
    if (data.status === 'error') throw new Error(`rvw lint error: ${String(data.error)}`);
    throw new Error('not an rvw.lint/1 report or SARIF 2.1.0 log');
  }
  const diagnostics: LintDiagnostic[] = [];
  const backends: Record<string, string> = {};
  for (const [name, run] of Object.entries((data.backends ?? {}) as Record<string, Record<string, unknown>>)) {
    backends[name] = String(run.status);
    for (const f of (run.findings ?? []) as Record<string, unknown>[]) {
      const waived = f.disposition === 'waived' ? String(f.waiver_reason ?? '') : undefined;
      diagnostics.push({...locate(f), severity: waived !== undefined ? 'hint' : severity(f.severity),
        rule: String(f.rule), message: String(f.message ?? f.rule), endpoint: f.endpoint as string | undefined,
        backend: name, waived, id: f.id as string | undefined});
    }
  }
  for (const f of (data.waiver_findings ?? []) as Record<string, unknown>[]) {
    diagnostics.push({line: 1, column: 1, severity: 'error', rule: String(f.rule), message: String(f.message),
      endpoint: f.endpoint as string | undefined, backend: 'waivers'});
  }
  return {status: String(data.status), config: data.config as string, top: data.top as string, backends, diagnostics};
}

function fromSarif(data: Record<string, unknown>): LintSummary {
  const run = (data.runs as Record<string, unknown>[])[0] ?? {};
  const props = (run.properties ?? {}) as Record<string, unknown>;
  const diagnostics: LintDiagnostic[] = [];
  for (const r of (run.results ?? []) as Record<string, any>[]) {
    const phys = r.locations?.[0]?.physicalLocation;
    const waived = r.suppressions?.length ? String(r.suppressions[0].justification ?? '') : undefined;
    const level = r.level === 'note' ? 'info' : r.level;
    diagnostics.push({file: phys?.artifactLocation?.uri ? fromUri(phys.artifactLocation.uri) : undefined,
      line: phys?.region?.startLine ?? 1, column: phys?.region?.startColumn ?? 1,
      severity: waived !== undefined ? 'hint' : severity(level), rule: String(r.ruleId),
      message: String(r.message?.text ?? r.ruleId), endpoint: r.properties?.endpoint,
      backend: r.properties?.backend, waived, id: r.fingerprints?.['rvw/finding-id']});
  }
  return {status: String(props.status ?? 'unknown'), config: props.config as string, top: props.top as string,
    backends: (props.backends ?? {}) as Record<string, string>, diagnostics};
}

/** One status line. Only a `clean` report says clean; other states keep their name. */
export function headline(s: LintSummary): string {
  const active = s.diagnostics.filter(d => d.severity !== 'hint').length;
  const notRun = Object.entries(s.backends).filter(([, v]) => v === 'not_run').map(([k]) => k);
  return `Lint ${s.status}: ${active} active, ${s.diagnostics.length - active} waived` +
    (notRun.length ? `; not run: ${notRun.join(', ')}` : '');
}

export function messageText(d: LintDiagnostic): string {
  const where = d.endpoint && d.file ? ` [${d.endpoint}]` : d.endpoint ? ` (${d.endpoint})` : '';
  return `${d.message}${where}${d.waived !== undefined ? ` (waived: ${d.waived})` : ''}`;
}

/** The exact waiver row for a finding (settings `waivers`). The reason must be written by a person. */
export function waiver(d: LintDiagnostic, config: string | undefined): Record<string, string> {
  if (d.rule === 'lint.stale_waiver') throw new Error('remove the stale waiver instead of waiving it');
  if (!d.id || !d.endpoint || !config) throw new Error('this finding has no id, endpoint or configuration to waive');
  return {config, rule: d.rule, endpoint: d.endpoint, finding_id: d.id, reason: 'TODO: why this finding is safe'};
}

/** Keep backend and disposition on each finding, including CDC, RDC and SDC. */
export function ruleGroups(summary:LintSummary):{rule:string;findings:LintDiagnostic[]}[]{
 const groups=new Map<string,LintDiagnostic[]>();
 for(const finding of summary.diagnostics)groups.set(finding.rule,[...(groups.get(finding.rule)??[]),finding]);
 return [...groups].sort(([a],[b])=>a.localeCompare(b)).map(([rule,findings])=>({rule,findings}));
}
