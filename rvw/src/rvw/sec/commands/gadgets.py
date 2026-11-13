import json
from rvw.mcp.spec import ToolSpec, schema


def register(sub):
    p=sub.add_parser('gadgets',help='generate speculative gadget and receiver assembly')
    p.add_argument('--out',required=True);p.add_argument('--seed',type=int,default=1)
    p.add_argument('--threshold',type=int,default=10)
    p.add_argument('--declares-speculation',action='store_true')
    p.set_defaults(func=execute)


def execute(a):
    print(json.dumps(generate(a.out,a.seed,a.threshold,a.declares_speculation),indent=2));return 0


def mcp_tools():
    return [ToolSpec('sec_gadgets','Generate v1, v2, v4 and return-predictor gadget templates.',
                    schema({'out':{'type':'string'},'seed':{'type':'integer'},
                            'threshold':{'type':'integer'},'declares_speculation':{'type':'boolean'}},['out']),generate,
        side_effects='writes assembly templates under out', native_tools=(),
        )]


def generate(out, seed=1, threshold=10, declares_speculation=False):
    """Load the handler on first use."""
    from rvw.sec.gadgets import generate as implementation
    return implementation(out, seed, threshold, declares_speculation)
