"""Timing, software-cost and optional saved RTL evidence for one workload."""
from hashlib import sha256
import json
from pathlib import Path
from .energy import number
from .ledger import store
from rvw.ooo.core import run


def tradeoff(plan,out):
    p=Path(plan).resolve();spec=json.loads(p.read_text())
    if spec.get('schema')!='rvw.custom-tradeoff-plan/1' or not spec.get('workload_id'):
        raise ValueError('custom trade-off plan needs a workload identity')
    rows={}
    for name in ('baseline','candidate'):
        case=spec[name];paths={k:p.parent/case[k] for k in ('config','trace','elf')}
        hashes={k:sha256(v.read_bytes()).hexdigest() for k,v in paths.items()}
        model=run(paths['config'],paths['trace'])
        row=dict(hashes=hashes,model=model,rtl_status='no_checks',ppa_status='no_checks')
        if case.get('c1'):
            from rvw.results.schema import RunResult
            cp=p.parent/case['c1'];raw=json.loads(cp.read_text());c1=RunResult.from_dict(raw)
            header=json.loads(paths['trace'].read_bytes().splitlines()[0])
            if c1.status!='pass' or c1.why_inconclusive or c1.elf_sha256!=hashes['elf'] or c1.instret!=model['instret']:
                raise ValueError('C1 must pass and match the ELF and instruction count')
            if any(header[k]!=getattr(c1,k) for k in ('core','config','elf')):
                raise ValueError('C1/C2 identity mismatch')
            if type(c1.cycles) is not int or c1.cycles<1:raise ValueError('positive RTL cycles required')
            row.update(rtl_status='reported',rtl_cycles=c1.cycles,c1_sha256=sha256(cp.read_bytes()).hexdigest(),
                       model_cycle_error_percent=100*(model['cycles']/c1.cycles-1))
        if case.get('ppa'):
            pp=p.parent/case['ppa'];e=json.loads(pp.read_text())
            if e.get('schema')!='rvw.early-ppa/1' or not e.get('source') or not e.get('rtl_revision'):
                raise ValueError('PPA evidence needs schema, source and RTL revision')
            metrics={k:number(e[k]) for k in ('area_mm2','delay_ns','power_mw') if k in e}
            if not metrics:raise ValueError('PPA evidence has no metrics')
            row.update(ppa_status='reported',ppa=dict(metrics=metrics,source=e['source'],rtl_revision=e['rtl_revision']),
                       ppa_sha256=sha256(pp.read_bytes()).hexdigest())
        checks=[p.parent/v for v in case.get('checks',[])]
        row['independent_check_artifacts']={str(v):sha256(v.read_bytes()).hexdigest() for v in checks}
        rows[name]=row
    cost=spec['software_cost']
    if not cost.get('source') or not cost.get('unit'):raise ValueError('software cost needs source and unit')
    costs={k:number(cost[k]) for k in ('baseline','candidate')}
    result=dict(schema='rvw.custom-tradeoff/1',status='reported',workload_id=spec['workload_id'],
                plan_sha256=sha256(p.read_bytes()).hexdigest(),cases=rows,
                predicted_speedup=rows['baseline']['model']['cycles']/rows['candidate']['model']['cycles'],
                software_cost=dict(**costs,unit=cost['unit'],source=cost['source'],delta=costs['candidate']-costs['baseline']),
                accuracy_status='inconclusive',
                limits=['workload equivalence is producer-declared; different ELF bytes are not proven equivalent',
                        'C1 timing pass does not establish custom instruction semantic correctness',
                        'check artifacts are hashed references; no aggregate pass is inferred',
                        'PPA metrics are producer declarations, not physical measurements inferred by this command'])
    if all(r['rtl_status']=='reported' for r in rows.values()):
        result['rtl_speedup']=rows['baseline']['rtl_cycles']/rows['candidate']['rtl_cycles']
    if all(r['ppa_status']=='reported' for r in rows.values()):
        a,b=[rows[k]['ppa']['metrics'] for k in ('baseline','candidate')]
        result['ppa_delta']={k:dict(delta=b[k]-a[k],ratio=b[k]/a[k] if a[k] else None)
                             for k in sorted(a.keys() & b.keys())}
    return store(out,result)
