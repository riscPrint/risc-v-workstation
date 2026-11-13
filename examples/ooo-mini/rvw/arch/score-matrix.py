#!/usr/bin/env python3
"""Freeze base-only predictions, then score them when the RTL matrix is complete."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
from rvw.ooo.core import run, _instructions
from rvw.ooo.delta import delta_error
from matrix import VARIANTS, PROGRAMS

TRAINING=PROGRAMS[:3]


def configuration(base,changes):
    config=deepcopy(base)
    for key,value in changes.items():
        if key=='predictor_entries':
            config['components']['branch']['entries']=value
            config['components']['btb']['entries']=value
        else:config[key]=value
    return config


def main(captures,output,allow_incomplete=False):
    if allow_incomplete not in (False,"--allow-incomplete"):
        raise ValueError("unknown scoring option")
    captures,output=Path(captures).resolve(),Path(output).resolve()
    output.mkdir(parents=True,exist_ok=True)
    if (output/'model-summary.json').exists():raise ValueError('final score already exists')
    rtl=json.loads((captures/'rtl-summary.json').read_text())
    observed={(r['config'],r['program']):r for r in rtl}
    if len(observed)!=len(rtl):raise ValueError('duplicate RTL tuple')
    frozen=output/'predictions.json'
    if not frozen.exists():
        base=json.loads((Path(__file__).parent/'model.json').read_text())
        candidates=[]
        for penalty in (0,1,2,3):
            config=deepcopy(base);config['branch_penalty']=penalty
            cp=output/f'candidate-{penalty}.json';cp.write_text(json.dumps(config))
            predictions={p:run(cp,captures/'default'/p/'rvfi.jsonl') for p in TRAINING}
            score=sum(abs(predictions[p]['ipc']/observed['default',p]['ipc']-1) for p in TRAINING)/len(TRAINING)
            candidates.append(dict(penalty=penalty,training_mae_percent=100*score))
        chosen=min(candidates,key=lambda r:(r['training_mae_percent'],r['penalty']))
        base['branch_penalty']=chosen['penalty']
        (output/'frozen-config.json').write_text(json.dumps(base,indent=2)+'\n')
        models={}
        for variant,changes in VARIANTS.items():
            config=configuration(base,changes)
            path=output/(variant+'.json');path.write_text(json.dumps(config))
            for program in PROGRAMS:
                model=run(path,captures/'default'/program/'rvfi.jsonl')
                models[variant+'/'+program]=model
                print(variant,program,model['cycles'],flush=True)
        prepared=dict(base=base,candidates=candidates,chosen=chosen,models=models,
                      base_hashes={p:{f:sha256((captures/'default'/p/f).read_bytes()).hexdigest()
                                      for f in ('result.json','rvfi.jsonl')} for p in PROGRAMS})
        frozen.write_text(json.dumps(prepared,indent=2)+'\n')
    else:prepared=json.loads(frozen.read_text())
    base,candidates,chosen,models=(prepared[k] for k in ('base','candidates','chosen','models'))
    for p,files in prepared['base_hashes'].items():
        for f,digest in files.items():
            if sha256((captures/'default'/p/f).read_bytes()).hexdigest()!=digest:
                raise ValueError('frozen base input changed')
    expected={(v,p) for v in VARIANTS for p in PROGRAMS}
    missing=sorted(expected-set(observed))
    if missing and not allow_incomplete:
        print('Predictions frozen. RTL matrix is incomplete. No delta report.',flush=True)
        return
    # Recheck the engine on resume. Variant cycles never enter these predictions.
    check=run(output/'default.json',captures/'default'/PROGRAMS[0]/'rvfi.jsonl')
    if any(m['engine_sha256']!=check['engine_sha256'] for m in models.values()):
        raise ValueError('engine changed after predictions were frozen')
    for r in rtl:
        directory=captures/r['config']/r['program']
        for name,digest in r['hashes'].items():
            if sha256((directory/name).read_bytes()).hexdigest()!=digest:raise ValueError('capture hash changed')
        c1=json.loads((directory/'result.json').read_text())
        with (directory/'rvfi.jsonl').open() as stream:header=json.loads(stream.readline())
        if any(header[k]!=c1[k] for k in ('core','config','elf','elf_sha256','seed')):
            raise ValueError('C1/C2 identity mismatch')
        base_trace=captures/'default'/r['program']/'rvfi.jsonl'
        if _instructions(base_trace.read_bytes())!=_instructions((directory/'rvfi.jsonl').read_bytes()):
            raise ValueError('variant trace semantics differ from frozen base')
        if models[r['config']+'/'+r['program']]['instret']!=r['instret']:
            raise ValueError('model/C1 instruction count differs')
    rows=[];absolute=[]
    for p in PROGRAMS:
        m=models['default/'+p];b=observed['default',p]
        absolute.append(dict(program=p,split='training' if p in TRAINING else 'heldout',
                             rtl_ipc=b['ipc'],model_ipc=m['ipc'],ipc_error_percent=100*(m['ipc']/b['ipc']-1)))
        for variant in VARIANTS:
            if variant=='default' or (variant,p) not in observed:continue
            r=observed[variant,p];n=models[variant+'/'+p]
            measured=r['ipc']/b['ipc']-1;predicted=n['ipc']/m['ipc']-1
            error=delta_error(measured,predicted)
            rows.append(dict(program=p,variant=variant,rtl_ipc=r['ipc'],model_ipc=n['ipc'],
                             measured_delta_percent=100*measured,predicted_delta_percent=100*predicted,
                             direction_matches=error['sign_match'],criterion_met=not error['wrong_delta'],
                             model_events=n['events'],engine_sha256=n['engine_sha256']))
    result=dict(schema='ooo-mini.delta-matrix/1',status='inconclusive' if missing else 'reported',
                missing_captures=[dict(config=v,program=p) for v,p in missing],
                expected_pairs=(len(VARIANTS)-1)*len(PROGRAMS),scored_pairs=len(rows),
                accuracy_status='inconclusive',configuration_status='unchecked',
                engine_sha256=check['engine_sha256'],training=list(TRAINING),fit_candidates=candidates,
                selected=chosen,frozen_config=base,absolute=absolute,rows=rows,
                capture_summary_sha256=sha256((captures/'rtl-summary.json').read_bytes()).hexdigest(),
                limits=['nine short simulated programs; no whole-core qualification',
                        'component predictor updates at issue, while RTL trains at commit',
                        'Spike synchronizes benchmark counter reads; see RTL receipts',
                        'every prediction uses its frozen base C2; decoded trace semantics must match'])
    report='partial-model-summary.json' if missing else 'model-summary.json'
    (output/report).write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main(*sys.argv[1:])
