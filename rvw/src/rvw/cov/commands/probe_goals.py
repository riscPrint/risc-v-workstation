"""Qualified probe event and sequence goals."""
import json
from rvw.cov.probe_goals import probe_goals


def run(args):
    try:
        result=probe_goals(args.result,args.plan,args.platform)
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps({'status':'error','message':str(exc)}));return 2
    print(json.dumps(result,indent=2));return 0


def register(sub):
    p=sub.add_parser('probe-goals',help='measure event and bounded sequence goals from qualified probe streams')
    for key in ('result','plan','platform'):p.add_argument('--'+key,required=True)
    p.add_argument('--json',action='store_true');p.set_defaults(func=run)


def mcp_tools():
    from rvw.mcp.spec import ToolSpec,schema
    return [ToolSpec('cov_probe_goals','Measure project probe goals after complete strict Spike qualification.',
        schema({k:{'type':'string'} for k in ('result','plan','platform')},['result','plan','platform']),
        probe_goals,isolate=True,side_effects='read-only',native_tools=('Spike',))]
