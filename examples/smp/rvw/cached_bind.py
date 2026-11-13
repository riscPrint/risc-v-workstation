#!/usr/bin/env python3
"""Bind the generated monitor to real SpinalDB members of the line projection."""
import argparse,json,sqlite3
from pathlib import Path
from rvw.memory.tilelink_bind import FIELDS,generate

def bind(database,out):
    db=sqlite3.connect(database);db.row_factory=sqlite3.Row
    bundles=[dict(r) for r in db.execute('SELECT * FROM bundles')]
    signals=[dict(r) for r in db.execute('SELECT * FROM signals')]
    clients=[]
    for hart in range(2):
        matches=[b for b in bundles if b['path'].split('.')[-1]==f'observed{hart}' and b['class_name'].split('.')[-1]=='Bus']
        if len(matches)!=1:raise ValueError(f'one typed observed{hart} bundle required: {matches}')
        bus=matches[0];mapping={}
        for field in FIELDS:
            channel,name=field.split('_',1)
            path=bus['path']+'.'+channel+('.' if name in ('valid','ready') else '.payload.')+name
            found=[r for r in signals if r.get('spinal_path')==path and r['component_id']==bus['component_id']]
            if len(found)!=1:raise ValueError(f'unique typed member required: {path}')
            mapping[field]=found[0]['id']
        clients.append(dict(bundle_id=bus['id'],signals=mapping))
    component=matches[0]['component_id'];by_id={r['id']:r for r in signals}
    def unique(name):
        found=[r for r in signals if r['name']==name and r['component_id']==component and not r.get('pruned')]
        if len(found)!=1:raise ValueError(f'unique live {name} required')
        return found[0]['id']
    def width(name):return by_id[clients[0]['signals'][name]]['width']
    profile=dict(schema='rvw.tlc-bind/1',bus_family='spinal-tilelink',oracle_kind='independent-stimulus',
        fairness='finite cache handoff, no channel stalls injected; 10000-cycle service bound',
        line_address='0x80080000',line_bytes=64,source_bits=width('a_source'),sink_bits=width('d_sink'),
        address_bits=width('a_address'),data_bits=width('d_data'),size_bits=width('a_size'),bound_cycles=10000,
        trunk_dirty=True,clock=unique('clk'),reset=unique('reset'),expected_data=unique('expected_data'),clients=clients)
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    path=out/'profile.json';path.write_text(json.dumps(profile,indent=2)+'\n')
    result=generate(database,path,out/'monitor')
    result['monitor']='monitor/rvw_tlc_monitor.sv';result['bind']='monitor/rvw_tlc_bind.sv'
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--database',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();print(json.dumps(bind(a.database,a.out),indent=2))
