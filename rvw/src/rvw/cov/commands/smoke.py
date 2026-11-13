"""Measured coverage minimisation and budgeted C1 smoke execution."""
import json
from rvw.cov.smoke import execute_json


def run(args):
    try:r=execute_json(args.database,args.budget_s,args.startup_s,args.run,getattr(args,'project',None),args.work_dir)
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps({'status':'error','message':str(exc)}));return 2
    print(json.dumps(r,indent=2))
    if r['status']=='fail':return 1
    return 3 if r['status'] in ('timed_out','inconclusive','no_tests') else 0


def register(sub):
    p=sub.add_parser('smoke',help='select measured coverage within a time estimate; optional adapter deadline')
    p.add_argument('--database',required=True);p.add_argument('--budget-s',type=float,required=True)
    p.add_argument('--startup-s',type=float,default=0);p.add_argument('--run',action='store_true')
    p.add_argument('--work-dir');p.add_argument('--json',action='store_true')
    p.set_defaults(func=run)


def mcp_tools():
    from rvw.mcp.spec import ToolSpec,schema
    return [ToolSpec('cov_smoke','Minimise measured coverage and select a budgeted suite; optional C1 deadline.',
        schema({'database':{'type':'string'},'budget_s':{'type':'number'},'startup_s':{'type':'number'},
                'run':{'type':'boolean'},'project':{'type':'string'},'work_dir':{'type':'string'}},['database','budget_s']),
        execute_json,isolate=True,side_effects='writes-files when run is true; read-only otherwise',native_tools=())]
