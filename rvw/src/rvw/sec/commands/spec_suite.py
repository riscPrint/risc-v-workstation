from pathlib import Path
import json
from rvw.mcp.spec import ToolSpec, schema


def register(sub):
    p = sub.add_parser('spec-suite', help='run RV32 speculative-leakage self-tests on a bound core')
    p.add_argument('--binding', required=True, help='rvw.sec-core/1 project binding')
    p.add_argument('--template', required=True, help='case template with sec_probe, sec_slot and sec_public')
    p.add_argument('--out', required=True)
    p.add_argument('--gadget', action='append', help='gadget name; repeat (default: all)')
    p.set_defaults(func=execute)


def calculate(binding, template, out, gadget=None):
    from rvw.sec.spec_suite import run
    command = ['{python}', '-m', 'rvw.sec.core_adapter', '--binding', str(Path(binding).resolve()),
               '--template', str(Path(template).resolve()), '{request}', '{out}']
    return run(command, out, gadgets=gadget)


def execute(args):
    try:
        r = calculate(args.binding, args.template, args.out, args.gadget)
        print(json.dumps(r, indent=2))
        return {'violation': 1, 'inconclusive': 3}.get(r['status'], 0)
    except (ValueError, OSError, KeyError) as e:
        print(str(e)); return 2


def mcp_tools():
    return [ToolSpec('sec_spec_suite', 'Run RV32 speculative-leakage self-tests on a bound core in Verilator.',
                     schema({'binding': {'type': 'string'}, 'template': {'type': 'string'}, 'out': {'type': 'string'},
                             'gadget': {'type': 'array', 'items': {'type': 'string'}}},
                            ['binding', 'template', 'out']), calculate, long=True,
                     side_effects='writes-files', native_tools=('Verilator', 'Yosys', 'Spike', 'RISC-V GCC'))]
