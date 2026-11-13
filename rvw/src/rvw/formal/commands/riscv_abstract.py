"""Run conditional instruction experiments with the shared RAM abstraction."""
import json
from pathlib import Path


def main(args):
    from rvw.common.project import load_project
    from rvw.formal.common import sigterm_raises
    from rvw.formal.riscv_abstract import run
    try:
        project=load_project(getattr(args,'project',None))
        if project is None: raise ValueError('select a riscv_formal project')
        cfg=dict(project.sections['riscv_formal'])
        cfg['checks']=(args.checks.split(',') if args.checks else [c for c in cfg['checks'] if c.startswith('insn_')])+['cover']
        cfg['check_options']={k:v for k,v in cfg.get('check_options',{}).items() if k in cfg['checks']}
        plan=json.loads(Path(args.manifest).read_text())
        if args.engines: plan['engines']=args.engines.split(',')
        with sigterm_raises():
            result=run(cfg,plan,args.out,timeout=args.timeout,budget=args.budget)
        print(json.dumps(result) if args.json else str(Path(args.out)/'result.json'))
        return 1 if result['status']=='fail' else 3
    except (ValueError,OSError,KeyError) as exc:
        print(json.dumps(dict(status='error',error=str(exc))))
        return 2


def register(subparsers):
    p=subparsers.add_parser('riscv-abstract',help='run conditional RVFI proofs with selected pipeline and RAM reductions')
    p.add_argument('--manifest',required=True)
    p.add_argument('--out',required=True)
    p.add_argument('--engines',help='comma-separated proof engines; default: manifest selection')
    p.add_argument('--checks',help='comma-separated instruction checks')
    p.add_argument('--timeout',type=float,default=120)
    p.add_argument('--budget',type=float,default=240,help='reduction phase budget per check; concrete cover is separate')
    p.add_argument('--json',action='store_true')
    p.set_defaults(func=main)


def mcp_run(job, **args):
    from rvw.formal.mcp_tools import _argv
    from rvw.mcp.spec import ToolError
    code=job.run(_argv('riscv-abstract',args))
    if code not in (1,3): raise ToolError('instruction abstraction failed',{'exit_code':code,'log_tail':job.tail(30)})
    result=json.loads((Path(args['out'])/'result.json').read_text())
    if result.get('schema')!='rvw.riscv-abstract/1' or result.get('status')!={1:'fail',3:'inconclusive'}[code]:
        raise ToolError('invalid instruction abstraction result')
    return result


def mcp_tools():
    from rvw.mcp.spec import ToolSpec,schema
    return [ToolSpec('formal_riscv_abstract','Run declared single-flight instruction proofs with RAM abstraction. Results remain conditional.',
                     schema({'project':{'type':'string'},'manifest':{'type':'string'},'out':{'type':'string'},'checks':{'type':'string'},'engines':{'type':'string'},
                             'timeout':{'type':'number','exclusiveMinimum':0},'budget':{'type':'number','exclusiveMinimum':0}},['manifest','out']),
                     mcp_run,long=True,side_effects='writes-files',native_tools=())]
