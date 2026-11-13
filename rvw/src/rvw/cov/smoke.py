"""Coverage selection with a measured cost estimate and an optional wall deadline."""
import json
import math
from hashlib import sha256
from pathlib import Path
import sys
import time
from . import captured
from .code import _require_conclusive,rank
from rvw.common.proc import run_group
from rvw.regress.config import load_config
from rvw.results import load_run


def select(hits,costs,budget_s,startup_s=0):
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 for v in (budget_s,startup_s)) or budget_s<=0:
        raise ValueError('budget must be positive and startup cost nonnegative')
    remaining=budget_s-startup_s;chosen=[];covered=set();cost=0.0
    unknown=sorted(name for name in hits if name not in costs or costs[name] is None)
    for name,value in costs.items():
        if value is None:continue
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:
            raise ValueError('test costs must be finite and nonnegative')
    while True:
        eligible=[name for name in hits if name not in chosen and name in costs and costs[name] is not None
                  and costs[name]<=remaining and hits[name]-covered]
        if not eligible:break
        name=min(eligible,key=lambda n:(-len(hits[n]-covered)/max(costs[n],1e-9),-len(hits[n]-covered),costs[n],n))
        chosen.append(name);covered|=hits[name];remaining-=costs[name];cost+=costs[name]
    return {'selected':chosen,'covered':sorted(covered),'estimated_test_s':cost,
        'estimated_total_s':startup_s+cost if chosen else 0,'unknown_costs':unknown,
        'notes':['Costs are recorded C1 wall seconds plus the declared startup allowance.',
                 'Selection is greedy. It does not prove the best coverage under the time budget.',
                 'The estimate is not a runtime guarantee.']}


@captured.command
def execute_json(database,budget_s,startup_s=0,run=False,project=None,work_dir=None):
    data=json.loads(captured.read_text(database));_require_conclusive(data)
    if data.get('schema')!='rvw.coverage/1':raise ValueError('expected rvw.coverage/1')
    hits={name:{p['id'] for p in data['points'] if p['count'] and name in p['tests'] and not p.get('exclusion')}
          for name in data['tests']}
    costs={name:t['run']['wall_s'] for name,t in data['tests'].items()
           if t.get('run') and t['run'].get('wall_s') is not None}
    selection=select(hits,costs,budget_s,startup_s)
    result={'schema':'rvw.coverage-smoke/1','status':'planned','database_sha256':captured.sha256(database),
        'point_universe':data['point_universe'],'budget_s':budget_s,'startup_s':startup_s,
        **selection,'minimisation':rank(data,exact=len(data['tests'])<=20),
        'measured_target_points':len(set().union(*hits.values())) if hits else 0,
        'new_execution_coverage_credit':False}
    covered=result.pop('covered')
    result['covered_points']=len(covered)
    result['covered_sha256']=sha256('\n'.join(covered).encode()).hexdigest()
    result['native_point_denominator']=len(data['points'])
    if not run:return result
    if not work_dir:raise ValueError('execution needs a new work_dir and a selected project')
    if not selection['selected']:return result|{'status':'no_tests'}
    core=load_config(project=project);out=Path(work_dir).resolve();out.mkdir(parents=True,exist_ok=False)
    jobs=[];kinds=set()
    for index,name in enumerate(selection['selected']):
        old=data['tests'][name]['run']
        if old['core']!=core.name or old['config'] not in core.configs:
            raise ValueError('measured test differs from selected project')
        elf=Path(old['elf']).resolve()
        if not elf.is_file() or captured.sha256(elf)!=old['elf_sha256']:
            raise ValueError('measured ELF is unavailable or changed: '+name)
        model=old.get('details',{}).get('model',{})
        kinds.add(tuple(model.get('coverage_types',[])))
        jobs.append({'elf':str(elf),'out':str(out/f'test-{index:04d}'),'config':old['config'],'seed':old['seed'],
            'max-cycles':old['max_cycles'],'mem-latency':old['mem_latency'],'rvfi-trace':True,
            'coverage':True,'probes':bool(model.get('probes',False)),'wall-timeout':budget_s})
        if old['mem_latency'] is None:jobs[-1].pop('mem-latency')
    if len(kinds)!=1 or not next(iter(kinds)):
        raise ValueError('measured native coverage kinds are missing or differ')
    manifest=out/'jobs.jsonl';manifest.write_text(''.join(json.dumps(job)+'\n' for job in jobs))
    command=[*core.adapter,'run-many','--manifest',str(manifest),'--jobs','1','--json']
    if core.lock:command=[sys.executable,'-m','rvw.common.lock',core.lock,*command]
    import os
    env=dict(os.environ);env['RISCVSIM_COVERAGE']=','.join(next(iter(kinds)))
    started=time.monotonic()
    with (out/'adapter.log').open('w') as log:
        execution=run_group(['nice','-n','10',*command],timeout=budget_s,stdout=log,stderr=log,env=env)
    observations=[]
    for name,job in zip(selection['selected'],jobs):
        path=Path(job['out'])/'result.json'
        if path.is_file():
            observed=load_run(path)
            identity_ok=(observed.core==core.name and observed.config==job['config']
                and observed.seed==job['seed'] and observed.elf_sha256==captured.sha256(job['elf']))
            options=observed.extra.get('options',{})
            flags_ok=options.get('coverage') is True and options.get('probes')==job['probes']
            why=observed.why_inconclusive or (None if identity_ok and flags_ok else 'C1 requested job identity or model flags differ')
            observations.append({'test':name,'status':observed.status,
                'inconclusive':why,'sha256':captured.sha256(path),'rtl_sha256':observed.extra.get('rtl_sha256')})
    passed=len(observations)==len(jobs) and all(r['status']=='pass' and not r['inconclusive'] for r in observations)
    result['execution']={'elapsed_s':time.monotonic()-started,'timed_out':execution.timed_out,
        'returncode':execution.returncode,'observations':observations,
        'scope':'C1 only; no new Spike comparison or coverage credit'}
    failed=any(r['status'] in ('fail','assert') and not r['inconclusive'] for r in observations)
    result['status']='fail' if failed else 'timed_out' if execution.timed_out else 'pass' if passed and execution.returncode==0 else 'inconclusive'
    (out/'smoke.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
