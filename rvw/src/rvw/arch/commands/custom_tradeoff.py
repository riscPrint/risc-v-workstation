"""Compare a custom extension under one declared workload identity."""
import json
from rvw.mcp.spec import ToolSpec,schema
from rvw.mcp.worker import run_function


def register(sub):
    p=sub.add_parser('custom-tradeoff');p.add_argument('plan');p.add_argument('--out',required=True)
    p.add_argument('--json',action='store_true');p.set_defaults(func=command)


def command(args):
    from rvw.arch.custom_tradeoff import tradeoff
    try:
        print(json.dumps(tradeoff(args.plan,args.out),indent=2));return 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps({'error':str(exc)}));return 2


def mcp_tools():
    def handler(job,**kw):return run_function(job,'rvw.arch.custom_tradeoff','tradeoff',kw)
    return [ToolSpec('arch_custom_tradeoff','Join extension timing, software cost and saved RTL/PPA evidence.',
                     schema({k:{'type':'string'} for k in ['plan','out']},['plan','out']),handler,long=True)]
