"""Generate and package project-bound RTL transaction observations."""
import json
from pathlib import Path
import sys

from rvw.mcp.spec import ToolError,ToolSpec,schema


def register(subparsers):
    for name in ('observe','observe-pack'):
        command=subparsers.add_parser(name,help='generate or package observed RTL transaction tags')
        for option in (('binding','out') if name=='observe' else ('binding','pins','trace','result','out')):
            command.add_argument('--'+option,required=True)
        command.add_argument('--json',action='store_true')
        command.set_defaults(func=main,observe_action=name)


def main(args):
    from rvw.soc.observer import generate,pack
    try:
        if args.observe_action=='observe':
            result=generate(args.binding,args.out);code=0
        else:
            result=pack(args.binding,args.pins,args.trace,args.result,args.out)
            code=1 if result['status']=='mismatch' else 3
        print(json.dumps(result) if args.json else result['status'])
        return code
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps(dict(status='error',error=str(exc))))
        return 2


def run(job,command,**args):
    argv=[sys.executable,'-m','rvw','soc',command,'--json']
    for key,value in args.items():argv+=['--'+key,str(value)]
    code=job.run(argv)
    if command=='observe':
        if code:raise ToolError('RTL observer generation failed',{'exit_code':code,'log_tail':job.tail(20)})
        return json.loads((Path(args['out'])/'result.json').read_text())
    if code not in (1,3):raise ToolError('RTL pin packaging failed',{'exit_code':code,'log_tail':job.tail(20)})
    from rvw.soc.pairing import check
    return check(args['out'],args['trace'],args['result'])


def generate_job(job,**args):return run(job,'observe',**args)
def pack_job(job,**args):return run(job,'observe-pack',**args)


def mcp_tools():
    result=[]
    for command,names,handler in [('observe',['binding','out'],generate_job),
                                  ('observe_pack',['binding','pins','trace','result','out'],pack_job)]:
        result.append(ToolSpec('soc_'+command,'Generate or package independently sampled RTL transaction tags. Matching samples remain inconclusive.',
                              schema({name:{'type':'string'} for name in names},names),handler,long=True))
    return result
