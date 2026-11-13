"""IPC comparisons require successful repeated RTL measurements."""
import json
import math
from pathlib import Path


def compare(a, b):
    tables = [json.loads(Path(p).read_text()) for p in (a, b)]
    if any(t.get('schema') != 'rvw.rtl-bench/1' for t in tables):
        raise ValueError('expected two rvw.rtl-bench/1 tables')
    maps = [{r['program']: r for r in t['workloads']} for t in tables]
    rows = []
    for name in sorted(set(maps[0]) | set(maps[1])):
        left, right = (m.get(name) for m in maps)
        row = {'program': name, 'status': 'inconclusive', 'ipc_delta': None,
               'ipc_delta_pct': None, 'topdown_delta': None}
        if left is None or right is None:
            row['reason'] = 'program missing from one table'
        elif any(r.get('status') != 'pass' for r in (left, right)):
            row['reason'] = 'program did not pass in both tables'
        elif left.get('instructions') != right.get('instructions'):
            row['reason'] = 'instruction counts differ; compare program inputs and ISA'
        else:
            values = [r.get('ipc') for r in (left, right)]
            if not all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in values):
                row['reason'] = 'missing or invalid IPC'
            else:
                row['base_ipc'], row['candidate_ipc'] = values
                row['ipc_delta'] = values[1] - values[0]
                row['ipc_delta_pct'] = 100 * (values[1] / values[0] - 1)
                deterministic = all(_deterministic(r) for r in (left, right))
                row['noise_check'] = 'deterministic' if deterministic else 'unverified'
                row['status'] = 'compared' if deterministic else 'inconclusive'
                if not deterministic:
                    row['reason'] = 'both tables need at least two identical passing samples'
                td = [r.get('topdown') for r in (left, right)]
                if all(td):
                    if td[0]['unit'] == td[1]['unit']:
                        row['topdown_delta'] = {k: td[1]['fractions'][k] - td[0]['fractions'][k]
                                                for k in td[0]['fractions']}
                # Different binaries are explicit, even with the same retired count.
                row['same_elf'] = left.get('elf_sha256') == right.get('elf_sha256')
        rows.append(row)
    return {'schema': 'rvw.rtl-bench-compare/1', 'status': 'compared' if rows and all(
        r['status'] == 'compared' for r in rows) else 'inconclusive', 'workloads': rows}


def _deterministic(row):
    samples = row.get('samples', [])
    return len(samples) >= 2 and all(s.get('status') == 'pass' and
        (s.get('instructions'), s.get('cycles')) == (row.get('instructions'), row.get('cycles'))
        for s in samples)


def render(result):
    classes = ('retiring', 'bad_speculation', 'frontend_bound', 'backend_bound')
    topdown = any(r.get('topdown_delta') for r in result['workloads'])
    header = ['Program', 'IPC A', 'IPC B', 'Delta (%)', 'Noise', 'Status']
    if topdown:
        header += [c + ' delta (pp)' for c in classes]
    lines = ['| ' + ' | '.join(header) + ' |', '|' + '---|' * len(header)]
    for r in result['workloads']:
        values = [r['program'], r.get('base_ipc'), r.get('candidate_ipc'), r['ipc_delta_pct'],
                  r.get('noise_check', 'unverified'), r['status']]
        if topdown:
            delta = r.get('topdown_delta') or {}
            values += [round(100 * delta[c], 4) if c in delta else None for c in classes]
        lines.append('| ' + ' | '.join(map(str, values)) + ' |')
    return '\n'.join(lines)
