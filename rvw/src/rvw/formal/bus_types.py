"""Resolve ambiguous database classes from an elaboration's bus inventory."""
import json
from pathlib import Path


def resolve(database, report):
    data=json.loads(Path(report).read_text())
    if data.get('schema')!='rvw.checks/1' or data.get('toplevel')!=database.top:
        raise ValueError('bus type report schema or top differs from database')
    inventory=data.get('buses',[])
    result={}
    for bid,cid,path,cls in database.q('SELECT id,component_id,path,class_name FROM bundles'):
        if cls!='Bus': continue
        component=database.component(cid)
        names={row[0] for row in database.q('SELECT name,spinal_path FROM signals WHERE component_id=? AND pruned=0',(cid,))
               if row[1] and row[1].startswith(path+'.')}
        if not names: continue
        matches=[b for b in inventory if b.get('path')==component['path'] and set(b.get('signals',[]))==names]
        if len(matches)==1:
            result[bid]=matches[0]
    return result
