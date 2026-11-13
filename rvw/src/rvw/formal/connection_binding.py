"""Expose captured internal RTL observations without cutting their drivers."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re

from .common import check_path, run


def top_ports(db):
    return {s.name:s for s in db.signals_where('s.direction IS NOT NULL AND s.pruned=0')
            if db.component(s.component_id)['parent_id'] is None}


def expose(db, declaration, files, out, timeout):
    """Required value transfers can observe internal nets. No abstraction cut."""
    ports = top_ports(db)
    existing = {s.id for s in ports.values()}
    signals = {db.resolve_one(declaration[k]).id:db.resolve_one(declaration[k])
               for k in ('source','destination','mode','enable') if k in declaration}
    internal = [s for sid,s in signals.items() if sid not in existing]
    if not internal:
        return files, ports, None
    if declaration['kind'] != 'required':
        raise ValueError('internal forbidden influence needs a state-coupling backend')
    identifier = r'[A-Za-z_][A-Za-z0-9_$]*'
    if not re.fullmatch(identifier, db.top):
        raise ValueError('internal binding needs a plain top module name')
    out = Path(out)
    out.mkdir()
    reads = '\n'.join(f'read_verilog -formal -sv {check_path("RTL", f)}' for f in files)
    (out/'flatten.ys').write_text(reads + f'\nhierarchy -check -top {db.top}\nproc\nflatten\n'
                                f'write_json -noscopeinfo {out}/flatten.json\nwrite_rtlil {out}/flatten.il\n')
    try:
        rc, _ = run(['yosys','-Q','-T','-s','flatten.ys'],out,out/'flatten.log',timeout)
    except OSError as exc:
        raise ValueError('internal binding needs Yosys') from exc
    if rc or not (out/'flatten.json').is_file():
        raise ValueError('internal RTL flattening failed; see binding/flatten.log')
    module = json.loads((out/'flatten.json').read_text())['modules'][db.top]
    rtl_ports = module['ports']
    if set(rtl_ports) != set(ports):
        raise ValueError('captured RTL top ports differ from the database')
    for name, signal in ports.items():
        port = rtl_ports[name]
        if len(port['bits']) != signal.width or port['direction'] != {'in':'input','out':'output','inout':'inout'}[signal.direction]:
            raise ValueError('captured RTL port type differs from the database')
    commands, bindings = [], []
    for i, signal in enumerate(internal):
        name = signal.path.removeprefix(db.top + '.')
        if not re.fullmatch(identifier + r'(?:\.' + identifier + ')*',name):
            raise ValueError('internal signal path is not supported by the binding backend')
        net = module['netnames'].get(name)
        if net is None or len(net['bits']) != signal.width:
            raise ValueError('internal RTL signal missing or width differs from database: ' + signal.path)
        alias = f'rvw_conn_observe_{i}'
        if alias in module['netnames']:
            raise ValueError('reserved internal observation alias already exists')
        commands += [f'rename {name} {alias}',f'expose w:{alias}']
        ports[alias] = replace(signal,name=alias,direction='out')
        bindings.append(dict(signal=signal.path,port=alias,width=signal.width))
    (out/'expose.ys').write_text(f'read_rtlil {out}/flatten.il\ncd {db.top}\n' + '\n'.join(commands) +
                               f'\ncd ..\nwrite_verilog -noattr {out}/observed.v\nwrite_json -noscopeinfo {out}/observed.json\n')
    rc, _ = run(['yosys','-Q','-T','-s','expose.ys'],out,out/'expose.log',timeout)
    if rc or not (out/'observed.v').is_file():
        raise ValueError('internal RTL exposure failed; see binding/expose.log')
    observed = json.loads((out/'observed.json').read_text())['modules'][db.top]
    for entry in bindings:
        port = observed['ports'].get(entry['port'])
        if not port or port['direction'] != 'output' or len(port['bits']) != entry['width']:
            raise ValueError('internal observation interface was not preserved')
    target = out/'observed.v'
    identity = dict(backend='yosys flatten and expose; drivers retained',bindings=bindings,
                    derived_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                    source_sha256={str(p):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in files})
    (out/'binding.json').write_text(json.dumps(identity,indent=2)+'\n')
    return [str(target)], ports, identity
