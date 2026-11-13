"""Expose captured RTL observations, with optional source-cut SoC cones."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re

from .common import check_path, run


def top_ports(db):
    return {s.name:s for s in db.signals_where('s.direction IS NOT NULL AND s.pruned=0')
            if db.component(s.component_id)['parent_id'] is None}


def expose(db, declaration, files, out, timeout, *, cone_cut=False):
    """Observe required transfers. The default retains every driver."""
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
    original_files = files
    abstractions = []
    if cone_cut:
        from rvw.soc.connection_cone import abstract_modules
        files, abstractions = abstract_modules(db, declaration, files, out)
    read_options = '-formal -noblackbox -sv' if cone_cut else '-formal -sv'
    reads = '\n'.join(f'read_verilog {read_options} {check_path("RTL", f)}' for f in files)
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
    if cone_cut:
        # A free source strengthens the transfer obligation. Keep clock/reset
        # aliases connected to their original primary inputs.
        source = db.resolve_one(declaration['source'])
        source_port = next(p for p in ports.values() if p.id == source.id)
        source_net = module['netnames'][source.path.removeprefix(db.top + '.')]['bits']
        primary_bits = {b for p in rtl_ports.values() if p['direction'] == 'input' for b in p['bits']}
        if not set(source_net) & primary_bits:
            if any(not isinstance(b, int) for b in source_net):
                raise ValueError('cannot cut a constant source')
            # JSON uses canonical bit IDs. Disconnect the actual driver, not
            # just one named alias of the source wire.
            netlist = json.loads((out/'flatten.json').read_text())
            mod = netlist['modules'][db.top]
            fresh = max(b for n in mod['netnames'].values() for b in n['bits'] if isinstance(b,int))+1
            cut_bits = set(source_net)
            for cell in mod['cells'].values():
                for pin, direction in cell['port_directions'].items():
                    if direction != 'output':
                        continue
                    bits = cell['connections'][pin]
                    for index, bit in enumerate(bits):
                        if bit in cut_bits:
                            bits[index] = fresh
                            fresh += 1
            mod['ports']['rvw_cut_source'] = dict(direction='input',bits=source_net)
            mod['netnames']['rvw_cut_source'] = dict(hide_name=0,bits=source_net,attributes={})
            (out/'cut.json').write_text(json.dumps(netlist))
            ports['rvw_cut_source'] = replace(source, id=-1, name='rvw_cut_source', direction='in')
        observed_ids = set(signals)
        for name, port in list(ports.items()):
            if port.direction == 'out' and port.id not in observed_ids:
                commands.append(f'delete -output w:{name}')
                del ports[name]
        commands += ['delete t:$assert t:$assume t:$cover t:$check t:$live t:$fair', 'setattr -unset keep w:* c:*', 'opt -full', 'opt_clean -purge']
    reader = f'read_json {out}/cut.json' if (out/'cut.json').exists() else f'read_rtlil {out}/flatten.il'
    writer_options = '-norename' if cone_cut else '-noattr'
    (out/'expose.ys').write_text(f'{reader}\ncd {db.top}\n' + '\n'.join(commands) +
                               f'\ncd ..\nwrite_verilog {writer_options} {out}/observed.v\nwrite_json -noscopeinfo {out}/observed.json\n')
    rc, _ = run(['yosys','-Q','-T','-s','expose.ys'],out,out/'expose.log',timeout)
    if rc or not (out/'observed.v').is_file():
        raise ValueError('internal RTL exposure failed; see binding/expose.log')
    observed = json.loads((out/'observed.json').read_text())['modules'][db.top]
    for entry in bindings:
        port = observed['ports'].get(entry['port'])
        if not port or port['direction'] != ('input' if ports[entry['port']].direction == 'in' else 'output') or len(port['bits']) != entry['width']:
            raise ValueError('internal observation interface was not preserved')
    if cone_cut:
        # Serialize all remaining free module outputs as primary inputs. This
        # preserves their freedom without relying on backend-specific $anyseq
        # Verilog cells.
        netlist = json.loads((out/'observed.json').read_text())
        mod = netlist['modules'][db.top]
        for index, (name, cell) in enumerate(list(mod['cells'].items())):
            if cell['type'] != '$anyseq':
                continue
            bits = cell['connections']['Y']
            alias = f'rvw_free_{index}'
            mod['ports'][alias] = dict(direction='input', bits=bits)
            mod['netnames'][alias] = dict(hide_name=0, bits=bits, attributes={})
            ports[alias] = replace(next(iter(signals.values())), id=-index-2, name=alias, direction='in', width=len(bits))
            del mod['cells'][name]
        (out/'reduced.json').write_text(json.dumps(netlist))
        (out/'serialize.ys').write_text(f'read_json {out}/reduced.json\nwrite_verilog -noattr {out}/observed.v\n')
        rc, _ = run(['yosys','-Q','-T','-s','serialize.ys'],out,out/'serialize.log',timeout)
        if rc:
            raise ValueError('connection cone serialization failed')
    target = out/'observed.v'
    identity = dict(backend='yosys source cut and cone reduction' if cone_cut else 'yosys flatten and expose; drivers retained',
                    abstractions=abstractions, bindings=bindings,
                    derived_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                    source_sha256={str(p):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in original_files})
    (out/'binding.json').write_text(json.dumps(identity,indent=2)+'\n')
    return [str(target)], ports, identity
