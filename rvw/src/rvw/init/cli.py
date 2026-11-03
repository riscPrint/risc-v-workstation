import json
from .scaffold import scaffold


def register(subparsers):
    parser = subparsers.add_parser('init', help='Scaffold one Spinal/sbt core project')
    parser.add_argument('path', nargs='?', default='.')
    parser.add_argument('--isa')
    parser.add_argument('--xlen', type=int, choices=(32, 64))
    parser.add_argument('--name')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--json', action='store_true')
    parser.set_defaults(func=run)


def run(args):
    try:
        result = scaffold(args.path, isa=args.isa, xlen=args.xlen, name=args.name,
                          dry_run=args.dry_run, force=args.force)
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
