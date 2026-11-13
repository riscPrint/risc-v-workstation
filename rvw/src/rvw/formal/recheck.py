"""Bounded solver what-if checks over an unchanged captured model plus pins."""
from pathlib import Path
import json
import re
import time
from rvw.common.capture import Capture
from rvw.common.proc import run_group
from . import common


def inject(model, top, pins, depth):
    """Add assumptions, rather than replace drivers. Cover a full-depth legal path."""
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.$]*', top):
        raise ValueError('unsupported model top name')
    if depth < 2:
        raise ValueError('depth must be at least two samples')
    lines = []
    def cell(kind, name, parameters, connections):
        lines.append(f'  cell {kind} \\rvwp_{name}')
        lines.extend(f'    parameter \\{key} {value}' for key, value in parameters.items())
        lines.extend(f'    connect \\{key} {value}' for key, value in connections.items())
        lines.append('  end')
    def wire(name, width=1, initial=False):
        if initial:
            lines.append(f"  attribute \\init {width}'" + '0'*width)
        lines.append(f'  wire width {width} \\rvwp_{name}')
    for i, (signal, width, value) in enumerate(pins):
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.$]*', signal):
            raise ValueError('unsupported pin signal name')
        if not 0 <= value < 2**width:
            raise ValueError('pin value does not fit signal width')
        wire(f'ok{i}')
        cell('$eq', f'eq{i}', dict(A_SIGNED=0, B_SIGNED=0, A_WIDTH=width, B_WIDTH=width, Y_WIDTH=1),
             dict(A='\\'+signal, B=f"{width}'{value:0{width}b}", Y=f'\\rvwp_ok{i}'))
        cell('$assume', f'assume{i}', {}, dict(A=f'\\rvwp_ok{i}', EN="1'1"))
    width = depth.bit_length()
    wire('age', width, initial=True)
    wire('next', width)
    wire('reached')
    cell('$add', 'increment', dict(A_SIGNED=0, B_SIGNED=0, A_WIDTH=width, B_WIDTH=width, Y_WIDTH=width),
         dict(A='\\rvwp_age', B=f"{width}'" + '0'*(width-1)+'1', Y='\\rvwp_next'))
    cell('$ff', 'age_ff', dict(WIDTH=width), dict(D='\\rvwp_next', Q='\\rvwp_age'))
    cell('$eq', 'depth', dict(A_SIGNED=0, B_SIGNED=0, A_WIDTH=width, B_WIDTH=width, Y_WIDTH=1),
         dict(A='\\rvwp_age', B=f"{width}'{depth-1:0{width}b}", Y='\\rvwp_reached'))
    cell('$cover', 'feasible', {}, dict(A='\\rvwp_reached', EN="1'1"))
    pattern = re.compile(r'(^module \\' + re.escape(top) + r'\n)(.*?)(^end\b)', re.M | re.S)
    match = pattern.search(model)
    if not match or '\\rvwp_' in model:
        raise ValueError('model top missing or reserved rvwp_ name already present')
    return model[:match.end(2)] + '\n'.join(lines) + '\n' + model[match.start(3):]


def run(args):
    root = Path(args.result).resolve()
    if root.is_dir():
        root /= 'result.json'
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    capture = Capture(out / 'inputs')
    original = json.loads(capture.file(root).copy.read_text())
    if original.get('schema') != 'rvw.formal/1' or original.get('flow') != 'bmc' or not original.get('assertions', 0):
        raise ValueError('recheck requires a captured BMC result with assertions')
    source = capture.file(root.parent / 'sby/model/design.il').copy
    yosys, sby = capture.tool('yosys'), capture.tool('sby', identity_only=True)
    deadline = time.monotonic() + args.timeout
    metadata = out / 'model.json'
    proc = run_group([str(yosys.path), '-Q', '-T', '-p', f'read_rtlil {source}; write_json {metadata}'],
                     capture=True, timeout=args.timeout)
    if proc.returncode:
        raise ValueError('cannot read captured model')
    modules = json.loads(metadata.read_text())['modules']
    tops = [name for name, mod in modules.items() if int(mod.get('attributes', {}).get('top', '0'), 2)]
    if len(tops) != 1:
        raise ValueError('captured model has no unique top')
    top = tops[0]
    pins, requested = [], []
    for entry in args.pin:
        name, raw = entry.split('=', 1)
        net = modules[top]['netnames'].get(name)
        if not net:
            raise ValueError('unresolved pin in captured flattened model: ' + name)
        value = int(raw, 0)
        pins.append((name, len(net['bits']), value))
        requested.append({'signal': name, 'value': value, 'width': len(net['bits'])})
    depth = args.depth or original['depth']
    model = out / 'pinned.il'
    model.write_text(inject(source.read_text(), top, pins, depth))
    jobs = {}
    for mode in ('cover', 'bmc'):
        path = out / f'{mode}.sby'
        script = f'read_rtlil {model}\nprep -top {top}'
        script += '\nchformal -remove -assert' if mode == 'cover' else '\nchformal -remove -cover'
        path.write_text(f'[options]\nmode {mode}\ndepth {depth}\n[engines]\n{args.engine.replace(":", " ")}\n'
                        f'[script]\n{script}\n')
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            jobs[mode] = {'status': 'timeout'}
            continue
        proc = run_group([str(sby.path), '-f', '-d', str(out / mode), str(path)], capture=True, timeout=remaining)
        (out / f'{mode}.log').write_text((proc.stdout or '') + (proc.stderr or ''))
        status_file = out / mode / 'status'
        status = status_file.read_text().strip().split()[0] if status_file.exists() else 'ERROR'
        jobs[mode] = {'status': status, 'exit_code': proc.returncode}
    legal = jobs['cover'].get('status') == 'PASS' and jobs['cover'].get('exit_code') == 0
    verdict = jobs['bmc'].get('status')
    status = 'pass' if legal and verdict == 'PASS' and jobs['bmc'].get('exit_code') == 0 else (
        'fail' if legal and verdict == 'FAIL' else 'inconclusive')
    capture.verify_tools()
    result = {'schema': 'rvw.formal-recheck/1', 'status': status, 'proof_kind': 'bounded',
              'depth': depth, 'pins': requested, 'jobs': jobs, 'restrictions': original.get('restrictions', []),
              'input_capture': capture.record(),
              'limits': 'Pins are additional all-sample assumptions. Original drivers and assertions remain. '
                        'Full-depth feasibility is required. No unbounded proof or coverage exclusion.'}
    common.write_json(out / 'result.json', result)
    print(json.dumps(result, indent=2) if args.json else status)
    return 0 if status == 'pass' else 1
