"""Project declarations for plain HDL ready/valid channels.

A declaration supplies protocol meaning. The design database supplies port
existence and widths. Signal names alone do not identify a protocol.
"""
import json
import re
from pathlib import Path
from rvw.query.db import DesignDB

IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')


def load(database, port_map):
    spec = json.loads(Path(port_map).read_text())
    if spec.get('schema') != 'rvw.hdl-ports/1':
        raise ValueError('expected rvw.hdl-ports/1')
    design = DesignDB(database)
    try:
        tops = design.q('SELECT id,module FROM components WHERE parent_id IS NULL')
        if len(tops) != 1 or tops[0][1] != spec['top']:
            raise ValueError('declared top differs from database')
        ports = {name: width for name, width, pruned in design.q(
            'SELECT name,width,pruned FROM signals WHERE component_id=? AND direction IS NOT NULL', (tops[0][0],))
                 if not pruned}
        def port(name, width=None):
            if not isinstance(name, str) or not IDENT.fullmatch(name) or name not in ports:
                raise ValueError('declared port is absent: ' + str(name))
            if not ports[name] or width is not None and ports[name] != width:
                raise ValueError('declared port has wrong width: ' + name)
            return name
        port(spec['clock'], 1)
        port(spec['reset']['signal'], 1)
        if type(spec['reset']['active']) is not int or spec['reset']['active'] not in (0,1):
            raise ValueError('reset active must be 0 or 1')
        names=set()
        if not spec.get('buses'):
            raise ValueError('declare at least one bus')
        for bus in spec['buses']:
            if not IDENT.fullmatch(bus['name']) or bus['name'] in names:
                raise ValueError('bus names must be unique HDL identifiers')
            names.add(bus['name'])
            if bus['protocol'] != 'ready_valid':
                raise ValueError('declared HDL path currently supports ready_valid channels')
            if set(bus['ports']) != {'valid','ready','payload'}:
                raise ValueError('ready_valid needs valid, ready and payload ports')
            port(bus['ports']['valid'],1); port(bus['ports']['ready'],1)
            payload=bus['ports']['payload']
            if not isinstance(payload,list) or not payload or len(set(payload)) != len(payload):
                raise ValueError('payload must list unique ports')
            for name in payload: port(name)
            bus['payload_width']=sum(ports[name] for name in payload)
        return spec
    finally:
        design.close()


def checks(database, port_map, out):
    from rvw.formal.simple_bus_checks import render
    spec=load(database,port_map)
    sources=[];binds=[];rows=[]
    for bus in spec['buses']:
        module='rvw_declared_'+bus['name']
        sources.append(render('axis',bus['payload_width'],4).replace('rvw_axis(',module+'('))
        pins=bus['ports']
        reset=spec['reset']['signal']
        if spec['reset']['active']==0: reset='~'+reset
        ports=dict(clk=spec['clock'],reset=reset,valid=pins['valid'],ready=pins['ready'],
                   payload='{'+','.join(pins['payload'])+'}')
        binds.append('bind '+spec['top']+' '+module+' '+module+'_instance ('+
                     ', '.join('.'+key+'('+value+')' for key,value in ports.items())+');')
        rows.append(dict(path=bus['name'],kind='ready_valid',status='generated',ports=ports))
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    (out/'monitors.sv').write_text('\n'.join(sources))
    (out/'binds.sv').write_text('\n'.join(binds)+'\n')
    result=dict(status='generated',buses=rows,complete=True,
                limits=['Generated stability checks only. No solver or simulation was run.'])
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
