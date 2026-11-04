"""Acyclic assume-guarantee jobs with a closed, assumption-free composition check.

This is a safety flow. Source RTL assumptions remain explicit environment restrictions.
"""
from argparse import Namespace
import contextlib
import sys
import hashlib
import json
import math
from pathlib import Path
import re
import time

IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*\Z')


def ident(value):
    if not isinstance(value, str) or not IDENT.fullmatch(value) or value.startswith('rvw_'):
        raise ValueError(f'invalid contract identifier: {value!r}')
    return value


def validate(plan):
    """Require exact predicate identity, one driver, input provenance and an acyclic graph."""
    signals = plan['signals']
    if not signals or any(ident(k) in ('clk', 'reset') or type(w) is not int or not 1 <= w <= 65536
                          for k, w in signals.items()):
        raise ValueError('signals need positive widths; clk/reset are reserved')
    predicates = plan['predicates']
    for name, expr in predicates.items():
        ident(name)
        # Restricted combinational expression language. No calls, hierarchy, macros or statements.
        if not isinstance(expr, str) or not expr or re.search(r'[^A-Za-z0-9_\s&|!~<>=+*%/^?:()\[\]-]', expr):
            raise ValueError('predicate must be a combinational expression')
        words = re.findall(r'[A-Za-z_][A-Za-z0-9_]*', expr)
        if any(w not in signals for w in words) or re.search(r'[A-Za-z_]\w*\s*\(', expr):
            raise ValueError('predicate uses unknown signal or function')
    nodes = plan['components']
    ids, drivers, providers = {}, {}, {}
    for node in nodes:
        name = ident(node['id'])
        ident(node['top'])
        if name == 'closed' or name in ids:
            raise ValueError('duplicate component')
        ids[name] = node
        for direction in ('inputs', 'outputs'):
            for sig in node[direction]:
                if sig not in signals:
                    raise ValueError('unknown interface signal')
                if direction == 'outputs':
                    if sig in drivers:
                        raise ValueError('multiple interface drivers')
                    drivers[sig] = name
        if set(node['inputs']) & set(node['outputs']):
            raise ValueError('interface direction conflict')
        if not node['guarantees']:
            raise ValueError('each component needs guarantees')
        for pred in node['guarantees']:
            if pred in providers or pred not in predicates:
                raise ValueError('guarantee needs one provider and a known predicate')
            providers[pred] = name
        for pred in node['guarantees'] + node['assumes']:
            if pred not in predicates:
                raise ValueError('unknown predicate')
            used = set(re.findall(r'[A-Za-z_]\w*', predicates[pred]))
            if not used <= set(node['inputs'] + node['outputs']):
                raise ValueError('predicate is outside component interface')
    visiting, done, order = set(), set(), []
    def visit(name):
        if name in visiting:
            raise ValueError('circular assume-guarantee dependency')
        if name in done:
            return
        visiting.add(name)
        for pred in ids[name]['assumes']:
            if pred not in providers or providers[pred] == name:
                raise ValueError('assumption has no neighbour guarantee')
            used = set(re.findall(r'[A-Za-z_]\w*', predicates[pred]))
            if not used <= set(ids[name]['inputs']):
                raise ValueError('assumptions must use inputs only')
            visit(providers[pred])
        visiting.remove(name)
        done.add(name)
        order.append(name)
    for name in ids:
        visit(name)
    if not nodes:
        raise ValueError('empty composition')
    return order


def harness(plan, selected=None):
    nodes = [n for n in plan['components'] if selected is None or n['id'] == selected]
    outputs = {s for n in nodes for s in n['outputs']}
    signals = {s for n in nodes for s in n['inputs'] + n['outputs']}
    decl = lambda s: f'[{plan["signals"][s]-1}:0] {s}'
    ports = ['input clk', 'input reset'] + ['input ' + decl(s) for s in sorted(signals - outputs)]
    lines = ['module rvw_contract(' + ', '.join(ports) + ');']
    lines += ['wire ' + decl(s) + ';' for s in sorted(outputs)]
    for node in nodes:
        names = ['clk', 'reset'] + node['inputs'] + node['outputs']
        lines.append(f'{node["top"]} {node["id"]} (' + ','.join(f'.{s}({s})' for s in names) + ');')
        for pred in node['assumes'] if selected else []:
            lines.append(f'always @(posedge clk) if (!reset) assume({plan["predicates"][pred]});')
        for pred in node['guarantees']:
            lines.append(f'always @(posedge clk) if (!reset) assert({plan["predicates"][pred]});')
    return '\n'.join(lines) + '\nendmodule\n'


def check_ports(plan, model):
    """Reject implicit width changes, missing ports and direction errors."""
    for node in plan['components']:
        ports = model['modules'][node['top']]['ports']
        expected = {'clk': ('input', 1), 'reset': ('input', 1)}
        for key, direction in (('inputs', 'input'), ('outputs', 'output')):
            expected.update({sig: (direction, plan['signals'][sig]) for sig in node[key]})
        actual = {name: (p['direction'], len(p['bits'])) for name, p in ports.items()}
        if actual != expected:
            raise ValueError(f"{node['id']}: RTL interface differs from typed contract")


def run(args):
    from .cli import _flow
    from .snapshot import InputSnapshot
    if not math.isfinite(args.budget) or args.budget <= 0:
        raise ValueError('budget must be finite and positive')
    out = Path(args.out).absolute()
    out.mkdir(parents=True, exist_ok=False)
    raw = Path(args.manifest).read_bytes()
    plan = json.loads(raw)
    order = validate(plan)
    (out / 'plan.json').write_bytes(raw)
    # Capture all RTL and literal includes once, before any proof starts.
    source_args = Namespace(verilog=[str(Path(args.manifest).absolute().parent / f) for f in plan['verilog']], checks=None)
    (out / 'source').mkdir()
    snapshot = InputSnapshot(source_args, out / 'source')
    rows = []
    deadline = time.monotonic() + args.budget
    for name in order + ['closed']:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            rows.append({'id': name, 'status': 'inconclusive', 'reason': 'budget exhausted'})
            continue
        wrapper = out / f'{name}.sv'
        wrapper.write_text(harness(plan, None if name == 'closed' else name))
        child = Namespace(verilog=[str(p) for p in snapshot.sources] + [str(wrapper)],
                          top='rvw_contract', clock='clk', reset='reset', reset_active='high',
                          reset_cycles=1, free_reset=False, event_model=False, event_clock=None,
                          async_reset=False, checks=None, depth=args.depth, mode='prove',
                          engine=args.engine, timeout=remaining, first_failure=True, cut=None,
                          tie=None, out=str(out / name), json=False, project=None)
        with contextlib.redirect_stdout(sys.stderr):
            _flow('bmc', child)
        if name == 'closed':
            check_ports(plan, json.loads((out / name / 'module_ports.json').read_text()))
        result = json.loads((out / name / 'result.json').read_text())
        rows.append({'id': name, 'status': result['status'], 'proof_kind': result['proof_kind'],
                     'result': str(out / name / 'result.json')})
    passed = all(r['status'] == 'pass' and r.get('proof_kind') == 'unbounded' for r in rows)
    result = {'schema': 'rvw.formal-contracts/1', 'status': 'conditional_proved' if passed else 'inconclusive',
              'plan_sha256': hashlib.sha256(raw).hexdigest(), 'obligations': rows,
              'restrictions': ['Source RTL assumptions remain environment restrictions.',
                               'Reset is active for one step, then inactive.',
                               'No liveness or per-predicate activation proof.'],
              'input_capture': snapshot.capture.record()}
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    if args.json:
        print(json.dumps(result))
    return 0 if passed else 1
