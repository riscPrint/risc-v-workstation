"""Build concurrent programs for per-hart project adapters."""
from pathlib import Path
from rvw.memory.concurrent_build import build
from rvw.mcp.spec import ToolSpec, schema


def register(commands):
    p = commands.add_parser('concurrent-build', help=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--seed', type=int, default=1)
    p.add_argument('--harts', type=int, default=2)
    p.add_argument('--length', type=int, default=16)
    p.add_argument('--gcc', default='riscv64-unknown-elf-gcc')
    p.add_argument('--base', type=lambda s: int(s, 0), default=0x80000000)
    p.add_argument('--shared-base', type=lambda s: int(s, 0), default=0x81000000)
    p.add_argument('--timeout', type=float, default=30)
    def run(args):
        from rvw.memory.cli import emit
        return emit(lambda: build(args.out, args.seed, args.harts, args.length, args.gcc,
                                  args.base, args.shared_base, args.timeout))
    p.set_defaults(func=run)


def mcp_tools():
    return [ToolSpec('memory_concurrent_build', 'Compile seeded RV64 per-hart ELFs, image manifest and axiomatic initial state. Does not execute a DUT.',
                     schema({'out': {'type': 'string'}, 'seed': {'type': 'integer', 'default': 1},
                             'harts': {'type': 'integer', 'default': 2}, 'length': {'type': 'integer', 'default': 16},
                             'gcc': {'type': 'string', 'default': 'riscv64-unknown-elf-gcc'},
                             'base': {'type': 'string', 'default': '0x80000000'},
                             'shared_base': {'type': 'string', 'default': '0x81000000'},
                             'timeout': {'type': 'number', 'default': 30}}, required=['out']), build,
        side_effects='long-running; launches compiler; writes per-hart ELFs under out', native_tools=('RISC-V GCC',),
        )]
