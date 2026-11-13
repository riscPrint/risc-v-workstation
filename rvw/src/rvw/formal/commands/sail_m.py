"""Sail RV32 M arithmetic expression generation."""
import json
from pathlib import Path


def main(args):
    from rvw.formal.sail_m import generate
    try:
        result=generate(args.model,args.compiler,args.out)
        print(json.dumps(result) if args.json else str(Path(args.out)/'manifest.json'))
        return 0
    except (ValueError,OSError,KeyError) as exc:
        print(json.dumps(dict(status='error',error=str(exc))))
        return 2


def register(subparsers):
    p=subparsers.add_parser('sail-m',help='compile pinned Sail RV32 multiply, divide and remainder expressions')
    p.add_argument('--model',required=True)
    p.add_argument('--compiler',default='sail')
    p.add_argument('--out',required=True)
    p.add_argument('--json',action='store_true')
    p.set_defaults(func=main)


def mcp_run(job, **args):
    from rvw.formal.mcp_tools import _argv
    from rvw.mcp.spec import ToolError
    code=job.run(_argv('sail-m',args))
    if code: raise ToolError('Sail M generation failed',{'exit_code':code,'log_tail':job.tail(30)})
    return json.loads((Path(args['out'])/'manifest.json').read_text())


def mcp_tools():
    from rvw.mcp.spec import ToolSpec,schema
    return [ToolSpec('formal_sail_m','Compile pinned Sail RV32 M arithmetic expressions. Generation is not a core proof.',
                     schema({k:{'type':'string'} for k in ('model','compiler','out')},['model','out']),mcp_run,long=True,side_effects="writes-files",native_tools=())]
