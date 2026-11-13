"""Memory BIST handoff obligations, not BIST insertion or manufacturing evidence."""
import json
from pathlib import Path
from rvw.query.db import DesignDB, QueryError
from .handoff import rows
from .model import dumps,keys


def requirements(db_path, source, out):
    spec=json.loads(Path(source).read_text())
    keys(spec,{'schema','memories'},{'schema','memories'})
    if spec['schema']!='rvw.soc-mbist/1': raise ValueError('unsupported MBIST requirements')
    db=DesignDB(db_path)
    try:
        memories={m['path']:m for m in rows(db,'memories')}
        ports=rows(db,'mem_ports')
        domains={d['id']:d for d in rows(db,'clock_domains')}
        results=[]
        declared=set()
        for req in spec['memories']:
            keys(req,{'path','width','depth','test_enable','functional_value','repair','isolation_connections'},
                 {'path','width','depth','test_enable','functional_value','repair','isolation_connections'})
            if req['path'] in declared or req['path'] not in memories: raise ValueError('duplicate or unknown memory')
            declared.add(req['path'])
            memory=memories[req['path']]
            if (req['width'],req['depth'])!=(memory['width'],memory['depth']): raise ValueError('memory dimensions differ')
            enable=db.resolve_one(req['test_enable'])
            if enable.width!=1 or req['functional_value'] not in (0,1): raise ValueError('functional mode needs a one-bit test enable and binary value')
            repair=[]
            for name in req['repair']:
                s=db.resolve_one(name)
                repair.append(dict(path=s.path,width=s.width,direction=s.direction))
            from rvw.formal.connectivity import resolve
            isolation=[resolve(db, row) for row in req['isolation_connections']]
            selected=[p for p in ports if p['memory_id']==memory['id']]
            results.append(dict(memory=memory,ports=selected,
                clock_reset=[domains.get(p['clock_domain_id']) for p in selected],
                test_enable=enable.path,functional_value=req['functional_value'],repair=repair,
                isolation_connections=req['isolation_connections'],isolation_structural=isolation,isolation_status='not_run',
                obligation='Prove functional port value transfer with test_enable fixed to functional_value. Prove test/repair controls cannot alter functional outputs in that mode.'))
        result=dict(schema='rvw.soc-mbist-handoff/1',status='inconclusive',database_sha256=db.input.sha256,
            memories=results,undeclared_memories=sorted(memories.keys()-declared),
            note='Metadata consistency only. Functional isolation is an unrun proof obligation. No insertion or manufacturing readiness claim.')
        with Path(out).open('x') as f: f.write(dumps(result))
        return result
    finally: db.close()
