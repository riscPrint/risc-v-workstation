"""Bind reviewed Stream/Flow rules to captured instance-local ports."""
import json
import re
from pathlib import Path
from rvw.formal.channel_bindings import bind_database
from rvw.formal.property_library import from_channels,render
from rvw.formal.temporal import lower
from rvw.query.db import DesignDB,QueryError


def generate(database,report,contracts,out):
    if report.get('schema')!='rvw.checks/1': raise ValueError('expected rvw.checks/1')
    rows,sources,binds=[],[],[]
    db=DesignDB(database)
    try:
        for index,channel in enumerate(report.get('channels',[])):
            old_key=channel['path']+'.'+channel['object']
            key=old_key.lstrip('.')
            row=dict(path=key,kind=channel['kind'],status='unsupported');rows.append(row)
            try:
                contract=dict(contracts.get(key,contracts.get(old_key,{})))
                if channel['kind'].lower()=='stream' and contract.get('stable') is not True:
                    raise ValueError('declare stable=true for this reviewed Stream contract')
                subset=dict(schema='rvw.checks/1',channels=[channel])
                binding=bind_database(subset,{old_key:contract},db)
                spec=from_channels(subset,binding)[0]
                spec['id']='channel_'+str(index)
                owner=db.resolve_one(channel['valid']).component_id
                local={s.name:s for s in db.signals_where('s.component_id=?',(owner,))}
                ports={v:local[v].width for v in binding[old_key]['ports'].values()}
                for control in ('clock','reset'):
                    if spec.get(control): ports[spec[control]]=1
                module='rvw_channel_'+str(index)
                declarations=', '.join(f'input [{width-1}:0] {name}' for name,width in sorted(ports.items()))
                source='module '+module+'('+declarations+');\n'+render(spec)+'\nendmodule\n'
                source,_=lower(source)
                target=db.top
                path=db.component(owner)['path']
                if path: target+='.'+path
                if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*',target):
                    raise ValueError('unsupported hierarchical bind target')
                sources.append(source)
                binds.append('bind '+target+' '+module+' '+module+'_instance('+', '.join('.'+p+'('+p+')' for p in sorted(ports))+');')
                row.update(status='generated',target=target,ports=ports)
            except (ValueError,KeyError,TypeError,QueryError) as exc:
                row['reason']=str(exc)
        capture=db.capture_record()
    finally: db.close()
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    (out/'monitors.sv').write_text('\n'.join(sources))
    (out/'binds.sv').write_text('\n'.join(binds)+'\n')
    result=dict(schema='rvw.stream-generation/1',status='generated' if binds else 'no_checks',
                channels=rows,database=capture,
                complete=bool(binds) and all(r['status']=='generated' for r in rows),
                limits=['Stream stability and Flow ranges are project contracts.',
                        'Use a SystemVerilog frontend with bind support.',
                        'Sampled clock/reset rules only. No compiler, simulator or proof was run.'])
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
