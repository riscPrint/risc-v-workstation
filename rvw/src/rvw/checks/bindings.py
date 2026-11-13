"""Bound generator inputs for the project-wide check command."""
import json
from pathlib import Path


def generate(kind,entry,base,out):
    if kind=='cdc':
        from .cdc import generate as generate_cdc
        return generate_cdc(entry,base,out)
    if not isinstance(entry,dict): return None
    base=Path(base)
    if kind=='streams':
        if set(entry)-{'database','report','contracts'} or not {'database','report'}<=set(entry):
            raise ValueError('streams needs database/report and optional contracts paths')
        from .streams import generate as generate_streams
        report=json.loads((base/entry['report']).read_text())
        contracts=json.loads((base/entry['contracts']).read_text()) if entry.get('contracts') else {}
        result=generate_streams(base/entry['database'],report,contracts,out)
        return dict(status=result['status'],instances=result['channels'])
    if kind=='buses':
        if set(entry)-{'database','depth','max_beats','type_report','clocks'} or 'database' not in entry:
            raise ValueError('buses needs database and optional tracker depth/max_beats')
        from rvw.formal.bus_bindings import generate as generate_buses
        result=generate_buses(base/entry['database'],out,entry.get('depth',4),entry.get('max_beats',256),
                              base/entry['type_report'] if entry.get('type_report') else None,
                              base/entry['clocks'] if entry.get('clocks') else None)
        return dict(status=result['status'],instances=result['buses'])
    if kind=='power':
        if set(entry)!={'source','bindings'}:
            raise ValueError('bound power needs UPF source and bindings paths')
        from rvw.formal.upf_subset import generate as generate_upf
        result=generate_upf(base/entry['source'],base/entry['bindings'],out)
        instances=[]
        for family in ('isolation','retention','psts','switches'):
            instances.extend(dict(id=family+':'+name,status='generated') for name in result['intent'].get(family,{}))
        instances.extend(dict(id=name,status='unsupported',reason='domain has no generated monitor')
                         for name in result['unmonitored_domains'])
        return dict(status=result['status'],instances=instances)
    raise ValueError(kind+' expects an input path')
