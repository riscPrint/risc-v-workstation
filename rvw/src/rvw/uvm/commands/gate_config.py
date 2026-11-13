"""Generate a C4 config for a source-bound compiled SV bench."""
import json
from pathlib import Path
from rvw.uvm.gate import configure
from rvw.mcp.spec import ToolSpec,schema

def command(a):
    try:
        print(json.dumps(configure(a.build,a.source_repo,a.out,seeds=a.seeds)));return 0
    except (OSError,ValueError,KeyError) as exc:
        print(json.dumps({'error':str(exc)}));return 2

def register(sub):
    p=sub.add_parser('gate-config',help='bind a compiled pure SV UVM bench to C4')
    p.add_argument('--build',type=Path,required=True)
    p.add_argument('--source-repo',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--seeds',nargs='+',type=int,default=[1,3]);p.set_defaults(func=command)

def mcp_tools():
    string={'type':'string'}
    return [ToolSpec('uvm_gate_config','Bind a pure SV UVM build to a C4 build suite.',
        schema({'build_dir':string,'source_repo':string,'out':string,'seeds':{'type':'array','items':{'type':'integer'}}},
               ['build_dir','source_repo','out']),configure, side_effects='writes generated files under out', native_tools=())]
