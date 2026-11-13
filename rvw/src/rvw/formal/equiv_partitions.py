"""Independent closed-cone proofs for automatically matched register boundaries."""
from copy import deepcopy
import contextlib
import json
import math
from pathlib import Path
import time

from rvw.common.proc import run_group


def projection(design, top, bits):
    result=deepcopy(design)
    module=result['modules'][top]
    name='partition_observation'
    if name in module['ports'] or name in module['netnames']:
        raise ValueError('partition observation name collision')
    module['ports']={n:p for n,p in module['ports'].items() if p['direction']=='input'}
    module['ports'][name]={'direction':'output','bits':list(bits)}
    module['netnames'][name]={'hide_name':0,'bits':list(bits),'attributes':{}}
    return result


def run(args):
    from rvw.cli import main
    from .equiv import state
    out=Path(args.out).resolve()
    out.mkdir(parents=True,exist_ok=False)
    started=time.monotonic()
    result={'schema':'rvw.equiv-partitions/1','status':'inconclusive','partitions':[],
            'scope':'automatically matched state observations; independent closed cones; no assumed internal cuts'}
    def budget():
        left=args.timeout-(time.monotonic()-started)
        if left<=0:raise ValueError('total partition proof time limit')
        return left
    def prove(gold,gate,target):
        command=['formal','equiv','--gold',*map(str,gold),'--gate',*map(str,gate),
                 '--top',args.top,'--clock',args.clock,'--unmatched-state','prove',
                 '--settle',str(args.settle),'--timeout',str(budget()),'--out',str(target),'--json']
        if args.reset:
            command+=['--reset',args.reset,'--reset-cycles',str(args.reset_cycles)]
        with (out/(target.name+'.log')).open('w') as log,contextlib.redirect_stdout(log):
            main(command)
        return json.loads((target/'result.json').read_text())
    try:
        if not math.isfinite(args.timeout) or args.timeout<=0:
            raise ValueError('positive finite timeout required')
        if args.max_partitions<1 or args.max_partitions>64:
            raise ValueError('max-partitions must be in 1..64')
        base=prove(args.gold,args.gate,out/'outputs')
        result['output_equivalence']=base['status']
        result['unmatched']=base.get('unmatched',{})
        if base['status']!='equivalent':
            result['status']=base['status']
            result['reason']='closed output proof did not establish equivalence'
        else:
            rows=base['state_mapping']
            if not rows:raise ValueError('no matched internal register observations')
            result['matched_count']=len(rows)
            result['omitted_count']=max(0,len(rows)-args.max_partitions)
            designs=[json.loads((out/'outputs'/side/'flat.json').read_text()) for side in ('gold','gate')]
            states=[state(d['modules'][args.top]) for d in designs]
            for index,row in enumerate(rows[:args.max_partitions]):
                directory=out/f'internal-{index}';directory.mkdir()
                sources=[]
                for side,design,inventory in zip(('gold','gate'),designs,states):
                    source=directory/(side+'.json');rtl=directory/(side+'.v')
                    source.write_text(json.dumps(projection(design,args.top,inventory[row[side]]))+'\n')
                    script=directory/(side+'.ys')
                    script.write_text(f'read_json {json.dumps(str(source))}\nwrite_verilog {json.dumps(str(rtl))}\n')
                    p=run_group(['nice','-n','10','yosys','-Q','-s',str(script)],timeout=budget(),capture=True)
                    (directory/(side+'.log')).write_text((p.stdout or '')+(p.stderr or ''))
                    if p.returncode:raise ValueError('state projection export failed')
                    sources.append([rtl])
                proof=prove(*sources,directory/'proof')
                result['partitions'].append({**row,'status':proof['status'],'result':str((directory/'proof/result.json').relative_to(out))})
            if not result['omitted_count'] and all(p['status']=='equivalent' for p in result['partitions']):
                result['status']='equivalent'
            else:
                result['reason']='internal observation relation failed, timed out or was omitted; output proof remains recorded separately'
    except (ValueError,OSError,KeyError,TypeError) as exc:
        result['reason']=str(exc)
    result['wall_s']=round(time.monotonic()-started,3)
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2) if args.json else f"equiv-partitions: {result['status']} ({out/'result.json'})")
    return 0 if result['status']=='equivalent' else 1
