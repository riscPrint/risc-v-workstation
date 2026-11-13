"""ACT4 build entry point."""
import json
from pathlib import Path
from rvw.regress.act4 import build, selection
from rvw.mcp.spec import ToolSpec, schema


def register(commands):
    p = commands.add_parser('act4-build', help='build pinned ACT4 tests with independent Sail signatures')
    for name in ('profile', 'checkout', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--timeout', type=int, default=900)
    p.add_argument('--compiler', default='riscv64-unknown-elf-gcc')
    p.add_argument('--reference', default='sail_riscv_sim')
    p.add_argument('--json', action='store_true')
    def run(a):
        try:
            report = build(a.profile, a.checkout, a.out, a.timeout, a.compiler, a.reference)
        except (ValueError, OSError, KeyError) as exc:
            import sys
            print(f'rvw regress act4-build: {exc}', file=sys.stderr)
            return 2
        print(json.dumps(report))
        return 0 if report['status'] == 'built' else 1
    p.set_defaults(func=run)


def mcp_tools():
    return [ToolSpec('regress_act4_plan', 'Select ACT4 extensions from project data. No DUT evidence.',
                     schema({'profile': {'type': 'string'}}, ['profile']), selection,
                     annotations={'readOnlyHint': True}, side_effects='read-only', native_tools=()),
            ToolSpec('regress_act4_build', 'Build pinned ACT4 tests. Sail supplies expected signatures; no DUT execution.',
                     schema({k: {'type': 'string'} for k in ('profile', 'checkout', 'out')}, ['profile', 'checkout', 'out']),
                     build, side_effects='writes build outputs', native_tools=('Sail', 'RISC-V GCC'))]
