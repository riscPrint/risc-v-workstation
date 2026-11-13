import json
from rvw.mcp.spec import ToolSpec, schema


def register(sub):
    p = sub.add_parser('campaign', help='run or resume a coverage-guided paired leakage campaign')
    p.add_argument('--manifest', required=True); p.add_argument('--out', required=True)
    p.add_argument('--resume', action='store_true', help='continue the campaign in --out until its budget')
    p.set_defaults(func=execute)


def calculate(manifest, out, resume=False):
    from rvw.sec.campaign import run
    return run(manifest, out, resume)


def execute(args):
    try:
        r = calculate(args.manifest, args.out, args.resume)
        print(json.dumps({k: v for k, v in r.items() if k != 'findings'} | {'signatures': [f['signature'] for f in r['findings']]}, indent=2))
        return {'violation': 1, 'inconclusive': 3}.get(r['status'], 0)
    except (ValueError, OSError, KeyError) as e:
        print(str(e)); return 2


def mcp_tools():
    return [ToolSpec('sec_campaign', 'Run or resume a coverage-guided paired leakage campaign with reduction and deduplication.',
                     schema({'manifest': {'type': 'string'}, 'out': {'type': 'string'}, 'resume': {'type': 'boolean'}},
                            ['manifest', 'out']), calculate, long=True,
                     side_effects='writes-files', native_tools=('Verilator', 'Spike', 'RISC-V GCC'))]
