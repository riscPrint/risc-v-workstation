"""Reuse fault campaigns, then require declared security observations as well as C2."""
import json
from pathlib import Path
from rvw.fault.campaign import sites, plan, run_campaign
from .common import publish


def classify(outcomes,golden,observations):
    findings=[];unresolved=[]
    for row in outcomes:
        key=row['id'];kind=row['classification']
        if kind=='silent_corruption': findings.append(dict(fault=key,reason=kind))
        elif kind=='detected':
            mechanisms=row.get('evidence',{}).get('detected_by',[])
            if not mechanisms or any(m.startswith('status:') for m in mechanisms):
                unresolved.append(key)
        elif kind=='safe':
            if key not in observations or not golden or set(observations[key])!=set(golden):
                unresolved.append(key)
            elif observations[key]!=golden:
                findings.append(dict(fault=key,reason='security observation changed'))
        else: unresolved.append(key)
    return findings,unresolved


def run(manifest,out):
    source=Path(manifest).resolve();p=json.loads(source.read_text())
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    def local(key):
        q=Path(p[key]);return q if q.is_absolute() else source.parent/q
    if not p.get('critical_registers') or not p.get('observations'):
        raise ValueError('declare critical_registers and security observation channels')
    timeout=p.get('timeout',90)
    if not 0<timeout<=120: raise ValueError('timeout must be in (0,120]')
    population=sites(local('db'),include=p['critical_registers'])
    fp=plan(population,kinds=('flip',),window=tuple(p.get('window',[0,100])),
            samples=p.get('samples',16),seed=p.get('seed',1))
    (out/'plan.json').write_text(json.dumps(fp,indent=2))
    summary,outcomes=run_campaign(fp,['nice','-n','10',*p['adapter_command']],local('elf'),out/'fault',
             timeout=timeout,detections=p.get('detections'),jobs=1)
    def obs(folder):
        file=folder/'security-observations.json'
        if not file.exists(): return {}
        data=json.loads(file.read_text())
        return data if set(data)==set(p['observations']) else {}
    golden=obs(out/'fault/golden')
    observations={r['id']:obs(out/'fault/faults'/r['id']) for r in outcomes}
    findings,unresolved=classify(outcomes,golden,observations)
    return publish(out,'fault',findings,bool(outcomes) and not unresolved,
                   unresolved=unresolved,fault_summary=summary,plan=fp,
                   detection_model='rvw fault declared detections; same digital observation channels')
