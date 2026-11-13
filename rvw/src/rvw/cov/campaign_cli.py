"""CLI and MCP share the bounded execution loop."""
import json
from .campaign import campaign


def execute_json(action='campaign', settings=None, work_dir=None, resume=False, replay=None):
    if action != 'campaign':
        raise ValueError('unknown stimulus loop action')
    return campaign(settings, work_dir, resume, replay)


def run(args):
    try:
        result = execute_json(settings=args.settings, work_dir=args.work_dir, resume=args.resume, replay=args.replay)
        code = (0 if result['status']=='qualified' else
                1 if result['status'] in ('fail','mismatch','core_failure') else 3)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        result, code = {'schema':'rvw.stimulus-loop-error/1','status':'error','message':str(exc)}, 2
    print(json.dumps(result, indent=2))
    return code


def register(sub):
    parser = sub.add_parser('campaign', help='run bounded ISA candidates through C1 and strict Spike checks')
    parser.add_argument('--settings', required=True)
    parser.add_argument('--work-dir', required=True)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--replay', type=int, help='recheck an archived attempt in a fresh result directory')
    parser.add_argument('--json', action='store_true')
    parser.set_defaults(func=run)
