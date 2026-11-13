"""Slow detection-power regression tier."""
import json
from rvw.cov.mutation_regression import execute


def run(args):
    try:result=execute(args.work_dir,args.expectations,args.budget_s)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(json.dumps(dict(status='error',reason=str(exc))));return 2
    print(json.dumps(result,indent=2))
    return {'pass':0,'fail':1}.get(result['status'],3)


def register(sub):
    p=sub.add_parser('mutation',help='slow tier: rerun pinned mutants and check expected killers')
    p.add_argument('--work-dir',required=True);p.add_argument('--expectations',required=True)
    p.add_argument('--budget-s',type=float,default=120);p.add_argument('--json',action='store_true')
    p.set_defaults(func=run)


def mcp_tools():
    from rvw.mcp.spec import ToolSpec,schema
    return [ToolSpec('regress_mutation','Rerun a project-pinned mutant plan and check every expected first killer.',
        schema({'work_dir':{'type':'string'},'expectations':{'type':'string'},'budget_s':{'type':'number'}},
               ['work_dir','expectations']),execute,long=True,
        side_effects='runs mutation build/test/equivalence commands; replaces campaign results',native_tools=())]
