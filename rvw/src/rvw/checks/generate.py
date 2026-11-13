"""Run available generators and keep missing bindings explicit."""
import json
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
    if spec.get('schema')!='rvw.check-generation/1':
        raise ValueError('expected rvw.check-generation/1')
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
            source=(settings.parent/spec[kind]).resolve()
            target=out/kind
            if kind=='buses':
                from rvw.formal.bus_bindings import generate as run
                result=run(source,target)
                row.update(status=result['status'],instances=result['buses'])
            elif kind=='csrs':
                from rvw.formal.csr import generate as run,load
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
        except (ValueError,KeyError,TypeError,OSError,QueryError) as exc:
            row.update(status='unsupported',reason=str(exc))
    result=dict(schema='rvw.check-generation-summary/1',
                status='generated' if any(r['status']=='generated' for r in rows) else 'no_checks',
                complete=all(r['status']=='generated' and all(i['status']=='generated' for i in r.get('instances',[])) for r in rows),
                project=str(selected),checks=rows,
                limitations=['Generation does not compile RTL or run proofs.',
                             'Declared instance bindings require project review.'])
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
