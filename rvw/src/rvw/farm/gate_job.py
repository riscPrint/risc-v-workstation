"""Queue transport for the unchanged regress gate. C4 decides acceptance."""
import argparse
import json
from pathlib import Path
from rvw.results import write_json
from .gate_intake import intake


def execute(base,candidate,project,tier='quick',out=None,rvfi_trace=False):
    captured=dict(base=intake(base),candidate=intake(candidate))
    from rvw.regress.config import load_config
    from rvw.regress.plan import gate
    from rvw.regress.runner import RunOptions
    core=load_config(None,project=project)
    destination=Path(out) if out else Path(candidate)/'verdict.json'
    result=gate(core,tier,None,None,str(base),str(candidate),None,
                RunOptions(jobs=1,rvfi_trace=rvfi_trace,use_cache=False,results_root=destination.parent),
                core.known_failures,None,out=destination)
    verdict=result['verdict']
    verdict.extra['farm_intake']=captured
    write_json(destination,verdict.to_dict())
    return verdict.to_dict()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('base','candidate','project','out'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--tier',default='quick')
    parser.add_argument('--rvfi-trace',action='store_true')
    args=parser.parse_args()
    directory=Path(args.out);directory.mkdir(parents=True,exist_ok=True)
    try:
        verdict=execute(args.base,args.candidate,args.project,args.tier,directory/'verdict.json',args.rvfi_trace)
        report=dict(schema='rvw.farm-gate/1',status='complete',recorded_verdict=verdict['verdict'])
    except (ValueError,OSError) as error:
        report=dict(schema='rvw.farm-gate/1',status='inconclusive',error=str(error))
    write_json(directory/'collection.json',report)
    print(json.dumps(report))
    return 0 if report['status']=='complete' else 3


if __name__=='__main__':raise SystemExit(main())
