"""Direct bounded engine/seed campaigns at elaborated cover cells."""
import copy
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import shutil
import time

from rvw.common.proc import run_group
from .bug_hunt import hunt


def problem(design, top, target):
    result = copy.deepcopy(design)
    module = result['modules'][top]
    cover = module['cells'][target]
    if cover['type'] != '$cover' or any(len(cover['connections'][p]) != 1 for p in ('A', 'EN')):
        raise ValueError('expected a lowered one-bit cover cell')
    if '$rvw_cover_not' in module['cells']:
        raise ValueError('cover monitor name collision')
    used = [b for n in module['netnames'].values() for b in n['bits'] if type(b) is int]
    used += [b for c in module['cells'].values() for v in c['connections'].values() for b in v if type(b) is int]
    bit = max(used, default=1) + 1
    module['cells'] = {n: c for n, c in module['cells'].items() if c['type'] not in ('$assert', '$cover', '$print')}
    module['cells']['$rvw_cover_not'] = {'hide_name': 1, 'type': '$not', 'attributes': {},
        'parameters': {k: format(v, '032b') for k, v in {'A_SIGNED': 0, 'A_WIDTH': 1, 'Y_WIDTH': 1}.items()},
        'port_directions': {'A': 'input', 'Y': 'output'}, 'connections': {'A': cover['connections']['A'], 'Y': [bit]}}
    module['cells'][target] = {**cover, 'type': '$assert', 'parameters': {},
                               'connections': {'A': [bit], 'EN': cover['connections']['EN']}}
    return result


def run(plan, root, out, *, budget=60, timeout=15):
    if any(not math.isfinite(v) or v <= 0 for v in (budget, timeout)):
        raise ValueError('budget and timeout must be finite and positive')
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', plan['top']):
        raise ValueError('invalid top module')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.monotonic() + budget
    (out / 'manifest.json').write_text(json.dumps(plan, indent=2) + '\n')
    inputs, hashes = [], []
    for i, item in enumerate(plan['sources']):
        data = (Path(root) / item['path']).read_bytes()
        digest = sha256(data).hexdigest()
        if item.get('format', 'verilog') != 'verilog' or digest != item['sha256']:
            raise ValueError('cover search requires hash-pinned Verilog')
        if b'`include' in data or b'$readmem' in data:
            raise ValueError('cover search requires self-contained sources and initial memory')
        source = out / f'input{i}.sv'
        source.write_bytes(data)
        inputs.append(source)
        hashes.append(digest)
    if not inputs:
        raise ValueError('no RTL sources')
    report = {'schema': 'rvw.formal-cover-hunt/1', 'status': 'inconclusive', 'proof_kind': 'none',
              'source_sha256': hashes, 'targets': [], 'unstarted': [], 'covered': 0,
              'preparation': ['prep -flatten', 'async2sync', 'chformal -lower'],
              'transformer_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
              'limits': 'Cover hits are bounded reachability witnesses in the captured source model. '
                        'Original safety assertions are removed from each cover job. Assumptions and '
                        'cover enables stay in place. A completed bounded schedule cannot prove '
                        'unreachability, safety, reset qualification or whole-design coverage.'}
    if not shutil.which('yosys'):
        return {**report, 'reason': 'not_installed'}
    def yosys(script, label):
        left = deadline - time.monotonic()
        if left <= 0:
            return False
        p = run_group(['yosys', '-Q', '-T', '-p', script], cwd=out, capture=True, timeout=min(timeout, left))
        (out / (label + '.log')).write_text((p.stdout or '') + (p.stderr or ''))
        return not p.timed_out and p.returncode == 0
    script = 'read -formal ' + ' '.join(json.dumps(str(p)) for p in inputs)
    script += '; prep -flatten -top ' + plan['top'] + '; async2sync; chformal -lower; write_json design.json'
    if not yosys(script, 'prepare'):
        return {**report, 'reason': 'preparation_failed'}
    design = json.loads((out / 'design.json').read_text())
    report['elaborated_sha256'] = sha256((out / 'design.json').read_bytes()).hexdigest()
    cells = design['modules'][plan['top']]['cells']
    if any(c['type'] in ('$live', '$fair') for c in cells.values()):
        return {**report, 'reason': 'liveness_constraints_unsupported'}
    available = sorted(n for n, c in cells.items() if c['type'] == '$cover')
    selected = plan.get('targets', available)
    if not isinstance(selected, list) or len(selected) != len(set(selected)) or any(n not in available for n in selected):
        raise ValueError('targets must be unique elaborated cover cell names')
    report['available'] = available
    if not selected:
        return {**report, 'reason': 'no_covers'}
    for i, target in enumerate(selected):
        left = deadline - time.monotonic()
        if left <= 0:
            break
        model = out / f'target-{i}.json'
        model.write_text(json.dumps(problem(design, plan['top'], target)))
        source = out / f'target-{i}.sv'
        if not yosys(f'read_json {model.name}; write_verilog {source.name}', f'target-{i}-export'):
            report['targets'].append({'id': target, 'status': 'inconclusive', 'reason': 'export_failed'})
            continue
        text = source.read_text()
        text = re.sub(r'\\\$initstate\s+[^\s]+\s*\(\s*\.Y\(([^)]+)\)\s*\);',
                      lambda match: 'assign ' + match[1] + ' = $initstate;', text)
        source.write_text(text)
        left = deadline - time.monotonic()
        if left <= 0:
            break
        child = {**plan, 'sources': [{'path': source.name, 'sha256': sha256(source.read_bytes()).hexdigest()}]}
        directory = out / f'search-{i}'
        result = hunt(child, out, directory, budget=left / (len(selected) - i), timeout=timeout)
        covered = result['status'] == 'fail' and result['proof_kind'] == 'counterexample'
        report['targets'].append({'id': target, 'source': cells[target].get('attributes', {}).get('src'),
                                  'status': 'covered' if covered else 'inconclusive',
                                  'proof_kind': 'bounded_reachability' if covered else 'none',
                                  'result': str(directory.relative_to(out) / 'result.json'),
                                  'attempts': result['attempts'], 'stop_reason': result['stop_reason']})
        report['covered'] += int(covered)
    report['unstarted'] = selected[len(report['targets']):]
    report['status'] = 'covered' if report['covered'] == len(selected) else 'inconclusive'
    report['proof_kind'] = 'bounded_reachability' if report['status'] == 'covered' else 'none'
    return report
