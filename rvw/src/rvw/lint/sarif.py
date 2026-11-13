"""SARIF 2.1.0 output of a `rvw.lint/1` report, for editors and code-review tools."""
import json
from pathlib import Path
import re

LEVEL = {'error': 'error', 'warning': 'warning', 'info': 'note', 'note': 'note'}
ENDPOINT = re.compile(r'^(.*):(\d+):(\d+)$')


def location(f):
    if f.get('file'):
        loc = dict(artifactLocation=dict(uri=Path(f['file']).as_uri() if Path(f['file']).is_absolute()
                                         else f['file']))
        if f.get('line'):
            loc['region'] = dict(startLine=int(f['line']))
        return [dict(physicalLocation=loc, logicalLocations=[dict(fullyQualifiedName=f.get('endpoint') or '')])]
    m = ENDPOINT.match(f.get('endpoint') or '')
    if m:
        uri = Path(m.group(1)).as_uri() if Path(m.group(1)).is_absolute() else m.group(1)
        return [dict(physicalLocation=dict(artifactLocation=dict(uri=uri),
                                           region=dict(startLine=int(m.group(2)), startColumn=int(m.group(3)))))]
    return [dict(logicalLocations=[dict(fullyQualifiedName=f.get('endpoint') or '')])]


def convert(report):
    findings = [(b, f) for b, r in report.get('backends', {}).items() for f in r.get('findings', [])]
    findings += [('waivers', f) for f in report.get('waiver_findings', [])]
    rules = sorted({f['rule'] for _, f in findings})
    results = []
    for backend, f in findings:
        r = dict(ruleId=f['rule'], ruleIndex=rules.index(f['rule']), level=LEVEL.get(f.get('severity'), 'warning'),
                 message=dict(text=f.get('message') or f['rule']), locations=location(f),
                 properties=dict(backend=backend, endpoint=f.get('endpoint'), source=f.get('source')))
        if f.get('id'):
            r['fingerprints'] = {'rvw/finding-id': f['id']}
        if f.get('disposition') == 'waived':
            r['suppressions'] = [dict(kind='external', justification=f.get('waiver_reason', ''))]
        results.append(r)
    runs = [dict(tool=dict(driver=dict(name='rvw lint', informationUri='https://github.com/riscPrint/risc-v-workstation',
                                       rules=[dict(id=x) for x in rules])),
                 results=results,
                 properties=dict(status=report.get('status'), config=report.get('config'), top=report.get('top'),
                                 backends={b: r.get('status') for b, r in report.get('backends', {}).items()}))]
    return {'$schema': 'https://json.schemastore.org/sarif-2.1.0.json', 'version': '2.1.0', 'runs': runs}


def write(report, path):
    Path(path).write_text(json.dumps(convert(report), indent=2) + '\n')
    return str(path)
