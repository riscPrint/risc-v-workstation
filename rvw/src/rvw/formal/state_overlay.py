"""Load a trace-selected register state into native timed replay."""
import json
from pathlib import Path
import re

from . import common, vcdsnap


def bits(var, snapshot):
    raw=snapshot.values.get(var.code)
    if raw is None:
        raise ValueError('trace lacks a value for '+'.'.join(var.path))
    raw=raw.removeprefix('b').lower()
    if len(raw)>var.width or set(raw)-set('01xz'):
        raise ValueError('invalid trace register value')
    return raw.rjust(var.width,raw[0] if raw[0] in 'xz' else '0')


def load(spec, capture, event_file, out, top, inputs, initial, timeout):
    if set(spec)-{'trace','time','scope','registers'}:
        raise ValueError('unknown state field')
    if type(spec.get('time')) is not int or spec['time']<0:
        raise ValueError('state.time must be a nonnegative trace timestamp')
    names=spec.get('registers',[])
    if not names or len(set(names))!=len(names):
        raise ValueError('state.registers must name each loaded register once')
    for name in names:
        common.check_hier('state register',name)
    path=Path(spec['trace'])
    if not path.is_absolute():
        path=Path(event_file.source).parent/path
    item=capture.file(path)
    scope=spec['scope']
    common.check_hier('state scope',scope)
    snap=vcdsnap.take(item.copy,scope,None,None,spec['time'],timeout)
    variables={'.'.join(v.path):v for v in snap.vars}
    for name,width in inputs.items():
        var=variables.get(name)
        if var is None or var.width!=width or bits(var,snap)!=initial[name].lower():
            raise ValueError('initial event inputs disagree with trace: '+name)
    model=json.loads((out/'module_ports.json').read_text())['modules']
    state=set()
    instances={}
    genuine=register_outputs(out/'module_ports.il')
    # Exclude generated registers, not Boolean aliases of real DUT state.
    source=(out/'inputs/temporal.sv').read_text()
    helpers=re.findall(r'\breg\b[^;\n]*\b(rvw_sva_\w+)\s*(?:=[^;]*)?;',source)
    def visit(module,path=(),stack=()):
        if module in stack:
            raise ValueError('recursive module state')
        mod=model[module]
        if mod.get('attributes',{}).get('blackbox',0) not in (0,'0','0'*32):
            raise ValueError('trace state loading cannot inspect black-box state')
        instances[path]=(module,mod)
        generated=set()
        for name,net in mod.get('netnames',{}).items():
            if name in helpers or name.startswith('$formal$'):
                generated.update(net['bits'])
        for name,cell in mod.get('cells',{}).items():
            kind=cell['type']
            if kind in model:
                visit(kind,(*path,name),(*stack,module))
                continue
            if kind.startswith('$mem'):
                raise ValueError('trace state loading does not yet load memories')
            if not kind.startswith('$'):
                raise ValueError('trace state loading cannot inspect unknown cell state')
            q=set(cell.get('connections',{}).get('Q',[]))
            if not q or not kind.startswith(('$dff','$adff','$sdff','$ff')) or q<=generated:
                continue
            state.update((path,bit) for bit in q)
    visit(top)
    loaded=set()
    assignments=[]
    for name in names:
        var=variables.get(name)
        *parents,leaf=name.split('.')
        owner=instances.get(tuple(parents))
        module,mod=owner if owner else (None,{})
        net=mod.get('netnames',{}).get(leaf)
        mapped={(tuple(parents),bit) for bit in net['bits']} if net else set()
        if var is None or var.kind not in ('reg','logic','bit','integer'):
            raise ValueError('state register needs a trace variable: '+name)
        if (net is None or len(net['bits'])!=var.width or not mapped<=state
                or leaf not in genuine.get(module,set())):
            raise ValueError('state register does not map to DUT register bits: '+name)
        if mod.get('ports',{}).get(leaf,{}).get('direction')=='input':
            raise ValueError('state register is an input: '+name)
        assignments.append(dict(signal=name,width=var.width,value=bits(var,snap)))
        loaded.update(mapped)
    if loaded != state:
        raise ValueError(f'incomplete trace register state: {len(loaded)} of {len(state)} bits')
    return dict(trace=item.source,trace_sha256=item.sha256,time=snap.time,timescale=snap.timescale,scope=scope,
                registers=assignments,state_bits=len(state),coverage='complete hierarchical register state',
                limits=['No memory or black-box state.',
                        'Replay forces all state while setup events settle, then releases it.',
                        'Monitor histories restart; this is a finite native continuation, not a proof.'])


def register_outputs(path):
    """Keep actual FF destination names before JSON bit IDs merge aliases."""
    result={}
    module=kind=None
    for line in path.read_text().splitlines():
        line=line.strip()
        if line.startswith('module '):
            module=line.split()[1].removeprefix('\\')
            result[module]=set()
        elif line.startswith('cell '):
            kind=line.split()[1]
        elif line=='end':
            if kind is not None:
                kind=None
            else:
                module=None
        elif (module is not None and kind is not None
              and kind.startswith(('$dff','$adff','$sdff','$ff'))
              and line.startswith('connect \\Q ')):
            result[module].update(re.findall(r'\\([A-Za-z_]\w*)\b',line[len('connect \\Q '):]))
    return result
