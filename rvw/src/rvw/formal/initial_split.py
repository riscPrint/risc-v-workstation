"""Exhaustive initial-value case splits over an elaborated RTL variable."""
import copy
from hashlib import sha256
import json
import math
from pathlib import Path
import re

from rvw.common.proc import run_group
from .portfolio import race


def partition_model(design, top, variable, value):
    result = copy.deepcopy(design)
    module = result['modules'][top]
    bits = module['netnames'][variable]['bits']
    if not bits or any(type(b) is not int for b in bits) or len(set(bits)) != len(bits):
        raise ValueError('split variable needs distinct nonconstant bits')
    if not 0 <= value < 2**len(bits):
        raise ValueError('split value is outside variable width')
    used = [b for n in module['netnames'].values() for b in n['bits'] if type(b) is int]
    for c in module['cells'].values():
        used.extend(b for v in c['connections'].values() for b in v if type(b) is int)
    eq, init = max(used, default=1) + 1, max(used, default=1) + 2
    names = ['$rvw_split_eq', '$rvw_split_init', '$rvw_split_assume']
    if any(n in module['cells'] for n in names):
        raise ValueError('split cell name collision')
    def cell(kind, connections, directions, parameters=None):
        return {'hide_name': 0, 'type': kind, 'parameters': parameters or {}, 'attributes': {},
                'port_directions': directions, 'connections': connections}
    width = len(bits)
    module['cells'][names[0]] = cell('$eq', {'A': bits, 'B': [str((value >> i) & 1) for i in range(width)], 'Y': [eq]},
        {'A': 'input', 'B': 'input', 'Y': 'output'},
        {k: format(v, '032b') for k, v in {'A_SIGNED': 0, 'B_SIGNED': 0, 'A_WIDTH': width, 'B_WIDTH': width, 'Y_WIDTH': 1}.items()})
    module['cells'][names[1]] = cell('$initstate', {'Y': [init]}, {'Y': 'output'})
    module['cells'][names[2]] = cell('$assume', {'A': [eq], 'EN': [init]}, {'A': 'input', 'EN': 'input'})
    return result


def case_status(report, source_assumptions):
    if report['status'] == 'fail':
        return 'fail'
    proved = (report.get('mode') == 'prove' and bool(report.get('winner'))
              and report['winner']['status'] == 'pass' and report['cross_check'] != 'disagree')
    return 'pass' if proved and not source_assumptions else 'inconclusive'


def run(plan, root, out, timeout=15):
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('timeout must be finite and positive')
    top, variable = plan['top'], plan['split_variable']
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', top):
        raise ValueError('invalid top module')
    limit = plan.get('max_cases', 16)
    if type(limit) is not int or not 1 <= limit <= 256:
        raise ValueError('max_cases must be between 1 and 256')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    inputs = []
    hashes = []
    for i, source in enumerate(plan['sources']):
        raw = (Path(root) / source['path']).read_bytes()
        if source.get('format', 'verilog') != 'verilog' or sha256(raw).hexdigest() != source['sha256']:
            raise ValueError('split sources must be hash-pinned Verilog')
        if b'`include' in raw or b'$readmem' in raw:
            raise ValueError('split sources must be self-contained')
        p = out / f'input{i}.sv'
        p.write_bytes(raw)
        inputs.append(p.name)
        hashes.append(source['sha256'])
    def yosys(script, log):
        proc = run_group(['yosys', '-Q', '-T', '-p', script], cwd=out, capture=True, timeout=timeout)
        (out / log).write_text((proc.stdout or '') + (proc.stderr or ''))
        if proc.timed_out or proc.returncode:
            raise ValueError('case split elaboration failed; see ' + log)
    yosys('read -formal ' + ' '.join(inputs) + '; prep -top ' + top + '; flatten; write_json base.json', 'prepare.log')
    design = json.loads((out / 'base.json').read_text())
    module = design['modules'][top]
    if variable not in module['netnames']:
        raise ValueError('split variable is absent from the flattened design')
    width = len(module['netnames'][variable]['bits'])
    if width < 1 or width > 8 or 2**width > limit:
        raise ValueError('exhaustive split exceeds max_cases')
    source_assumptions = sum(c['type'] == '$assume' or
        (c['type'] == '$check' and c.get('parameters', {}).get('FLAVOR') == 'assume') for c in module['cells'].values())
    cases = []
    for value in range(2**width):
        model = partition_model(design, top, variable, value)
        path = out / f'case-{value}.json'
        path.write_text(json.dumps(model))
        source = out / f'case-{value}.sv'
        yosys(f'read_json {path.name}; write_verilog {source.name}', f'case-{value}-export.log')
        text = source.read_text()
        text = re.sub(r'\\\$initstate\s+[^\s]+\s*\(\s*\.Y\(([^)]+)\)\s*\);',
                      lambda m: 'assign ' + m[1] + ' = $initstate;', text)
        source.write_text(text)
        cases.append({'id': f'case-{value}', 'value': value, 'top': top, 'mode': 'prove',
                      'engines': plan.get('engines', ['abc:pdr']), 'depth': plan.get('depth', 20),
                      'sources': [{'path': source.name, 'sha256': sha256(source.read_bytes()).hexdigest()}]})
    decomposition = {'schema': 'rvw.formal-initial-split-plan/1', 'variable': variable, 'width': width,
                     'initial_values': list(range(2**width)), 'cases': cases,
                     'source_sha256': hashes, 'scope': 'exhaustive initial-state partition; full transitions in every case'}
    (out / 'plan.json').write_text(json.dumps(decomposition, indent=2) + '\n')
    rows = []
    for case in cases:
        r = race(case, out, out / case['id'], timeout=timeout)
        # The generated partition is exhaustive. Its known initial guard is the
        # only added assumption. Existing source assumptions remain unqualified.
        status = case_status(r, source_assumptions)
        rows.append({'value': case['value'], 'status': status, 'result': case['id'] + '/result.json'})
    status = 'fail' if any(r['status'] == 'fail' for r in rows) else 'pass' if all(r['status'] == 'pass' for r in rows) else 'inconclusive'
    return {'schema': 'rvw.formal-initial-split/1', 'status': status, 'rows': rows,
            'proof_kind': 'unbounded_exhaustive_initial_partition' if status == 'pass' else 'none',
            'source_assumptions': source_assumptions, 'source_sha256': hashes,
            'plan_sha256': sha256((out / 'plan.json').read_bytes()).hexdigest(),
            'limits': 'Split constraints apply only at the initial state. Every bit pattern is checked. '
                      'Source environment assumptions remain unqualified. Cases retain the full transition system.'}
