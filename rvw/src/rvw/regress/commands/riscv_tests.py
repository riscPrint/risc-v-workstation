"""Managed ISA build CLI and MCP."""
import json
from rvw.mcp.spec import ToolSpec, schema


def build(out, xlen=64, source=None, targets=None, environments='p,v', compiler_prefix='riscv64-unknown-elf-', timeout=300, jobs=2, elf_dir=None):
    from rvw.regress.isa_build import build as implementation
    return implementation(out, xlen, source, targets, environments, compiler_prefix, timeout, jobs, elf_dir)


def register(commands):
    p = commands.add_parser('riscv-tests-build', help='Build pinned ISA tests outside their source tree')
    p.add_argument('--out', required=True)
    p.add_argument('--xlen', type=int, choices=(32, 64), default=64)
    p.add_argument('--source')
    p.add_argument('--elf-dir', help='Optional explicit ELF directory')
    p.add_argument('--targets')
    p.add_argument('--environments', '--envs', default='p,v')
    p.add_argument('--compiler-prefix', default='riscv64-unknown-elf-')
    p.add_argument('--timeout', type=int, default=300)
    p.add_argument('--jobs', type=int, default=2)
    p.add_argument('--json', action='store_true')
    def run(a):
        try:
            result = build(a.out, a.xlen, a.source, a.targets, a.environments, a.compiler_prefix, a.timeout, a.jobs, a.elf_dir)
        except (ValueError, RuntimeError, OSError) as exc:
            import sys
            print(str(exc), file=sys.stderr)
            return 2
        print(json.dumps(result))
        return 0 if result['status'] == 'built' else 1
    p.set_defaults(func=run)


def mcp_tools():
    return [ToolSpec('regress_riscv_tests_build', 'Acquire pinned sources and build ISA ELFs. No DUT execution.',
                     schema({'out': {'type': 'string'}, 'xlen': {'type': 'integer'},
                             'source': {'type': 'string'}, 'targets': {'type': 'string'}}, ['out']),
                     build, side_effects='downloads sources and writes build outputs', native_tools=('RISC-V GCC',))]
