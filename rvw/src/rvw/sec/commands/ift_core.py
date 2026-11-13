from pathlib import Path
import json
from rvw.mcp.spec import ToolSpec, schema


def register(sub):
    p = sub.add_parser('ift-core', help='track secret memory words and registers through a whole core')
    p.add_argument('--binding', required=True, help='rvw.sec-core/1 project binding')
    p.add_argument('--policy', required=True, help='memory regions, register sources and output sinks')
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--elf'); g.add_argument('--asm', help='assembly source linked with the binding link script')
    p.add_argument('--out', required=True)
    p.add_argument('--mode', choices=('precise', 'conservative'), default='precise')
    p.add_argument('--soc', help='rvw.soc/1 map for soc_region entries (default: binding "soc")')
    p.set_defaults(func=execute)


def calculate(binding, policy, out, elf=None, asm=None, mode='precise', soc=None):
    from rvw.sec import ift_core, rtl
    from rvw.sec.core_adapter import compile_elf
    if asm:
        folder = Path(out).resolve().parent/(Path(out).name+'.elf'); folder.mkdir(parents=True, exist_ok=True)
        elf = compile_elf(Path(asm).resolve(), folder, rtl.load(binding))
    return ift_core.run(binding, policy, elf, out, mode, soc=soc)


def execute(args):
    try:
        r = calculate(args.binding, args.policy, args.out, args.elf, args.asm, args.mode, args.soc)
        print(json.dumps(r, indent=2))
        return {'violation': 1, 'inconclusive': 3}.get(r['status'], 0)
    except (ValueError, OSError, KeyError) as e:
        print(str(e)); return 2


def mcp_tools():
    return [ToolSpec('sec_ift_core', 'Track secret memory words and registers through a whole core in Verilator.',
                     schema({'binding': {'type': 'string'}, 'policy': {'type': 'string'}, 'out': {'type': 'string'},
                             'elf': {'type': 'string'}, 'asm': {'type': 'string'},
                             'mode': {'type': 'string', 'enum': ['precise', 'conservative']}, 'soc': {'type': 'string'}},
                            ['binding', 'policy', 'out']), calculate, long=True,
                     side_effects='writes-files', native_tools=('Verilator', 'Yosys', 'Spike', 'RISC-V GCC'))]
