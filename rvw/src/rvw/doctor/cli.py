import json
from .check import diagnose


def register(subparsers):
    parser = subparsers.add_parser('doctor', help='Check setup and show required fixes')
    parser.add_argument('--features', default='sim,riscv-gcc', help='all or comma-separated sim,riscv-gcc,cosim,formal,gem5')
    parser.add_argument('--smoke-elf', help='Explicitly build and run this ELF for C1 conformance')
    parser.add_argument('--install', metavar='FEATURES', help='Explicitly run scripts/install.sh for these features')
    parser.add_argument('--yes', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--json', action='store_true')
    parser.set_defaults(func=run)


def run(args):
    result = diagnose(project=getattr(args, 'project', None), features=args.features,
                      install=args.install, yes=args.yes, dry_run=args.dry_run, smoke_elf=args.smoke_elf)
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
        for item in result.get('native', []):
            print(item['evidence'])
        if result.get('installation', {}).get('output'):
            print(result['installation']['output'])
    return result['exit_code']
