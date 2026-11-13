"""Table-driven, single-clock formal monitors. Specifications are reviewed input."""
from argparse import Namespace
from pathlib import Path
import contextlib
import io
import json
import re

from . import common

IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')


def ident(value):
    if not isinstance(value, str) or not IDENT.fullmatch(value) or value.startswith('rvwa_'):
        raise ValueError(f'expected plain identifier: {value}')
    return value


def generate(plan, prop):
    """Build a wrapper over declared DUT ports. No hierarchical name guessing."""
    top = ident(plan['top'])
    ports = plan['ports']
    declarations = []
    for name, port in ports.items():
        ident(name)
        width = port['width']
        if type(width) is not int or not 1 <= width <= 4096 or port['direction'] not in ('input', 'output'):
            raise ValueError('ports need direction input/output and width 1..4096')
        declarations.append(f"{port['direction']} wire [{width-1}:0] {name}")
    clock, reset = ident(plan['clock']), ident(plan['reset'])
    for name in (clock, reset):
        if ports.get(name) != {'direction': 'input', 'width': 1}:
            raise ValueError('clock and active-high synchronous reset must be one-bit inputs')
    def signal(name):
        ident(name)
        if name not in ports:
            raise ValueError('unresolved endpoint: ' + name)
        return name
    def expr(value):
        # A small Boolean grammar: ports, decimal integers and operators. No calls/macros.
        if not isinstance(value, str) or not value or re.search(r'[^A-Za-z0-9_ ()!&|^~<>=+*-]', value):
            raise ValueError('unsupported expression')
        for name in IDENT.findall(value):
            signal(name)
        if re.search(r'[A-Za-z_]\w*\s*\(', value):
            raise ValueError('function calls are unsupported')
        return value
    body = []
    kind = prop['kind']
    if kind == 'connectivity':
        dest = signal(prop['destination'])
        if 'source_expression' in prop:
            if 'source' in prop:
                raise ValueError('select source or source_expression, not both')
            source, width = '(' + expr(prop['source_expression']) + ')', prop['source_width']
            if type(width) is not int or not 1 <= width <= 4096:
                raise ValueError('source_width must be 1..4096')
        else:
            source = signal(prop['source'])
            width = ports[source]['width']
        if ports[dest]['direction'] != 'output' or width != ports[dest]['width']:
            raise ValueError('destination must be an output of the same width')
        if prop.get('relation', 'required') != 'required':
            raise ValueError('forbidden connectivity needs structural/noninterference evidence; inequality is not sufficient')
        latency = prop.get('latency', 0)
        if type(latency) is not int or not 0 <= latency <= 64:
            raise ValueError('latency must be 0..64')
        enable = expr(prop.get('enable', '1'))
        mode = expr(prop.get('mode', '1'))
        guard = f'({enable}) && ({mode})'
        value = source
        for i in range(latency):
            body += [f'reg [{width-1}:0] rvwa_data{i};', f'reg rvwa_valid{i} = 0;',
                     f'always @(posedge {clock}) begin',
                     f'  rvwa_valid{i} <= !{reset} && ({guard});',
                     f'  rvwa_data{i} <= {value}; end']
            value, guard = f'rvwa_data{i}', f'rvwa_valid{i}'
        assertion = f'!({guard}) || ({dest} == {value})'
    elif kind == 'csr':
        state, write, data = (signal(prop[k]) for k in ('state', 'write_enable', 'write_data'))
        width = ports[state]['width']
        if (ports[state]['direction'] != 'output' or ports[data]['direction'] != 'input'
                or ports[write]['direction'] != 'input' or ports[data]['width'] != width
                or ports[write]['width'] != 1):
            raise ValueError('CSR needs output state, equal-width write data and one-bit write enable')
        initial = prop['reset_value']
        mask = prop.get('write_mask', (1 << width)-1)
        if any(type(v) is not int or not 0 <= v < (1 << width) for v in (initial, mask)):
            raise ValueError('CSR reset and mask must fit the register')
        access = prop.get('access', 'rw')
        if access not in ('rw', 'ro', 'w1c'):
            raise ValueError('CSR access must be rw, ro or w1c')
        update = f'(rvwa_model & ~{width}\'d{mask}) | ({data} & {width}\'d{mask})'
        if access == 'ro':
            update = 'rvwa_model'
        elif access == 'w1c':
            update = f'rvwa_model & ~({data} & {width}\'d{mask})'
        body += [f'reg [{width-1}:0] rvwa_model;', 'reg rvwa_valid = 0;',
                 f'always @(posedge {clock}) begin',
                 f' if ({reset}) begin rvwa_model <= {width}\'d{initial}; rvwa_valid <= 1; end',
                 f' else if ({write}) rvwa_model <= {update}; end']
        assertion = f'!rvwa_valid || ({state} == rvwa_model)'
    elif kind in ('deadlock', 'livelock', 'arbiter_starvation', 'handshake_progress'):
        bound = prop['bound']
        if type(bound) is not int or not 1 <= bound <= 65535:
            raise ValueError('progress bound must be 1..65535')
        if 'fairness' in prop:
            raise ValueError('fairness requires a general liveness engine; bounded progress does not model it')
        if kind == 'arbiter_starvation':
            request, grant = signal(prop['request']), signal(prop['grant'])
            if ports[request]['width'] != 1 or ports[grant]['width'] != 1:
                raise ValueError('arbiter request and grant must be one bit')
            pending, progress = request, grant
        elif kind == 'handshake_progress':
            valid, ready = signal(prop['valid']), signal(prop['ready'])
            if ports[valid]['width'] != 1 or ports[ready]['width'] != 1:
                raise ValueError('handshake valid and ready must be one bit')
            pending, progress = f'{valid} && !{ready}', f'{valid} && {ready}'
        else:
            pending, progress = expr(prop['pending']), expr(prop['progress'])
        body += [f'reg [{bound.bit_length()}:0] rvwa_age = 0;',
                 f'always @(posedge {clock}) begin',
                 f' if ({reset} || !({pending}) || ({progress})) rvwa_age <= 0;',
                 f' else if (rvwa_age < {bound}) rvwa_age <= rvwa_age + 1; end']
        assertion = f'!({pending}) || ({progress}) || rvwa_age < {bound}'
    elif kind in ('stuck_at', 'dead_code', 'fsm_state', 'fsm_transition'):
        from .automonitors import generate as auto_monitor
        extra, assertion = auto_monitor(prop, ports, signal, expr, clock, reset)
        body.extend(extra)
    elif kind == 'pmp':
        from .security.pmp import generate as pmp_monitor
        extra, assertion = pmp_monitor(prop, ports, signal, clock, reset)
        body.extend(extra)
    elif kind == 'entropy':
        from .security.entropy import generate as entropy_monitor
        extra, assertion = entropy_monitor(prop, ports, signal, clock, reset)
        body.extend(extra)
    elif kind == 'stream_stability':
        valid, ready, data = (signal(prop[k]) for k in ('valid', 'ready', 'signal'))
        if ports[valid]['width'] != 1 or ports[ready]['width'] != 1:
            raise ValueError('Stream controls must have width one')
        width = ports[data]['width']
        body += ['reg rvwa_stalled = 0;', f'reg [{width-1}:0] rvwa_payload;',
                 f'always @(posedge {clock}) begin rvwa_stalled <= !{reset} && {valid} && !{ready}; rvwa_payload <= {data}; end']
        assertion = f'!rvwa_stalled || ({valid} && {data} == rvwa_payload)'
    elif kind in ('onehot', 'mutex', 'array_bound', 'arithmetic_overflow', 'toggle', 'fifo'):
        from .app_monitors import generate as monitor
        extra, assertion = monitor(prop, ports, signal, expr, clock, reset)
        body.extend(extra)
    elif kind == 'unr':
        assertion = f'!({expr(prop["target"])})'
    else:
        raise ValueError('unsupported app kind: ' + str(kind))
    body += [f'always @(posedge {clock}) if (!{reset}) assert ({assertion});']
    return ('module rvwa_top(' + ', '.join(declarations) + ');\n' +
            f'{top} dut(' + ', '.join(f'.{n}({n})' for n in ports) + ');\n' +
            '\n'.join(body) + '\nendmodule\n')


def flow(files, top, clock, reset, out, depth, engine, timeout, mode='bmc', expected_interfaces=None, event_model=False, async_reset=False):
    from .cli import _flow
    args = Namespace(verilog=[str(p) for p in files], top=top, clock=clock, reset=reset,
                     out=str(out), depth=depth, engine=engine, timeout=timeout, mode=mode,
                     expected_interfaces=expected_interfaces or {}, checks=None, reset_active='high', reset_cycles=1, free_reset=False,
                     first_failure=True, tie=None, cut=None, event_model=event_model, event_clock=None,
                     async_reset=async_reset, frontend='verilog', json=False)
    with contextlib.redirect_stdout(io.StringIO()):
        _flow('bmc', args)
    return json.loads((Path(out) / 'result.json').read_text())


def run(args):
    path = Path(args.manifest).resolve()
    plan = json.loads(path.read_text())
    if plan.get('schema') != 'rvw.formal-apps/1':
        raise ValueError('expected rvw.formal-apps/1')
    properties = plan['properties']
    ids = [ident(p['id']) for p in properties]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError('properties need unique stable IDs')
    waivers = plan.get('waivers', {})
    if not isinstance(waivers, dict) or set(waivers) - set(ids) or any(not isinstance(reason, str) or not reason.strip() for reason in waivers.values()):
        raise ValueError('waivers need known property IDs and nonempty reasons')
    # Validate all rows before launching a solver.
    wrappers = [generate(plan, p) for p in properties]
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    # Freeze every source once, before the first property. Native flow captures tools/includes.
    files = []
    for i, source in enumerate(plan['verilog']):
        source = (path.parent / source).resolve()
        target = out / f'input{i}{source.suffix}'
        # The native snapshot captures literal include paths. Preserve their lookup directory.
        if '`include' in source.read_text():
            raise ValueError('app sources with includes need a pre-exported self-contained RTL file')
        target.write_bytes(source.read_bytes())
        files.append(target)
    common.write_json(out / 'spec.json', plan)
    rows = []
    for prop, text in zip(properties, wrappers):
        if prop['id'] in waivers:
            rows.append({'property_id': prop['id'], 'kind': prop['kind'], 'status': 'waived',
                         'reason': waivers[prop['id']], 'proof_kind': 'none'})
            continue
        wrapper = out / (prop['id'] + '.sv')
        wrapper.write_text(text)
        result = flow([*files, wrapper], 'rvwa_top', plan['clock'], plan['reset'],
                      out / prop['id'], args.depth, args.engine, args.timeout, args.mode, {plan['top']: plan['ports']},
                      getattr(args, 'event_model', False), getattr(args, 'async_reset', False))
        rows.append({'property_id': prop['id'], 'requirement_ids': prop.get('requirement_ids', []),
                     'kind': prop['kind'], 'status': result['status'],
                     'proof_kind': result['proof_kind'], 'result': f'{prop["id"]}/result.json',
                     'activation': 'not_measured', 'proof_core': 'unavailable',
                     'depth': result.get('depth'), 'module': prop.get('module', plan['top']),
                     'origin': prop.get('origin', 'hand_written'), 'source': prop.get('source')})
        from .automonitors import observation
        rows[-1]['observation'] = observation(prop['kind'], result)
    status = 'fail' if any(r['status'] == 'fail' for r in rows) else (
        'pass' if all(r['status'] == 'pass' for r in rows) else 'inconclusive')
    if all(r['status'] == 'waived' for r in rows):
        status = 'no_checks'
    if status != 'no_checks' and any(p['kind'] in ('fsm_state', 'fsm_transition', 'dead_code', 'toggle') for p in properties):
        status = 'inconclusive'  # Reachability targets use assertion failures as observations.
    report = {'schema': 'rvw.formal-app-results/1', 'status': status, 'properties': rows,
              'limits': 'Reviewed port map. Progress is a bounded response contract, '
                        'not general liveness. No activation or solver core claim. UNR app results do not '
                        'authorize exclusions; use rvw cov prove for guarded exclusion export.'}
    common.write_json(out / 'result.json', report)
    print(json.dumps(report, indent=2) if args.json else status)
    return 0 if status == 'pass' else 1
