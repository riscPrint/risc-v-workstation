import json
from .check import diagnose, FEATURES


def register(subparsers):
    parser = subparsers.add_parser('doctor', help='Check setup and show required fixes')
    parser.add_argument('--skip-adapter-info', action='store_true', help='Skip adapter info, which can compile a launcher')
    parser.add_argument('--features', default='sim,riscv-gcc', help='all or comma-separated ' + ','.join(FEATURES))
    parser.add_argument('--smoke-elf', help='Explicitly build and run this ELF for C1 conformance')
    parser.add_argument('--smoke-options', default='', help='Comma-separated rvfi,wave,coverage,konata,spinaltrace')
    parser.add_argument('--smoke-platform', help='Reviewed platform JSON for an independent Spike C2 mapping check')
    parser.add_argument('--conformance', action='store_true',
                        help='With --smoke-elf: run the C1 option checks (configs, latency, determinism, limits, run-many, replay, refusals)')
    parser.add_argument('--install', metavar='FEATURES', help='Explicitly run scripts/install.sh for these features')
    parser.add_argument('--yes', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--resolve', choices=('act4', 'riscv-tests', 'riscv-formal', 'sail'))
    parser.add_argument('--acquire', action='store_true', help='Acquire a missing --resolve dependency')
    parser.add_argument('--json', action='store_true')
    parser.set_defaults(func=run)


def run(args):
    if getattr(args, 'resolve', None):
        from rvw.common.dependencies import resolve
        try:
            result = resolve(args.resolve, acquire=args.acquire)
        except (ValueError, RuntimeError, OSError) as exc:
            import sys
            print(str(exc), file=sys.stderr)
            return 2
        print(json.dumps(result) if args.json else result['path'])
        return 0
    if getattr(args, 'acquire', False):
        raise ValueError('--acquire requires --resolve')
    result = diagnose(project=getattr(args, 'project', None), features=args.features,
                      install=args.install, yes=args.yes, dry_run=args.dry_run, smoke_elf=args.smoke_elf, smoke_flags=args.smoke_options, smoke_platform=args.smoke_platform,
                      conformance=args.conformance, skip_adapter_info=args.skip_adapter_info)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print('doctor: ' + result['status'])
        if result.get('error'):
            print(result['error'])
        for check in result['checks']:
            print(f"{check['status']} {check['name']}: {check['detail']}")
            if check['status'] != 'ready':
                print('  Fix: ' + check['fix'])
        for name, workflow in result.get('workflows', {}).items():
            print(f"{name}: {workflow['status']} (setup preconditions only)")
        for item in result.get('tool_inventory', []):
            print(f"{item['area']}: {item['status']} {item['name']} ({item['install_command']})")
        for item in result.get('native', []):
            print(item['evidence'])
        if result.get('installation', {}).get('output'):
            print(result['installation']['output'])
    return result['exit_code']
