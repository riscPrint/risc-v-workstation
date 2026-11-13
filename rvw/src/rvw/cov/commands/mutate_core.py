"""Whole-core mutation campaign CLI and MCP."""
import json
from rvw.cov.core_mutation import prepare, run_campaign


def execute(manifest=None, work_dir=None, count=60, budget_s=120, resume=False, prepare_only=False):
    if manifest:
        plan=prepare(manifest, work_dir, count)
        if prepare_only: return dict(status="prepared",mutants=len(plan["mutants"]))
    return run_campaign(work_dir, budget_s, resume)


def run(args):
    try: result=execute(args.manifest,args.work_dir,args.count,args.budget_s,args.resume,args.prepare_only)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(json.dumps(dict(status='error',reason=str(exc)))); return 2
    print(json.dumps(result,indent=2))
    return 0 if result['status'] in ('complete','prepared') else 3


def register(sub):
    p=sub.add_parser('mutate-core',help='run a serial exported-RTL mutation campaign')
    p.add_argument('--manifest');p.add_argument('--work-dir',required=True)
    p.add_argument('--count',type=int,default=60);p.add_argument('--budget-s',type=float,default=120)
    p.add_argument('--prepare-only',action='store_true');p.add_argument('--resume',action='store_true');p.add_argument('--json',action='store_true')
    p.set_defaults(func=run)


def mcp_tools():
    from rvw.mcp.spec import ToolSpec,schema
    return [ToolSpec('cov_mutate_core','Build each exported RTL mutant once; run ordered test tiers with explicit detection evidence.',
        schema({'manifest':{'type':'string'},'work_dir':{'type':'string'},'count':{'type':'integer'},
                'budget_s':{'type':'number'},'resume':{'type':'boolean'},'prepare_only':{'type':'boolean'}},['work_dir']),
        execute,long=True,side_effects='launches project builds, simulations and equivalence; writes campaign files',native_tools=())]
