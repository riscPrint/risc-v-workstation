"""Export a bounded solver query from a captured SBY model, independent of its engine."""
import json
import re
from pathlib import Path
from rvw.common.proc import run_group


def query(model, top, depth, property_name=None):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.$]*', top) or not 1 <= depth <= 10000:
        raise ValueError('unsupported top or depth')
    available = {name: index for index, name in re.findall(r"^; yosys-smt2-assert (\d+) (\S+)", model, re.M)}
    accessor = top + "_a"
    if property_name is not None:
        if property_name not in available:
            raise ValueError("property missing from captured top: " + property_name)
        accessor += " " + available[property_name]
    assumptions = {index: name for index, name in re.findall(r"^; yosys-smt2-assume (\d+) (\S+)", model, re.M)}
    constraints = {}
    lines = [model]
    def add(label, term, kind, sample):
        lines.append(f'(assert (! {term} :named {label}))')
        constraints[label] = {'kind': kind, 'sample': sample, 'signals': []}
    for step in range(depth):
        lines.append(f'(declare-fun s{step} () |{top}_s|)')
        add(f'hierarchy_{step}', f'(|{top}_h| s{step})', 'hierarchy', step)
        if not assumptions:
            add(f'assumptions_{step}', f'(|{top}_u| s{step})', 'assumptions', step)
        # Yosys uses is to distinguish initial from later samples.
        add(f'initial_flag_{step}', f'(|{top}_is| s{step})' if step == 0 else
            f'(not (|{top}_is| s{step}))', 'initial_flag', step)
        if step == 0:
            add('initial_state', f'(|{top}_i| s0)', 'initial_state', step)
        else:
            add(f'transition_{step}', f'(|{top}_t| s{step-1} s{step})', 'transition', step)
    for index, name in assumptions.items():
        term = '(and ' + ' '.join(f'(|{top}_u {index}| s{i})' for i in range(depth)) + ')'
        label = 'assumption_' + index
        add(label, term, 'assumption', None)
        constraints[label]['cell'] = name
    failures = ' '.join(f'(not (|{accessor}| s{i}))' for i in range(depth))
    add('failure', f'(or {failures})', 'any_assertion_failure', None)
    return '\n'.join(lines), {'schema': 'rvw.smt-bindings/1', 'property_id': f'{top}:{property_name or "all_assertions"}',
                              'constraints': constraints, 'depth': depth, 'top': top}


def export(result, out, capture, timeout, depth=None, property_name=None):
    root = Path(result).resolve()
    if root.is_dir():
        root /= 'result.json'
    original = json.loads(capture.file(root).copy.read_text())
    if original.get('schema') != 'rvw.formal/1' or not original.get('assertions'):
        raise ValueError('expected captured formal result with assertions')
    source = capture.file(root.parent / 'sby/model/design.il').copy
    yosys = capture.tool('yosys')
    metadata, smt = out / 'model.json', out / 'model.smt2'
    script = f'read_rtlil {json.dumps(str(source))}; flatten; chformal -lower; write_json {json.dumps(str(metadata))}; write_smt2 -wires {json.dumps(str(smt))}'
    proc = run_group([str(yosys.path), '-Q', '-T', '-p', script], capture=True, timeout=timeout)
    (out / 'export.log').write_text((proc.stdout or '') + (proc.stderr or ''))
    if proc.returncode:
        raise ValueError('captured model SMT export failed; see export.log')
    modules = json.loads(metadata.read_text())['modules']
    tops = [n for n, m in modules.items() if int(m.get('attributes', {}).get('top', '0'), 2)]
    if len(tops) != 1:
        raise ValueError('captured model needs one top')
    text, bindings = query(smt.read_text(), tops[0], depth or original['depth'], property_name)
    query_path, mapping = out / 'bounded.smt2', out / 'bindings.json'
    query_path.write_text(text)
    mapping.write_text(json.dumps(bindings, indent=2))
    return query_path, mapping, bindings
