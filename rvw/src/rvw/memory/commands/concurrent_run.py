"""Run generated concurrent programs through an explicit project adapter."""
from pathlib import Path
from rvw.memory.concurrent_campaign import run
from rvw.mcp.spec import ToolSpec, schema


def register(commands):
    p=commands.add_parser('concurrent-run',help=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--adapter',required=True)
    p.add_argument('--config',required=True)
    p.add_argument('--seed',type=int,default=1)
    p.add_argument('--harts',type=int,default=2)
    p.add_argument('--length',type=int,default=16)
    p.add_argument('--model',choices=('rvwmo','ztso'),default='rvwmo')
    p.add_argument('--gcc',default='riscv64-unknown-elf-gcc')
    p.add_argument('--max-cycles',type=int,default=20000)
    p.add_argument('--timeout',type=float,default=60)
    p.add_argument('--limit',type=int,default=100000)
    p.add_argument('--base',type=lambda s:int(s,0),default=0x80000000)
    p.add_argument('--shared-base',type=lambda s:int(s,0),default=0x81000000)
    def command(args):
        from rvw.memory.cli import emit
        return emit(lambda: run(args.out,args.adapter,args.config,args.seed,args.harts,args.length,args.model,
                                args.gcc,args.max_cycles,args.timeout,args.limit,args.base,args.shared_base))
    p.set_defaults(func=command)


def mcp_tools():
    return [ToolSpec('memory_concurrent_run','Build seeded per-hart programs, invoke a project C1 adapter and check its captured C2 under RVWMO or Ztso.',
                     schema({'out':{'type':'string'},'adapter':{'type':'string'},'config':{'type':'string'},
                             'seed':{'type':'integer','default':1},'harts':{'type':'integer','default':2},
                             'length':{'type':'integer','default':16},'model':{'type':'string','default':'rvwmo'},
                             'gcc':{'type':'string','default':'riscv64-unknown-elf-gcc'},
                             'max_cycles':{'type':'integer','default':20000},'timeout':{'type':'number','default':60},
                             'limit':{'type':'integer','default':100000},'base':{'type':'string','default':'0x80000000'},
                             'shared_base':{'type':'string','default':'0x81000000'}},required=['out','adapter','config']),run)]
