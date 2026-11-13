"""Measured C1 artifact feedback for a bounded stimulus controller."""
from pathlib import Path
from rvw.regress.run_evidence import owned_run_paths
from rvw.results import load_run
from rvw.regress.random_stream import digest
from .rtl import sample


def collect(guide, goal, elf, run_dir, plan_path, qualified, platform=None):
    if not qualified:
        reason = 'execution did not pass complete reference qualification'
    else:
        runs = [r for p in owned_run_paths(run_dir) if (r:=load_run(p)).elf_sha256==digest(elf)]
        if len(runs)!=1:
            reason = 'no unique C1 execution for coverage feedback'
        else:
            run = runs[0]
            artifact_name='coverage' if guide.kind=='code' else 'probe_events' if guide.kind=='probe' else 'rtl_samples'
            artifact = run.artifact(artifact_name)
            if run.why_inconclusive or run.status!='pass':
                reason = 'C1 execution is not a conclusive pass'
            elif artifact is None:
                reason = 'core adapter has no '+artifact_name+' hook'
            else:
                try:
                    if guide.kind=='probe':
                        from .probe_goals import probe_goals
                        report=probe_goals(run.path/'result.json',plan_path,platform)
                        return guide.observe(goal,report,qualified=True,rtl_sha256=run.extra.get('rtl_sha256')) | {
                            'status':'observed','report':report,'c1_sha256':digest(run.path/'result.json')}
                    trace = run.artifact('rvfi_trace')
                    receipt = run.extra.get('details',{}).get('coverage_goals' if guide.kind=='code' else 'rtl_samples')
                    expected = {'elf_sha256':digest(elf),'rvfi_sha256':digest(trace) if trace else None,
                                'samples_sha256':digest(artifact),'plan_id':guide.plan_id,'rtl_sha256':guide.design}
                    if guide.kind=='code':
                        expected['reset_at_start']=True
                        if not isinstance(receipt,dict) or receipt.get('reset_at_start') is not True:
                            raise ValueError('code counters lack a reset-at-start receipt')
                    if trace is None or receipt != expected:
                        raise ValueError('coverage samples lack an exact C1 ELF/trace/plan receipt')
                    if guide.kind=='code':
                        from .code import merge
                        report=merge([str(run.path/'result.json')],root=guide.database['source_root'])
                    else:
                        report = sample(plan_path,[artifact])
                    return guide.observe(goal,report,qualified=True,rtl_sha256=run.extra.get('rtl_sha256')) | {
                        'status':'observed', 'report':report, 'c1_sha256':digest(run.path/'result.json')}
                except (OSError,ValueError,KeyError) as exc:
                    reason = str(exc)
    record = {'goal':goal,'new_events':[],'samples':[],'status':'unsupported','reason':reason}
    guide.history.append(record)
    return record
