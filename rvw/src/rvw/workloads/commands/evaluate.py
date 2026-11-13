"""Default open workload evaluation set."""
import json
from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import run_function


def mappings(values):
    result = {}
    for value in values:
        key,path = value.split('=',1)
        if key in result:
            raise ValueError('duplicate recipe mapping: '+key)
        result[key] = path
    return result


def register(sub):
    p = sub.add_parser('evaluate',help='build and Spike-trace the default sampled workload set')
    p.add_argument('--source',action='append',default=[],metavar='RECIPE=PATH')
    p.add_argument('--build',action='append',default=[],metavar='RECIPE=BUILD_JSON')
    p.add_argument('--trace',action='append',default=[],metavar='WORKLOAD=C2')
    p.add_argument('--manifest');p.add_argument('--out',required=True)
    p.add_argument('--timeout',type=int,default=600);p.add_argument('--json',action='store_true')
    p.set_defaults(func=command)


def command(args):
    from rvw.workloads.evaluation import evaluate
    try:
        print(json.dumps(evaluate(args.out,mappings(args.source),mappings(args.build),args.manifest,args.timeout,mappings(args.trace)),indent=2))
        return 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps({'error':str(exc)}));return 2


def mcp_tools():
    def handler(job, **kw):
        return run_function(job,'rvw.workloads.evaluation','evaluate',kw)
    fields={'out':{'type':'string'},'manifest':{'type':'string'},
            'sources':{'type':'object','additionalProperties':{'type':'string'}},
            'builds':{'type':'object','additionalProperties':{'type':'string'}},
            'traces':{'type':'object','additionalProperties':{'type':'string'}},
            'timeout':{'type':'integer','minimum':1}}
    return [ToolSpec('workloads_evaluate','Build pinned workloads, check Spike outputs, capture C2 and time shared simulation points. Approximate model evidence.',
                     schema(fields,['out']),handler,long=True,side_effects="writes-files",native_tools=("Spike", "RISC-V GCC"))]
