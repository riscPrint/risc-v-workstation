"""Load a trace-selected flat register state into native timed replay."""
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
        common.check_ident('state register',name)
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
    mod=model[top]
    state=set()
    generated=set()
    # Exclude only generated monitor registers. Boolean monitor wires can alias
    # real DUT state, so their names cannot identify monitor state.
    source=(out/'inputs/temporal.sv').read_text()
    helpers=re.findall(r'\breg\b[^;\n]*\b(rvw_sva_\w+)\s*(?:=[^;]*)?;',source)
    for name in helpers:
        generated.update(mod.get('netnames',{}).get(name,{}).get('bits',[]))
    for name,net in mod.get('netnames',{}).items():
        if name.startswith('$formal$'):
            generated.update(net['bits'])
    input_bits={bit for p in mod['ports'].values() if p['direction']=='input' for bit in p['bits']}
    def child_state(name,stack=()):
        if name in stack:
            raise ValueError('recursive module state')
        return any((cell['type'] in model and child_state(cell['type'],(*stack,name))) or
                   cell['type'].startswith(('$mem','$dff','$adff','$sdff','$dlatch','$aldff','$ff'))
                   for cell in model[name].get('cells',{}).values())
    for cell in mod.get('cells',{}).values():
        kind=cell['type']
        if kind in model:
            if child_state(kind):
                raise ValueError('trace state loading currently needs flat top-level state')
            continue
        if kind.startswith('$mem'):
            raise ValueError('trace state loading does not yet load memories')
        q=set(cell.get('connections',{}).get('Q',[]))
        if not q or not kind.startswith(('$dff','$adff','$sdff','$ff')):
            continue
        if q <= generated:
            continue
        for control in ('CLK','ARST'):
            wire=cell['connections'].get(control)
            if wire and not set(wire)<=input_bits:
                raise ValueError('loaded state clocks and async resets must be top-level inputs')
        state.update(q)
    loaded=set()
    assignments=[]
    for name in names:
        var=variables.get(name)
        net=mod.get('netnames',{}).get(name)
        if var is None or var.kind not in ('reg','logic','bit','integer'):
            raise ValueError('state register needs a trace variable: '+name)
        if net is None or len(net['bits'])!=var.width or not set(net['bits'])<=state:
            raise ValueError('state register does not map to DUT register bits: '+name)
        if name in inputs:
            raise ValueError('state register is an input: '+name)
        assignments.append(dict(signal=name,width=var.width,value=bits(var,snap)))
        loaded.update(net['bits'])
    if loaded != state:
        raise ValueError(f'incomplete trace register state: {len(loaded)} of {len(state)} bits')
    return dict(trace=item.source,trace_sha256=item.sha256,time=snap.time,timescale=snap.timescale,scope=scope,
                registers=assignments,state_bits=len(state),coverage='complete flat register state',
                limits=['No memory or child-module state.',
                        'Monitor histories restart; this is a finite native continuation, not a proof.'])
