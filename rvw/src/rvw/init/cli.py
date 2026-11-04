import json
from .scaffold import scaffold


def register(subparsers):
    parser = subparsers.add_parser('init', help='Scaffold one Spinal/sbt core project')
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
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--json', action='store_true')
    parser.set_defaults(func=run)


def run(args):
    try:
        result = scaffold(args.path, isa=args.isa, xlen=args.xlen, name=args.name,
                          dry_run=args.dry_run, force=args.force, wire_build=args.wire_build,
                          sbt_project=args.sbt_project, linker_script=args.linker_script,
                          ram_region=args.ram_region, reset_pc=args.reset_pc, db_top=args.db_top)
    except (OSError, ValueError) as exc:
        result = dict(schema='rvw.init/1', status='error', exit_code=2, error=str(exc))
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
