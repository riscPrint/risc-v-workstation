"""Measured C1 artifact feedback for a bounded stimulus controller."""
from pathlib import Path
from rvw.results import load_run
from rvw.regress.random_stream import digest
from .rtl import sample


def collect(guide, goal, elf, run_dir, plan_path, qualified):
    if not qualified:
        reason = 'execution did not pass complete reference qualification'
    else:
        runs = [r for p in Path(run_dir).rglob('result.json') if (r:=load_run(p)).elf_sha256==digest(elf)]
        if len(runs)!=1:
            reason = 'no unique C1 execution for RTL feedback'
        else:
            run = runs[0]
            artifact = run.artifact('rtl_samples')
            if run.why_inconclusive or run.status!='pass':
                reason = 'C1 execution is not a conclusive pass'
            elif artifact is None:
                reason = 'core adapter has no rtl_samples hook'
            else:
                try:
                    trace = run.artifact('rvfi_trace')
                    receipt = run.extra.get('details',{}).get('rtl_samples')
                    expected = {'elf_sha256':digest(elf),'rvfi_sha256':digest(trace) if trace else None,
                                'samples_sha256':digest(artifact),'plan_id':guide.plan_id,'rtl_sha256':guide.design}
                    if trace is None or receipt != expected:
                        raise ValueError('RTL samples lack an exact C1 ELF/trace/plan receipt')
                    report = sample(plan_path,[artifact])
                    return guide.observe(goal,report,qualified=True,rtl_sha256=run.extra.get('rtl_sha256')) | {
                        'status':'observed', 'report':report, 'c1_sha256':digest(run.path/'result.json')}
                except (OSError,ValueError,KeyError) as exc:
                    reason = str(exc)
    record = {'goal':goal,'new_events':[],'samples':[],'status':'unsupported','reason':reason}
    guide.history.append(record)
    return record
