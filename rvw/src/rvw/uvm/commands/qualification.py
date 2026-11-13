import json
from pathlib import Path
from rvw.mcp.spec import ToolSpec,schema

def command(a):
    try: print(json.dumps(generate(a.cpu_results,a.probes,a.out)));return 0
    except (OSError,ValueError,KeyError) as exc: print(json.dumps({'error':str(exc)}));return 2

def register(sub):
    p=sub.add_parser('qualification',help='render native SV CPU and engine probe evidence')
    p.add_argument('--cpu-results',required=True,type=Path);p.add_argument('--probes',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path);p.set_defaults(func=command)

def mcp_tools():
    string={'type':'string'}
    return [ToolSpec('uvm_qualification','Render measured SV CPU and feature-probe qualification.',
        schema({'cpu_results':string,'probes':string,'out':string},['cpu_results','probes','out']),generate, side_effects='writes generated files under out', native_tools=())]


def generate(cpu_results, probes, out):
    """Load the handler on first use."""
    from rvw.uvm.qualification import generate as implementation
    return implementation(cpu_results, probes, out)
