import json
from rvw.mcp.spec import ToolSpec, schema


def register(sub):
    p = sub.add_parser('model-check', help='predict contract-pair leakage on the OoO timing model before RTL')
    p.add_argument('--manifest', required=True); p.add_argument('--out', required=True)
    p.set_defaults(func=execute)


def calculate(manifest, out):
    from rvw.sec.model_check import run
    return run(manifest, out)


def execute(args):
    try:
        r = calculate(args.manifest, args.out)
        print(json.dumps(r, indent=2))
        return {'violation': 1, 'inconclusive': 3}.get(r['status'], 0)
    except (ValueError, OSError, KeyError) as e:
        print(str(e)); return 2


def mcp_tools():
    return [ToolSpec('sec_model_check', 'Predict contract-pair timing leakage on the OoO model from Spike traces.',
                     schema({'manifest': {'type': 'string'}, 'out': {'type': 'string'}}, ['manifest', 'out']),
                     calculate, long=True, side_effects='writes-files', native_tools=('Spike', 'RISC-V GCC'))]
