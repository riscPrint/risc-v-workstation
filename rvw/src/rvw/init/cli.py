import json
from .scaffold import scaffold


def register(subparsers):
    parser = subparsers.add_parser('init', help='Scaffold one core project (Spinal/sbt, or --hdl sv|vhdl|chisel)')
    parser.add_argument('path', nargs='?', default='.')
    parser.add_argument('--isa')
    parser.add_argument('--xlen', type=int, choices=(32, 64))
    parser.add_argument('--name')
    parser.add_argument('--wire-build', action='store_true', help='Generate an sbt build with core and RiscvSim dependencies')
    parser.add_argument('--sbt-project', help='Explicit core sbt project ID; enables build wiring')
    parser.add_argument('--linker-script', help='Linker script with literal MEMORY entries')
    parser.add_argument('--ram-region', help='Selected RAM region from the linker script')
    parser.add_argument('--reset-pc', help='Reset address from the core specification')
    parser.add_argument('--db-top', help='No-argument Component class for a SpinalDB entry; enables build wiring')
    parser.add_argument('--hdl', choices=('sv', 'vhdl', 'chisel'),
                        help='Non-Spinal core: query build through slang, GHDL or firtool, Verilator C1 launcher')
    parser.add_argument('--top', help='Toplevel module, entity or Chisel module (--hdl)')
    parser.add_argument('--source', action='append', default=[], help='HDL source in order (--hdl; default: discovered)')
    parser.add_argument('-I', '--include', action='append', default=[], dest='include_dirs', help='Include directory (--hdl sv)')
    parser.add_argument('--library', default='work', help='VHDL work library (--hdl vhdl)')
    parser.add_argument('--fir', help='FIRRTL file the core build emits (--hdl chisel)')
    parser.add_argument('--source-root', action='append', default=[], dest='source_roots',
                        help='Scala source root (--hdl chisel; default src/main/scala)')
    mapped = parser.add_argument_group('mapped adapter (a working C1 adapter from a port mapping)')
    mapped.add_argument('--spinal-top', help='No-argument Spinal Component class of the core top')
    mapped.add_argument('--verilog-top', help='Verilog module of the core top (ports read with Yosys)')
    mapped.add_argument('--verilog', action='append', default=[], help='Verilog source file; repeatable')
    mapped.add_argument('--define', action='append', default=[], help='Verilog define NAME[=VALUE]; repeatable')
    mapped.add_argument('--param', action='append', default=[], help='Verilog parameter NAME=INT; repeatable')
    mapped.add_argument('--clock', default='clk', help='Verilog clock port (default clk)')
    mapped.add_argument('--reset', default='reset', help='Verilog reset port (default reset)')
    mapped.add_argument('--reset-active', choices=('high', 'low'), default='high')
    mapped.add_argument('--bus', action='append', default=[],
                        help=('NAME:PROTOCOL:key=port,...; repeatable. req-rsp requires cmd_valid,address,rsp_valid,rdata; '
                      'optional cmd_ready,write,wdata,mask,error,rsp_ready. valid-ready requires '
                      'valid,ready,address,rdata; optional wdata,mask. Add write_response=1 for store responses.'))
    mapped.add_argument('--rvfi-prefix', help='Prefix of the riscv-formal RVFI ports (default rvfi_ when present)')
    mapped.add_argument('--irq', action='append', default=[], help='MIP_BIT=port interrupt input; repeatable')
    mapped.add_argument('--const', action='append', default=[], help='port=value constant input; repeatable')
    mapped.add_argument('--ram', default='0x80000000:0x100000', help='RAM BASE:SIZE (default 0x80000000:0x100000)')
    mapped.add_argument('--accept-platform-defaults', action='store_true',
                        help='Write the cosim platform without review_required')
    mapped.add_argument('--yosys', default='yosys')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--json', action='store_true')
    parser.set_defaults(func=run)


def run(args):
    try:
        if args.hdl and not (args.hdl == 'sv' and args.reset_pc is not None):
            from .hdl import scaffold_hdl
            result = scaffold_hdl(args.path, hdl=args.hdl, top=args.top, isa=args.isa, name=args.name,
                                  sources=args.source, include_dirs=args.include_dirs, library=args.library,
                                  fir=args.fir, source_roots=args.source_roots, force=args.force,
                                  dry_run=args.dry_run)
            return _print(args, result)
        if args.spinal_top or args.verilog_top or args.hdl == 'sv':
            from .mapped import mapped_scaffold
            if args.hdl == 'sv' and args.include_dirs:
                raise ValueError('Mapped SV init does not yet support -I. Supply self-contained --source files.')
            if args.reset_pc is None:
                raise ValueError('The mapped adapter needs --reset-pc from the core specification.')
            result = mapped_scaffold(args.path, isa=args.isa, name=args.name, top=args.spinal_top,
                                     verilog_top=args.verilog_top or (args.top if args.hdl == 'sv' else None),
                                     verilog=args.verilog or args.source, defines=args.define,
                                     params=args.param, clock=args.clock, reset=args.reset,
                                     reset_active=args.reset_active, buses=args.bus, rvfi_prefix=args.rvfi_prefix,
                                     irq=args.irq, constants=args.const, reset_pc=args.reset_pc, ram=args.ram,
                                     sbt_project=args.sbt_project, accept_platform_defaults=args.accept_platform_defaults,
                                     yosys=args.yosys, force=args.force, dry_run=args.dry_run)
        else:
            result = scaffold(args.path, isa=args.isa, xlen=args.xlen, name=args.name,
                              dry_run=args.dry_run, force=args.force, wire_build=args.wire_build,
                              sbt_project=args.sbt_project, linker_script=args.linker_script,
                              ram_region=args.ram_region, reset_pc=args.reset_pc, db_top=args.db_top)
    except (OSError, ValueError) as exc:
        result = dict(schema='rvw.init/1', status='error', exit_code=2, error=str(exc))
    return _print(args, result)


def _print(args, result):
    if args.json:
        print(json.dumps(result, indent=2))
    elif result['exit_code']:
        print(result['error'])
    else:
        print(result['status'] + ': ' + result['root'])
        for path, content in result['files'].items():
            print(path)
            if args.dry_run:
                print(content)
        for action in result['next']:
            print(action)
    return result['exit_code']
