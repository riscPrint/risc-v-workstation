"""Fetch native wrong-path instructions through deterministic Spike replay."""
import json
from rvw.mcp.spec import ToolSpec,schema
from rvw.mcp.worker import run_function


def register(sub):
    p=sub.add_parser('ooo-wrong-path',help='measure the committed-path gap with real Spike wrong-path bytes')
    for key in ('config','trace','elf','platform'):p.add_argument(key)
    p.add_argument('--out',required=True)
    p.add_argument('--max-branches',type=int,default=256)
    p.add_argument('--max-wrong-instructions',type=int,default=16)
    p.add_argument('--max-cycles',type=int,default=1000000)
    p.add_argument('--json',action='store_true');p.set_defaults(func=command)


def command(args):
    from rvw.ooo.wrongpath import experiment
    try:
        keys=('config','trace','elf','platform','out','max_branches','max_wrong_instructions','max_cycles')
        print(json.dumps(experiment(**{k:getattr(args,k) for k in keys}),indent=2));return 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps({'error':str(exc)}));return 2


def mcp_tools():
    def handler(job,**kw):return run_function(job,'rvw.ooo.wrongpath','experiment',kw)
    fields={k:{'type':'string'} for k in ('config','trace','elf','platform','out')}
    fields.update({k:{'type':'integer','minimum':1} for k in ('max_branches','max_wrong_instructions','max_cycles')})
    return [ToolSpec('arch_ooo_wrong_path','Fetch real Spike wrong paths and compare bounded cache-side timing with committed-path modeling.',
                     schema(fields,['config','trace','elf','platform','out']),handler,long=True,
                     side_effects='writes-files',native_tools=('Spike',))]
