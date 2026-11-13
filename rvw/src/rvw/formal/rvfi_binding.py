"""Generate a riscv-formal project from a core-owned RVFI port binding."""
import json
import os
from pathlib import Path
import re

from .riscv import FIELDS


def ident(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_$]*', value):
        raise ValueError('binding needs plain Verilog identifiers')
    return value


def wrapper(plan):
    if plan.get('schema') != 'rvw.rvfi-binding/1':
        raise ValueError('expected rvw.rvfi-binding/1')
    top, clock, reset = (ident(plan[k]) for k in ('top', 'clock', 'reset'))
    if top == 'rvfi_wrapper':
        raise ValueError('rvfi_wrapper is reserved')
    ports = plan['ports']
    if not isinstance(ports, dict) or set(ports) != set(FIELDS):
        raise ValueError('ports must map every RVFI field')
    names = [clock, reset, *ports.values()]
    lines = ['module rvfi_wrapper(input clock, input reset, `RVFI_OUTPUTS);']
    locals = {}
    conns = [f'.{clock}(clock)', f'.{reset}(reset)']
    for direction in ('inputs', 'outputs'):
        for i, (port, width) in enumerate(plan.get(direction, {}).items()):
            names.append(ident(port))
            if type(width) is not int or not 1 <= width <= 65536:
                raise ValueError('port width must be 1..65536')
            local = f'bound_{direction}_{i}'
            locals[port] = local
            declaration = '(* anyseq *) reg' if direction == 'inputs' else 'wire'
            lines.append(f'{declaration} [{width - 1}:0] {local};')
            conns.append(f'.{port}({local})')
    for name in names:
        ident(name)
    if len(set(names)) != len(names):
        raise ValueError('DUT ports must be distinct')
    from .bus_environment import render
    environment, _ = render(plan, locals)
    lines.extend(environment)
    lines += [f'{top} dut(' + ',\n'.join(conns) + ',\n@RVFI_CONNECTIONS@);', 'endmodule']
    return '\n'.join(lines) + '\n'


def generate(manifest, out):
    from .riscv import validate
    manifest, out = Path(manifest).resolve(), Path(out).resolve()
    plan = json.loads(manifest.read_text())
    text = wrapper(plan)
    # All core names and signal names come from this project-owned file.
    cfg = {k: plan[k] for k in ('isa', 'nret', 'checks', 'depth', 'solver', 'ports')}
    for key in ('defines', 'check_options', 'multiclock'):
        if key in plan:
            cfg[key] = plan[key]
    cfg['root'] = str((manifest.parent / os.path.expandvars(plan['root'])).resolve())
    cfg['verilog'] = [str((manifest.parent / os.path.expandvars(p)).resolve()) for p in plan['verilog']]
    out.mkdir(parents=True, exist_ok=False)
    cfg['wrapper'] = str(out / 'wrapper.sv.in')
    Path(cfg['wrapper']).write_text(text)
    validate(cfg)
    lines = ['[core]', 'name = ' + json.dumps(plan.get('name', plan['top'])), '', '[riscv_formal]']
    for key, value in cfg.items():
        if key not in ('ports', 'check_options'):
            lines.append(key + ' = ' + json.dumps(value))
    lines += ['', '[riscv_formal.ports]']
    lines += [key + ' = ' + json.dumps(value) for key, value in cfg['ports'].items()]
    for check, options in cfg.get('check_options', {}).items():
        lines += ['', '[riscv_formal.check_options.' + check + ']']
        lines += [key + ' = ' + json.dumps(value) for key, value in options.items()]
    (out / 'rvw.toml').write_text('\n'.join(lines) + '\n')
    import hashlib
    result = dict(schema='rvw.rvfi-generation/1', status='generated',
                  manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
                  project=str(out / 'rvw.toml'), wrapper=cfg['wrapper'],
                  bus_environment=plan.get('bus_environment', []),
                  environment_constants=plan.get('environment_constants', {}),
                  limits='Explicit bus assumptions restrict the environment. Other auxiliary inputs are unconstrained. Review adapter semantics before proof.')
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main(args):
    try:
        result = generate(args.manifest, args.out)
        print(json.dumps(result) if args.json else result['project'])
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps(dict(status='error', error=str(exc))))
        return 2
