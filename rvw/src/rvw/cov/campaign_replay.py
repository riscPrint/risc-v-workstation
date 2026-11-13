"""Replay archived candidate ELFs without changing campaign coverage or state."""
from pathlib import Path
import json
import os
import time
import uuid
from rvw.results.generation import open_generation
from .campaign_artifacts import seal_attempt


def replay_attempt(out,report,index,selected,data,manifest,source_root,platform):
    from . import campaign as controller
    if type(index) is not int or not 0<=index<len(report['attempts']):
        raise ValueError('replay index is outside the recorded attempt list')
    attempt=report['attempts'][index]
    result={'schema':'rvw.stimulus-replay/1','status':'unsupported','attempt':index,
            'goal':attempt['goal'],'seed':attempt.get('seed'),'credited_new_hits':[],
            'same_execution_identity':False,'expected_execution_identity':report.get('execution_identity'),
            'notes':['Replay does not change the original campaign state or credit new hits.',
                     'Failed runs are observations on the current configured model, not proof of original-context reproduction.']}
    seal=attempt.get('sealed_generation')
    if not seal or attempt.get('candidate',{}).get('status')!='generated':
        return result | {'reason':'attempt has no archived generated candidate'}
    generation=open_generation(out/seal['store'],seal['id'])
    elfs=[name for name in attempt['artifacts'] if Path(name).parts[-2:]==('elfs','program.elf')]
    if len(elfs)!=1:
        return result | {'reason':'attempt has no unique archived candidate ELF'}
    elf=generation.path/elfs[0]
    directory=out/'replays'/f'{index:04d}-{uuid.uuid4().hex}'
    directory.mkdir(parents=True)
    before,wall=os.times(),time.monotonic()
    try:
        suite=controller.Suite('closure',dir=elf.parent,glob='program.elf',strip_suffix='.elf',
            timeout_s=data.get('timeout_s',60),max_cycles=data.get('max_cycles',100000))
        controller.run_plan(selected,[controller.PlanItem(suite,data['config'])],directory/'run',
            controller.source_for(selected,None),controller.RunOptions(seeds=1,seed_base=attempt['seed'],
                rvfi_trace=True,use_cache=False,jobs=1,index=False,tier='closure'))
        coverage_plan=None
        if data.get('sequences') is not None:
            coverage_plan=directory/'coverage-plan.json'
            coverage_plan.write_text(json.dumps({'groups':[],'sequences':data['sequences']}))
        evidence=controller.qualify(elf,directory/'run',platform,manifest,source_root,
                                    attempt['candidate'],coverage_plan)
        result.update(evidence)
        current=evidence.get('execution_identity')
        result['same_execution_identity']=bool(current and current==report.get('execution_identity'))
        if evidence['status']=='qualified' and not result['same_execution_identity']:
            result.update(status='identity_error',reason='replay execution identity differs or was not previously qualified')
    except (OSError,ValueError,KeyError,TypeError) as exc:
        result.update(status='inconclusive',reason=str(exc))
    except BaseException:
        result.update(status='interrupted',reason='replay cancelled; cost may be incomplete')
        raise
    finally:
        after=os.times()
        result.update(elapsed_s=time.monotonic()-wall,
            controller_cpu_s=after.user+after.system-before.user-before.system,
            reaped_child_cpu_s=after.children_user+after.children_system-before.children_user-before.children_system,
            cpu_accounting='inconclusive',replay_directory=str(directory))
        (directory/'replay.json').write_text(json.dumps(result,indent=2)+'\n')
        result['artifacts']={str(p.relative_to(out)):controller.digest(p) for p in sorted(directory.rglob('*')) if p.is_file()}
        result['sealed_generation']=seal_attempt(out,directory,result)
    return result
