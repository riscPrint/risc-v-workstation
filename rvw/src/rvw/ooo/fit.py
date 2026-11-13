"""Bounded parameter fitting to saved C1/C2 and probe-derived event counts."""
from copy import deepcopy
from dataclasses import asdict
import itertools
import json
from pathlib import Path
from statistics import mean
from .core import run
from .evidence import calibrate
from .project import configuration
from .search import set_value


def fit(plan,out):
    p=Path(plan).resolve();spec=json.loads(p.read_text())
    if spec.get('schema')!='rvw.ooo-fit-plan/1':raise ValueError('expected fit plan')
    source=(p.parent/spec['calibration_plan']).resolve()
    calibration=json.loads(source.read_text())
    for key in ('config','event_map'):
        calibration[key]=str((source.parent/calibration[key]).resolve())
    for sample in calibration['samples']:
        for key in ('elf','trace','c1','events'):
            sample[key]=str((source.parent/sample[key]).resolve())
    base=asdict(configuration(json.loads(Path(calibration['config']).read_text())))
    params=spec['parameters']
    if not isinstance(params,dict) or not params or any(not isinstance(v,list) or not v for v in params.values()):
        raise ValueError('nonempty parameter choices required')
    count=1
    for v in params.values():count*=len(v)
    if count>32:raise ValueError('fit grid exceeds 32 candidates')
    dest=Path(out).resolve();dest.mkdir(parents=True,exist_ok=False)
    frozen=dest/'baseline-plan.json';frozen.write_text(json.dumps(calibration))
    # Reuse evidence identity, split, hash and region checks before selection.
    validated=calibrate(frozen,dest/'baseline-validation.json')
    training=validated['samples']['training']
    mappings=json.loads(Path(calibration['event_map']).read_text())
    paths={s['id']:s['trace'] for s in calibration['samples'] if s['split']=='training'}
    candidates=[]
    for i,values in enumerate(itertools.product(*(params[k] for k in sorted(params)))):
        data=deepcopy(base)
        for key,value in zip(sorted(params),values):set_value(data,key,value)
        cp=dest/f'candidate-{i}.json';cp.write_text(json.dumps(data,sort_keys=True))
        errors=[]
        for row in training:
            model=run(cp,paths[row['id']])
            errors.append(abs(model['cycles']/row['rtl_cycles']-1))
            for name,mapping in mappings.items():
                measured=row['events'][name]['measured']
                if measured is None:raise ValueError('training event is missing: '+name)
                errors.append(abs(model['events'].get(mapping['model_event'],0)-measured)/max(1,measured))
        candidates.append(dict(id=i,values=dict(zip(sorted(params),values)),score=mean(errors)))
    best=min(candidates,key=lambda r:(r['score'],r['id']))
    chosen=dest/'best-config.json';chosen.write_bytes((dest/f"candidate-{best['id']}.json").read_bytes())
    calibration['config']=str(chosen)
    frozen=dest/'fitted-plan.json';frozen.write_text(json.dumps(calibration))
    final=calibrate(frozen,dest/'calibration.json')
    report=dict(schema='rvw.ooo-fit/1',status='reported',accuracy_status='inconclusive',
                candidates=candidates,best=best,config=str(chosen),calibration=str(dest/'calibration.json'),
                heldout=final['samples']['heldout'],
                objective='mean absolute relative cycle and mapped-event errors on training only; zero events use denominator one',
                limits=['baseline validation reads heldout evidence, but selection uses training only',
                        'finite declared grid; no claim of unique or global fitted parameters',
                        'saved observations only; no RTL launch or accuracy verdict'])
    (dest/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
