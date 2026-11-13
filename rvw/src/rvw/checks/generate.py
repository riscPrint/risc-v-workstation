"""Run available generators and keep missing bindings explicit."""
import json
import sqlite3
from pathlib import Path

from rvw.common.project import load_project
from rvw.query.db import QueryError


def generate(project, out, manifest=None):
    loaded=load_project(project)
    if loaded is None:
        raise ValueError('select a project with rvw.toml')
    selected=loaded.path
    root=selected.parent
    settings=Path(manifest) if manifest else root/'checks.generate.json'
    spec=json.loads(settings.read_text())
    if not isinstance(spec,dict) or spec.get('schema')!='rvw.check-generation/1':
        raise ValueError('expected rvw.check-generation/1')
    if set(spec)-{'schema','streams','buses','csrs','queues','power'}:
        raise ValueError('unknown check generation kind')
    out=Path(out)
    if not out.is_absolute(): out=root/out
    out.mkdir(parents=True,exist_ok=False)
    rows=[]
    for kind in ('streams','buses','csrs','queues','power'):
        row=dict(kind=kind,status='unbound')
        rows.append(row)
        if kind not in spec:
            row['reason']='no project data supplied'
            continue
        try:
            target=out/kind
            from .bindings import generate as generate_bound
            bound=generate_bound(kind,spec[kind],settings.parent,target)
            if bound is not None:
                row.update(bound,output=str(target))
                continue
            source=(settings.parent/spec[kind]).resolve()
            if kind=='buses':
                from rvw.formal.bus_bindings import generate as run
                result=run(source,target)
                row.update(status=result['status'],instances=result['buses'])
            elif kind=='csrs':
                from rvw.formal.csr import generate as run,load
                if json.loads(source.read_text()).get('schema')=='rvw.csr-bank/1':
                    from rvw.formal.csr_bank import load as load_bank
                    model=load_bank(source)
                else:
                    model=load(source)
                result=run(source,target)
                row.update(status='generated' if 'binding' in model else 'unbound',
                           reason='review the project wrapper' if 'binding' in model else 'CSR sources emitted; no project wrapper supplied')
            elif kind=='queues':
                from rvw.formal.micro_checks import generate as run
                result=run(json.loads(source.read_text()),target)
                row.update(status=result['status'],instances=result['rules'])
            elif kind=='power':
                from rvw.formal.power_intent import generate as run
                result=run(source,target)
                row.update(status='unbound',reason='power sources emitted; instance bindings are required')
            else:
                from rvw.formal.property_library import render
                obj=json.loads(source.read_text())
                target.mkdir()
                text='\n'.join(render(p) for p in obj['properties'])
                (target/'properties.sv').write_text(text)
                row.update(status='unbound',reason='stream properties emitted; include them in the project module')
            row['output']=str(target)
        except (ValueError,KeyError,TypeError,OSError,QueryError,sqlite3.Error) as exc:
            row.update(status='unsupported',reason=str(exc))
    for row in rows:
        if row['status']!='generated' and 'reason' not in row:
            row['reason']='no recognized bindable instances' if not row.get('instances') else 'see per-instance binding reasons'
    unbound=[]
    for row in rows:
        instances=row.get('instances',[])
        if row['status']!='generated' and not instances:
            unbound.append(dict(kind=row['kind'],reason=row['reason']))
        for instance in instances:
            name=instance.get('id',instance.get('path'))
            if instance['status']!='generated':
                unbound.append(dict(kind=row['kind'],instance=name,reason=instance.get('reason','no bound monitor')))
            for gap in instance.get('unbound_checks',[]):
                unbound.append(dict(kind=row['kind'],instance=name,check=gap['kind'],reason=gap['reason']))
    result=dict(schema='rvw.check-generation-summary/1',
                status='generated' if any(r['status']=='generated' for r in rows) else 'no_checks',
                complete=all(r['status']=='generated' for r in rows) and not unbound,unbound=unbound,
                project=str(selected),checks=rows,
                limitations=['Generation does not compile RTL or run proofs.',
                             'Declared instance bindings require project review.'])
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
